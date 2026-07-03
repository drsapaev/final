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


class PIIMaskingFilter(logging.Filter):
    """Logging filter that masks PII in record args + message.

    Attached to the root logger's handler in setup_logging(). Catches PII
    that developers accidentally log via:
        log.info('Patient: %s', patient_dict)
        log.info('Phone: %s', patient.phone)

    See app/core/pii_masker.py for the masking rules.

    Safety: never raises — masking failures are silently swallowed so they
    cannot break logging.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            from app.core.pii_masker import mask_pii

            # Mask args (dict/list only — strings handled via message regex)
            if record.args:
                if isinstance(record.args, (dict, list, tuple)):
                    record.args = mask_pii(list(record.args) if isinstance(record.args, tuple) else record.args)
                    if isinstance(record.args, list):
                        record.args = tuple(record.args)
                elif isinstance(record.args, str):
                    record.args = mask_pii(record.args)

            # Mask the formatted message too (catches f-strings + %-strings)
            # We can't reformat safely, so we scrub the msg field if it's a string.
            if isinstance(record.msg, str):
                # Only scrub if there's likely PII — quick check via presence of digits/+998
                if "+998" in record.msg or "@" in record.msg or "patient" in record.msg.lower():
                    from app.core.pii_masker import _mask_string_inplace
                    record.msg = _mask_string_inplace(record.msg)
        except Exception:
            # Never let masking break logging
            pass
        return True  # always allow the record through


def setup_logging(
    level: int = logging.INFO,
    *,
    structured: bool = False,
    format_string: str | None = None,
    date_format: str | None = None,
    enable_pii_masking: bool = True,
) -> None:
    """Configure application loggers.

    Args:
        level: root log level.
        structured: emit JSON logs (for production log aggregation) vs plain text.
        format_string: custom plain-text format. Ignored if structured=True.
        date_format: custom date format. Ignored if structured=True.
        enable_pii_masking: attach PIIMaskingFilter to the handler. Default True
            — disable only in unit tests where masking interferes with assertions.
    """
    handler = logging.StreamHandler(sys.stdout)
    if structured:
        handler.setFormatter(JsonLogFormatter())
    else:
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if date_format is None:
            date_format = "%Y-%m-%d %H:%M:%S"
        handler.setFormatter(logging.Formatter(format_string, datefmt=date_format))

    if enable_pii_masking:
        handler.addFilter(PIIMaskingFilter())

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
