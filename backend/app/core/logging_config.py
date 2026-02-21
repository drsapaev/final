"""Logging configuration helpers (plain and JSON structured)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_STRUCTURED_FIELDS = (
    "request_id",
    "trace_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "client_ip",
    "error",
)


class JsonLogFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    level: int = logging.INFO,
    *,
    structured: bool = False,
    format_string: str | None = None,
    date_format: str | None = None,
) -> None:
    """Configure application loggers."""
    handler = logging.StreamHandler(sys.stdout)
    if structured:
        handler.setFormatter(JsonLogFormatter())
    else:
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if date_format is None:
            date_format = "%Y-%m-%d %H:%M:%S"
        handler.setFormatter(logging.Formatter(format_string, datefmt=date_format))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)

    # Keep noisy third-party loggers quiet by default.
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get module logger."""
    return logging.getLogger(name)
