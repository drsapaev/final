"""Logging configuration helpers (plain and JSON structured)."""

from __future__ import annotations

import functools
import json
import logging
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.pii_masker import _mask_string_inplace, mask_pii

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
    """Render log records as one JSON object per line.

    ``formatException`` is overridden to scrub PII patterns (phone numbers,
    emails, passports, IINs) from the rendered traceback string. The
    ``record.exc_info`` tuple itself is left untouched, so Sentry SDK,
    OpenTelemetry, and other handlers that consume ``record.exc_info``
    continue to receive the original exception object.
    """

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

    def formatException(self, exc_info):  # noqa: A003 - logging API
        """Render the traceback and scrub PII patterns from the result.

        - ``record.exc_info`` is NOT modified; only the serialized string is.
        - When the traceback contains no PII patterns, the output is identical
          to ``super().formatException()`` — masking is a no-op.
        """
        tb = super().formatException(exc_info)
        return _mask_string_inplace(tb)


def _trusted_idempotency_fingerprint(
    record: logging.LogRecord,
) -> tuple[int, str] | None:
    """Identify the HMAC argument from the canonical idempotency logger only.

    The _dispatch method computes this field with _idempotency_key_log_fingerprint;
    arbitrary log records or unrecognized format strings must stay fully masked.
    """
    if (
        record.name != "app.middleware.idempotency_middleware"
        or record.funcName != "_dispatch"
        or not isinstance(record.pathname, str)
        or not record.pathname.replace("\\", "/").endswith(
            "/app/middleware/idempotency_middleware.py"
        )
        or not isinstance(record.msg, str)
        or not isinstance(record.args, tuple)
    ):
        return None

    marker = "key_fingerprint=%s"
    if record.msg.count(marker) != 1:
        return None
    prefix = record.msg.split(marker, 1)[0]
    index = 0
    offset = 0
    while offset < len(prefix):
        if prefix[offset] != "%":
            offset += 1
            continue
        if offset + 1 >= len(prefix) or prefix[offset + 1] not in ("%", "s"):
            return None
        if prefix[offset + 1] == "s":
            index += 1
        offset += 2

    if index >= len(record.args):
        return None
    value = record.args[index]
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{16}", value) is None:
        return None
    return index, value


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
            # Mask args (dict/list only — strings handled via message regex)
            if record.args:
                if isinstance(record.args, dict | list | tuple):
                    fingerprint = _trusted_idempotency_fingerprint(record)
                    record.args = mask_pii(
                        list(record.args)
                        if isinstance(record.args, tuple)
                        else record.args
                    )
                    if isinstance(record.args, list):
                        if fingerprint is not None:
                            index, value = fingerprint
                            record.args[index] = value
                        record.args = tuple(record.args)
                elif isinstance(record.args, str):
                    record.args = mask_pii(record.args)

            # Mask the formatted message too (catches f-strings + %-strings)
            # We can't reformat safely, so we scrub the msg field if it's a string.
            if isinstance(record.msg, str):
                # Local/formatted numbers may lack the country prefix or any
                # patient-related words, so digits must also trigger masking.
                if (
                    any(char.isdigit() for char in record.msg)
                    or "@" in record.msg
                    or "patient" in record.msg.lower()
                ):
                    record.msg = _mask_string_inplace(record.msg)
        except Exception:
            # Never let masking break logging
            pass
        return True  # always allow the record through



_sms_transport_active: ContextVar[bool] = ContextVar("sms_transport_active", default=False)
_click_transport_active: ContextVar[bool] = ContextVar("click_transport_active", default=False)
_telegram_preview_active: ContextVar[bool] = ContextVar("telegram_preview_active", default=False)


@contextmanager
def protect_telegram_preview_logs():
    """Redact scoped provider transport logs containing preview capabilities.

    Independent handlers and external instrumentation require operator review.
    """
    token = _telegram_preview_active.set(True)
    try:
        yield
    finally:
        _telegram_preview_active.reset(token)


@contextmanager
def protect_click_transport_logs():
    """Redact only this Click call on the configured application handler.

    Independently configured child handlers and external HTTP instrumentation
    are outside this handler's control and require deployment review.
    """
    token = _click_transport_active.set(True)
    try:
        yield
    finally:
        _click_transport_active.reset(token)


def protect_sms_transport_logs(function):
    """Scope SMS transport logging; independently configured handlers are external."""
    @functools.wraps(function)
    async def wrapped(*args, **kwargs):
        token = _sms_transport_active.set(True)
        try:
            return await function(*args, **kwargs)
        finally:
            _sms_transport_active.reset(token)
    return wrapped


class _SensitiveTransportFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if _telegram_preview_active.get() and record.name.split(".", 1)[0] in {
            "httpx", "httpcore", "aiohttp", "aiogram"
        }:
            record.msg = "Telegram preview transport event"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
            for field in _STRUCTURED_FIELDS:
                if hasattr(record, field):
                    setattr(record, field, None)
            return True
        if _click_transport_active.get() and (
            record.name == "httpx" or record.name.startswith("httpx.")
            or record.name == "httpcore" or record.name.startswith("httpcore.")
        ):
            # httpx INFO includes the full request URL. httpcore traces can
            # contain exception details or response headers. Keep severity and
            # logger identity without exposing order/payment IDs or Auth.
            record.msg = "Click provider transport event"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
            for field in _STRUCTURED_FIELDS:
                if hasattr(record, field):
                    setattr(record, field, None)
            return True
        # httpcore DEBUG includes repr(exception), potentially containing a
        # complete outbound SMS. Restrict only this task and transport.
        return not (
            _sms_transport_active.get()
            and record.levelno == logging.DEBUG
            and (record.name == "httpcore" or record.name.startswith("httpcore."))
        )

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

    handler.addFilter(_SensitiveTransportFilter())
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
