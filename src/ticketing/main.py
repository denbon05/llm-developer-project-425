"""Ticketing process entry: schema bootstrap, gateway HTTP, MCP mount.

``create_all`` runs at process start; Alembic under ``migrations/``
is the reproducible schema path.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ticketing import db
from ticketing.config import Settings, get_settings
from ticketing.http import register_exception_handlers
from ticketing.http import router as http_router
from ticketing.logging_config import (
    LOGGING_CONFIG,
    configure_logging,
    get_logger,
)
from ticketing.mcp_server import configure_mcp_runtime, mcp

logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    db_session_factory: async_sessionmaker[AsyncSession] | None = None,
    db_engine: AsyncEngine | None = None,
) -> FastAPI:
    # Configure logging before building the app so early logs use shared format.
    configure_logging()
    settings = settings or get_settings()
    if db_session_factory is None and db_engine is None:
        # Session factory + process-wide engine (pool bound into the factory).
        db_session_factory, db_engine = db.make_session_factory(
            settings.database_url
        )
        owns_engine = True
    elif db_session_factory is not None and db_engine is not None:
        owns_engine = False
    else:
        raise ValueError(
            "db_session_factory and db_engine must both be set or both omitted"
        )
    # Path "/" under mount "/mcp" → public URL /mcp.
    # host=settings.host avoids localhost-only DNS rebinding defaults
    mcp_http = mcp.streamable_http_app(
        streamable_http_path="/",
        host=settings.host,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Bootstrap tables from the shared ORM registry.
        # create_all is sync; run_sync adapts it to this async connection.
        async with db_engine.begin() as conn:
            await conn.run_sync(db.Base.metadata.create_all)
        configure_mcp_runtime(settings, make_db_session=db_session_factory)
        app.state.settings = settings
        app.state.db_session_factory = db_session_factory
        async with mcp.session_manager.run():
            logger.info(
                "ticketing ready on %s:%s", settings.host, settings.port
            )
            yield
        if owns_engine:
            await db_engine.dispose()

    app = FastAPI(title="ticketing", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(http_router)
    app.mount("/mcp", mcp_http)
    return app


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "ticketing.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=LOGGING_CONFIG,
    )


if __name__ == "__main__":
    main()
