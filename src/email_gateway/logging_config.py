"""JSON lines on stderr for the email-gateway process.

Each line is one object: ``level``, ``logger``, ``msg``, plus any of
``_EXTRA_LOG_KEYS`` present on the record. Call sites pass those as
``extra={...}``. Subject, body, and recipient are not extra keys.
"""

from __future__ import annotations

import json
import logging
import logging.config
from typing import Any

# Extra keys copied onto the JSON object (stdlib ``logger.info(..., extra=)``).
_EXTRA_LOG_KEYS = (
    "uid",
    "reply_source",
    "skip_reason",
    "http_status",
    "workflow_run_id",
    "seen",
    "count",
    "exc_type",
    "fail_reason",
    "outputs_error",
    "dify_error_code",
    "workflow_status",
    "is_sent",
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line; extras limited to ``_EXTRA_LOG_KEYS``."""

    def format(self, record: logging.LogRecord) -> str:
        """Build ``level``, ``logger``, ``msg``, then listed extras."""
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in _EXTRA_LOG_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


LOGGING_CONFIG: dict[str, Any] = {
    # logging.config.dictConfig schema version (not our app version).
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": JsonFormatter,
        },
    },
    "handlers": {
        "default": {
            "formatter": "json",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "email_gateway": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["default"],
        # Same floor as email_gateway; third-party loggers inherit this.
        "level": "INFO",
    },
}


def configure_logging() -> None:
    """Apply JSON dictConfig for the email-gateway logger tree."""
    logging.config.dictConfig(LOGGING_CONFIG)
