"""Unit tests for ``app.core.logging_config.JsonLogFormatter``.

Covers the ``formatException`` override that scrubs PII patterns (phone
numbers, emails, passports, IINs) from the rendered traceback string while
leaving ``record.exc_info`` untouched.

These tests do not require a running application — they exercise the
formatter in isolation against synthetic exceptions.
"""
from __future__ import annotations

import json
import logging
import re

from app.core.logging_config import JsonLogFormatter


def _build_record(exc: BaseException) -> logging.LogRecord:
    """Build a LogRecord whose ``exc_info`` is the LIVE traceback of ``exc``.

    ``exc`` must already carry ``__traceback__`` (i.e. it must have been
    raised and caught at the call site). The record's ``pathname`` / ``lineno``
    / ``func`` fields are populated so the rendered traceback contains
    predictable anchors that the structure-preservation test can assert on.
    """
    assert exc.__traceback__ is not None, "exception must be raised before passing"
    exc_info = (type(exc), exc, exc.__traceback__)
    return logging.LogRecord(
        name="test.json_log_formatter",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Endpoint failed",
        args=None,
        exc_info=exc_info,
        func="test_function",
    )


class TestJsonLogFormatterFormatException:
    """Validate the PII-scrubbing override of ``formatException``."""

    def test_format_exception_masks_phone_in_traceback(self) -> None:
        """Phone in ``str(exc)`` is scrubbed in ``payload['exception']``."""
        try:
            raise ValueError("Patient phone +998901234567 leaked")
        except ValueError as exc:
            record = _build_record(exc)

        payload = json.loads(JsonLogFormatter().format(record))

        assert "+998901234567" not in payload["exception"]
        assert "+998901•••567" in payload["exception"]

    def test_format_exception_masks_email_in_traceback(self) -> None:
        """Email in ``str(exc)`` is scrubbed."""
        try:
            raise ValueError("Contact john.doe@example.com failed")
        except ValueError as exc:
            record = _build_record(exc)

        payload = json.loads(JsonLogFormatter().format(record))

        assert "john.doe@example.com" not in payload["exception"]
        assert "j•••@example.com" in payload["exception"]

    def test_format_exception_masks_iin_in_traceback(self) -> None:
        """IIN (14-digit) in ``str(exc)`` is scrubbed."""
        try:
            raise ValueError("IIN 12345678901234 mismatch")
        except ValueError as exc:
            record = _build_record(exc)

        payload = json.loads(JsonLogFormatter().format(record))

        assert "12345678901234" not in payload["exception"]
        assert "1234••••••1234" in payload["exception"]

    def test_format_exception_preserves_exc_info_tuple(self) -> None:
        """``record.exc_info`` remains a ``(type, value, tb)`` tuple after
        ``format()`` — type and exception object identity preserved.

        Sentry SDK, OpenTelemetry, and other handlers that read
        ``record.exc_info`` continue to receive the original exception.
        """
        sentinel = ValueError("boom with phone +998901234567")
        try:
            raise sentinel
        except ValueError as exc:
            assert exc is sentinel
            record = _build_record(exc)

        _ = JsonLogFormatter().format(record)

        assert record.exc_info is not None
        exc_type, exc_value, tb = record.exc_info
        assert exc_type is ValueError
        # The exception OBJECT is the same instance — not a copy.
        assert exc_value is sentinel
        # Traceback object is preserved.
        assert tb is not None

    def test_format_exception_preserves_traceback_structure(self) -> None:
        """After masking, the traceback still contains the diagnostic
        anchors a human needs: exception type, file path, line number,
        function name."""
        try:
            raise ValueError("Patient phone +998901234567 leaked")
        except ValueError as exc:
            record = _build_record(exc)

        payload = json.loads(JsonLogFormatter().format(record))
        tb = payload["exception"]

        # Exception type name preserved.
        assert "ValueError" in tb
        # File path preserved (this test file is the raise site).
        assert re.search(r'File ".*test_json_log_formatter\.py"', tb)
        # Line number preserved (the raise is on a real line in this file).
        assert re.search(r"line \d+", tb)
        # Function name preserved (the test method appears in the traceback).
        assert "test_format_exception_preserves_traceback_structure" in tb
        # And the PII is scrubbed.
        assert "+998901234567" not in tb
        assert "+998901•••567" in tb

    def test_format_exception_without_pii_is_unchanged(self) -> None:
        """When ``str(exc)`` has no PII patterns, the patched
        ``JsonLogFormatter.formatException()`` output must be byte-identical
        to the base ``logging.Formatter.formatException()`` output for the
        SAME ``exc_info`` — masking is a no-op.

        Both renderers receive the exact same ``(type, value, tb)`` tuple,
        so any difference in output must come from ``_mask_string_inplace``
        side effects on non-PII text. Protects against accidental regex
        substitutions on ordinary tracebacks.
        """
        try:
            raise ConnectionError("database unavailable")
        except ConnectionError as exc:
            record = _build_record(exc)

        # Same exc_info tuple passed to BOTH formatters — apples-to-apples.
        same_exc_info = record.exc_info

        # New (patched) formatter.
        patched_output = JsonLogFormatter().formatException(same_exc_info)

        # Base logging.Formatter — bypasses our override entirely.
        parent_output = logging.Formatter().formatException(same_exc_info)

        assert patched_output == parent_output

    def test_format_exception_preserves_unicode_around_pii(self) -> None:
        """When ``str(exc)`` mixes Cyrillic/Uzbek/emoji text with a phone
        number, the phone must be scrubbed while all surrounding Unicode
        characters are preserved verbatim.

        Guards against regex side effects on multibyte content (the project's
        primary language is Russian; patient messages frequently contain
        Cyrillic + Latin + digits in one string).

        Fixture uses an explicitly synthetic marker (``PHI_TEST_MARKER``) and
        a zero-suffixed phone number (``+998900000001``) so it cannot be
        mistaken for real patient data per AGENTS.md synthetic-data rule.
        """
        try:
            raise ValueError("PHI_TEST_MARKER +998900000001 обратился")
        except ValueError as exc:
            record = _build_record(exc)

        payload = json.loads(JsonLogFormatter().format(record))
        tb = payload["exception"]

        # PII scrubbed.
        assert "+998900000001" not in tb
        assert "+998900•••001" in tb
        # Cyrillic word preserved verbatim (no mojibake, no truncation).
        assert "PHI_TEST_MARKER" in tb
        assert "обратился" in tb
        # Exception type preserved.
        assert "ValueError" in tb
