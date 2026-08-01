"""Unit tests for ``app.api.v1.endpoints._error_logging.log_endpoint_error``.

Covers the in-place sanitization of ``context['error_message']`` — the field
is preserved (log contract stability) but its value is scrubbed of PII
patterns before being passed to ``logger.exception``.
"""
from __future__ import annotations

import io
import json
import logging

import pytest

from app.api.v1.endpoints._error_logging import log_endpoint_error
from app.core.logging_config import JsonLogFormatter, PIIMaskingFilter


@pytest.fixture
def capture_logger() -> tuple[logging.Logger, io.StringIO]:
    """Attach a JsonLogFormatter + PIIMaskingFilter handler to the
    ``_error_logging`` module logger and capture its output."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(PIIMaskingFilter())

    logger = logging.getLogger("app.api.v1.endpoints._error_logging")
    original_handlers = logger.handlers
    original_level = logger.level
    original_propagate = logger.propagate

    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    yield logger, buf

    # Restore
    logger.handlers = original_handlers
    logger.setLevel(original_level)
    logger.propagate = original_propagate


class TestLogEndpointError:
    """Validate PII scrubbing in ``log_endpoint_error``."""

    def test_log_endpoint_error_scrubs_phone_in_error_message(
        self, capture_logger: tuple[logging.Logger, io.StringIO]
    ) -> None:
        """``context['error_message']`` is sanitized in place.

        ``PIIMaskingFilter`` does not scrub values under the key
        ``error_message`` (it is not in ``PII_FIELD_PATTERNS``), so the
        scrubbing must happen in ``log_endpoint_error`` itself.
        """
        logger, buf = capture_logger

        try:
            raise ValueError("Patient phone +998901234567 update failed")
        except ValueError as exc:
            log_endpoint_error("POST /mobile/patient/profile", exc, user_id=42)

        output = buf.getvalue().strip()
        # The phone must NOT appear in raw form anywhere in the log line.
        assert "+998901234567" not in output
        # The masked form SHOULD appear (proves the value was sanitized,
        # not deleted).
        assert "+998901•••567" in output

    def test_log_endpoint_error_preserves_error_type(
        self, capture_logger: tuple[logging.Logger, io.StringIO]
    ) -> None:
        """``context['error_type']`` is preserved verbatim — devops needs
        the exception class name for triage."""
        logger, buf = capture_logger

        try:
            raise ValueError("some message")
        except ValueError as exc:
            log_endpoint_error("POST /mobile/foo", exc, user_id=1)

        payload = json.loads(buf.getvalue().strip())

        # error_type appears in payload['message'] (interpolated via %s).
        assert "ValueError" in payload["message"]
        # And in the traceback's last line: "ValueError: some message".
        assert "ValueError" in payload["exception"]

    def test_log_endpoint_error_does_not_leak_phi_in_message(
        self, capture_logger: tuple[logging.Logger, io.StringIO]
    ) -> None:
        """End-to-end check: after ``log_endpoint_error`` + ``PIIMaskingFilter``
        + ``JsonLogFormatter``, the phone does not appear in ``payload['message']``
        (which is built from ``record.msg`` + ``record.args``)."""
        logger, buf = capture_logger

        try:
            raise ValueError("Cannot update phone +998901234567 for patient")
        except ValueError as exc:
            log_endpoint_error("PUT /mobile/patient", exc, user_id=42)

        payload = json.loads(buf.getvalue().strip())

        assert "+998901234567" not in payload["message"]
        # But the masked form should be present.
        assert "+998901•••567" in payload["message"]
