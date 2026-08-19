"""Email-gateway process: IMAP poll loop."""

from __future__ import annotations

import asyncio

from email_gateway.config import Settings, get_settings
from email_gateway.logging_config import configure_logging, get_logger
from email_gateway.processor import Processor

logger = get_logger(__name__)


async def run(settings: Settings) -> None:
    """Run the IMAP poll loop until cancelled."""
    processor = Processor(settings)
    logger.info("email_gateway_start")
    await processor.poll_with_interval()


def main() -> None:
    """Process entry: JSON logs, env settings, then the poll loop."""
    configure_logging()
    settings = get_settings()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
