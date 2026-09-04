"""Email-gateway process: private HTTP listener and IMAP poll loop."""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from email_gateway.clients import mailbox
from email_gateway.config import Settings, get_settings
from email_gateway.http import router as http_router
from email_gateway.logging_config import LOGGING_CONFIG, configure_logging
from email_gateway.processor import Processor

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI app without starting the IMAP poll loop."""
    configure_logging()
    settings = settings or get_settings()
    app = FastAPI(title="email-gateway")
    app.state.settings = settings
    app.state.mailbox = mailbox.Client(settings)
    app.include_router(http_router)
    return app


async def run(settings: Settings) -> None:
    """Serve digest HTTP and poll IMAP until cancelled."""
    app = create_app(settings)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=settings.host,
            port=settings.port,
            log_config=LOGGING_CONFIG,
        )
    )
    processor = Processor(settings)
    logger.info("email_gateway_start")
    await asyncio.gather(server.serve(), processor.poll_with_interval())


def main() -> None:
    """Process entry: JSON logs, env settings, then HTTP plus poll."""
    configure_logging()
    settings = get_settings()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
