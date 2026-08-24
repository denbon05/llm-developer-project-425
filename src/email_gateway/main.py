"""Email-gateway process: IMAP poll loop."""

from __future__ import annotations

import asyncio
import logging

from email_gateway.config import Settings, get_settings
from email_gateway.logging_config import configure_logging
from email_gateway.processor import Processor

logger = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    """Run the IMAP poll loop until cancelled."""
    processor = Processor(settings)
    logger.info("email_gateway_start")
    await processor.poll_with_interval()


def main() -> None:
    """Process entry: JSON logs, env settings, then the poll loop."""
    configure_logging() # configure logger on init
    settings = get_settings()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
