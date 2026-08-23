"""JSON logs with opaque refs only (SEC-5): no subject/body/recipient."""

from __future__ import annotations

import json
import logging
import logging.config
from typing import Any

# Extra keys that may appear on LogRecord (never subject/body/recipient).
_SAFE_EXTRA = (
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
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line; extra fields are an allowlist."""

    def format(self, record: logging.LogRecord) -> str:
        """Build one JSON object: level, logger, msg, allowlisted extras."""
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in _SAFE_EXTRA:
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
            # INFO: operational events only; bodies never go in extra.
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


def get_logger(name: str) -> logging.Logger:
    """Logger for ``name``; use ``__name__`` under the email_gateway tree."""
    return logging.getLogger(name)
