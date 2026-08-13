"""Shared fixtures for ticketing contract/unit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from ticketing.config import Settings
from ticketing.db import Base, make_engine
from ticketing.main import create_app
from ticketing.mcp_server import configure_mcp_runtime


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:15.13-alpine") as pg:
        # psycopg3 driver URL
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        yield url


@pytest.fixture
def ticketing_settings(postgres_url: str) -> Settings:
    return Settings(
        database_url=postgres_url,
        escalation_seconds=86_400,
    )


@pytest.fixture
async def ticketing_app(
    ticketing_settings: Settings,
) -> AsyncIterator[FastAPI]:
    """Ticketing app with DB writes rolled back after the test.

    Session ``commit()`` releases a SAVEPOINT; teardown rolls back the
    outer transaction. Schema bootstrap and MCP wiring are applied here
    so the process lifespan is not required.
    """
    engine = make_engine(ticketing_settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as connection:
        trans = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        app = create_app(
            ticketing_settings,
            db_session_factory=factory,
            db_engine=engine,
        )
        configure_mcp_runtime(ticketing_settings, make_db_session=factory)
        app.state.settings = ticketing_settings
        app.state.db_session_factory = factory
        yield app
        await trans.rollback()
    await engine.dispose()


@pytest.fixture
async def ticketing_client(
    ticketing_app: FastAPI,
) -> AsyncIterator[AsyncClient]:
    """Async HTTP client on the same loop as MCP helpers and the outer txn."""
    async with AsyncClient(
        transport=ASGITransport(app=ticketing_app),
        base_url="http://test",
    ) as http_client:
        yield http_client
