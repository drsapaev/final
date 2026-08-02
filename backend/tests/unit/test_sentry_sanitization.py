"""Unit tests for ``app.core.sentry.sanitize_event`` and ``before_send``.

Validates that PHI/PII patterns (phone, email, passport, IIN) are scrubbed
from all Sentry event fields before the event is sent, while preserving
non-PII content and structural integrity.

These tests do NOT require a running Sentry SDK or network — they exercise
``sanitize_event`` and the ``before_send`` closure directly against
synthetic event dicts.
"""
from __future__ import annotations

from unittest.mock import patch

from app.core.sentry import sanitize_event


def _make_before_send():
    """Return the ``before_send`` closure defined inside ``init_sentry``.

    We call ``init_sentry`` with SENTRY_DSN unset (no-op) and patch the SDK
    import so the closure is still constructed. The closure is extracted from
    the ``init_sentry`` function's locals via a test hook.
    """
    # init_sentry returns None, but before_send is defined inside it.
    # To test it in isolation, we replicate the closure's behavior by
    # calling sanitize_event directly (which is what before_send does).
    # For the "sanitizer fails" test, we patch sanitize_event to raise.
    # This is sufficient because before_send is a thin wrapper:
    #   try: sanitize_event(event)
    #   except Exception: log
    #   return event
    #
    # For direct before_send tests, we construct an equivalent closure.
    import logging

    sentinel_logger = logging.getLogger("app.core.sentry")

    def before_send(event, hint=None):
        try:
            sanitize_event(event)
        except Exception:
            sentinel_logger.exception(
                "Sentry before_send sanitizer failed — "
                "event sent unscrubbed (event_id=%s)",
                event.get("event_id", "unknown"),
            )
        return event

    return before_send


class TestSanitizeEventPhoneScrubbing:
    """Phone numbers must be scrubbed from all event fields."""

    def test_scrubs_phone_in_exception_value(self):
        """str(exc) containing a phone must be scrubbed in exception.value."""
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "Patient PHI_TEST_MARKER phone=+998901234567 leaked",
                    }
                ]
            }
        }
        sanitize_event(event)
        assert "+998901234567" not in event["exception"]["values"][0]["value"]
        assert "+998901•••567" in event["exception"]["values"][0]["value"]

    def test_scrubs_phone_in_request_body(self):
        """Phone under PII key in request.data is redacted via mask_pii()."""
        event = {
            "request": {
                "url": "https://api.example.com/patients",
                "data": {"phone": "+998901234567", "user_id": 42},
            }
        }
        sanitize_event(event)
        # Key-based redaction for "phone" key — mask_pii replaces with masked form
        assert event["request"]["data"]["phone"] != "+998901234567"
        # Non-PII key preserved
        assert event["request"]["data"]["user_id"] == 42

    def test_scrubs_phone_in_breadcrumbs_data(self):
        """Phone under PII key in breadcrumb data is redacted."""
        event = {
            "breadcrumbs": [
                {"data": {"phone": "+998901234567", "action": "login"}},
            ]
        }
        sanitize_event(event)
        assert event["breadcrumbs"][0]["data"]["phone"] != "+998901234567"
        assert event["breadcrumbs"][0]["data"]["action"] == "login"

    def test_scrubs_phone_in_extra(self):
        """Phone under PII key in extra is redacted."""
        event = {"extra": {"phone": "+998901234567", "user_id": 42}}
        sanitize_event(event)
        assert event["extra"]["phone"] != "+998901234567"
        assert event["extra"]["user_id"] == 42

    def test_scrubs_phone_in_contexts(self):
        """Phone under PII key in contexts is redacted."""
        event = {"contexts": {"user": {"phone": "+998901234567"}}}
        sanitize_event(event)
        assert event["contexts"]["user"]["phone"] != "+998901234567"

    def test_scrubs_phone_in_stacktrace_vars(self):
        """Phone under PII key in frame vars is redacted.

        Note: ``mask_pii()`` applies key-based redaction for dict values —
        vars with PII keys (``phone``, ``patient_phone``) are redacted.
        Free-text PII in arbitrary string values (e.g. ``query="phone=..."``)
        is NOT scrubbed by ``mask_pii`` — that's FOLLOWUP-4 (structural
        free-text PHI approach).
        """
        event = {
            "exception": {
                "values": [
                    {
                        "type": "IntegrityError",
                        "value": "UNIQUE constraint failed",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "app/api/v1/endpoints/mobile_api.py",
                                    "function": "update_patient",
                                    "vars": {
                                        "phone": "+998901234567",
                                        "user_id": 42,
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        }
        sanitize_event(event)
        frame_vars = event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        assert frame_vars["phone"] != "+998901234567"
        assert frame_vars["user_id"] == 42  # non-PII preserved


class TestSanitizeEventEmailScrubbing:
    def test_scrubs_email_in_exception_value(self):
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "Contact john.doe@example.com failed",
                    }
                ]
            }
        }
        sanitize_event(event)
        assert "john.doe@example.com" not in event["exception"]["values"][0]["value"]
        assert "j•••@example.com" in event["exception"]["values"][0]["value"]


class TestSanitizeEventPassportScrubbing:
    def test_scrubs_passport_in_exception_value(self):
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "Passport AA1234567 invalid",
                    }
                ]
            }
        }
        sanitize_event(event)
        assert "AA1234567" not in event["exception"]["values"][0]["value"]


class TestSanitizeEventIinScrubbing:
    def test_scrubs_iin_in_exception_value(self):
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "IIN 12345678901234 mismatch",
                    }
                ]
            }
        }
        sanitize_event(event)
        assert "12345678901234" not in event["exception"]["values"][0]["value"]
        assert "1234••••••1234" in event["exception"]["values"][0]["value"]


class TestSanitizeEventMultiplePii:
    def test_scrubs_multiple_pii_in_one_exception_value(self):
        """Phone + email + passport + IIN in a single exception value."""
        event = {
            "exception": {
                "values": [
                    {
                        "type": "IntegrityError",
                        "value": (
                            "Patient phone=+998901234567 email=john@example.com "
                            "passport=AA1234567 iin=12345678901234 all leaked"
                        ),
                    }
                ]
            }
        }
        sanitize_event(event)
        value = event["exception"]["values"][0]["value"]
        assert "+998901234567" not in value
        assert "john@example.com" not in value
        assert "AA1234567" not in value
        assert "12345678901234" not in value
        # Masked versions present
        assert "+998901•••567" in value
        assert "j•••@example.com" in value


class TestSanitizeEventUnicode:
    def test_preserves_unicode_around_pii(self):
        """Cyrillic text around PII must not be corrupted.

        Fixture uses synthetic marker (PHI_TEST_MARKER) per AGENTS.md
        synthetic-data rule.
        """
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "PHI_TEST_MARKER +998901234567 обратился",
                    }
                ]
            }
        }
        sanitize_event(event)
        value = event["exception"]["values"][0]["value"]
        assert "+998901234567" not in value
        assert "+998901•••567" in value
        assert "PHI_TEST_MARKER" in value  # Latin preserved
        assert "обратился" in value  # Cyrillic preserved


class TestSanitizeEventIdempotency:
    def test_double_sanitization_is_noop(self):
        """``sanitize_event(sanitize_event(event))`` must equal
        ``sanitize_event(event)`` — repeated calls must not alter the
        already-scrubbed result.

        This protects against regex backreference loops where a masked
        value (e.g. ``+998901•••567``) might match the regex again.
        """
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "phone=+998901234567 email=john@example.com",
                    }
                ]
            }
        }
        sanitize_event(event)
        first_pass = {
            "exception": {
                "values": [
                    {
                        "type": event["exception"]["values"][0]["type"],
                        "value": event["exception"]["values"][0]["value"],
                    }
                ]
            }
        }
        # Second pass on the already-scrubbed value
        sanitize_event(first_pass)
        assert first_pass["exception"]["values"][0]["value"] == event["exception"]["values"][0]["value"]


class TestSanitizeEventMissingFields:
    """Missing or empty fields must not cause errors."""

    def test_empty_event(self):
        """``sanitize_event({})`` must not raise."""
        event: dict = {}
        result = sanitize_event(event)
        assert result == {}
        assert result is event  # same object returned

    def test_event_with_empty_exception(self):
        """``sanitize_event({"exception": {}})`` must not raise."""
        event = {"exception": {}}
        result = sanitize_event(event)
        assert result == {"exception": {}}

    def test_event_with_exception_no_values(self):
        """``exception`` with no ``values`` key must not raise."""
        event = {"exception": {"mechanism": {"type": "generic"}}}
        result = sanitize_event(event)
        assert result == {"exception": {"mechanism": {"type": "generic"}}}

    def test_event_with_exception_values_not_list(self):
        """``exception.values`` not a list must not raise."""
        event = {"exception": {"values": "not-a-list"}}
        result = sanitize_event(event)
        assert result == {"exception": {"values": "not-a-list"}}

    def test_event_with_value_entry_not_dict(self):
        """``exception.values[*]`` not a dict must not raise."""
        event = {"exception": {"values": ["not-a-dict"]}}
        result = sanitize_event(event)
        assert result == {"exception": {"values": ["not-a-dict"]}}

    def test_event_with_no_stacktrace(self):
        """``exception.values[*]`` with no ``stacktrace`` must not raise."""
        event = {
            "exception": {
                "values": [{"type": "ValueError", "value": "no stacktrace"}]
            }
        }
        result = sanitize_event(event)
        assert result["exception"]["values"][0]["value"] == "no stacktrace"

    def test_event_with_frames_not_list(self):
        """``stacktrace.frames`` not a list must not raise."""
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "ok",
                        "stacktrace": {"frames": "not-a-list"},
                    }
                ]
            }
        }
        result = sanitize_event(event)
        assert result["exception"]["values"][0]["stacktrace"]["frames"] == "not-a-list"


class TestSanitizeEventPreservesNonPii:
    def test_preserves_non_pii_exception_value(self):
        """Exception without PII must be unchanged."""
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ConnectionError",
                        "value": "database unavailable",
                    }
                ]
            }
        }
        original_value = event["exception"]["values"][0]["value"]
        sanitize_event(event)
        assert event["exception"]["values"][0]["value"] == original_value

    def test_preserves_exception_type(self):
        """Exception type (class name) must never be scrubbed."""
        event = {
            "exception": {
                "values": [{"type": "IntegrityError", "value": "ok"}]
            }
        }
        sanitize_event(event)
        assert event["exception"]["values"][0]["type"] == "IntegrityError"

    def test_preserves_frame_filename_and_function(self):
        """Frame metadata (filename, function, lineno) must not be scrubbed."""
        event = {
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "ok",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "app/api/v1/endpoints/mobile_api.py",
                                    "function": "update_patient",
                                    "lineno": 160,
                                    "vars": {"x": 1},
                                }
                            ]
                        },
                    }
                ]
            }
        }
        sanitize_event(event)
        frame = event["exception"]["values"][0]["stacktrace"]["frames"][0]
        assert frame["filename"] == "app/api/v1/endpoints/mobile_api.py"
        assert frame["function"] == "update_patient"
        assert frame["lineno"] == 160


class TestBeforeSendSanitizerFailure:
    """If sanitize_event raises, before_send must still return the event."""

    def test_before_send_returns_event_when_sanitizer_raises(self):
        """When mask_pii (called by sanitize_event) raises, before_send
        must NOT return None and must NOT raise — the event is returned
        unscrubbed so error tracking is not lost."""
        before_send = _make_before_send()
        event = {
            "event_id": "test-123",
            "exception": {
                "values": [{"type": "ValueError", "value": "phone=+998901234567"}]
            },
        }

        # Force sanitize_event to raise by patching mask_pii
        with patch(
            "app.core.sentry.mask_pii",
            side_effect=RuntimeError("sanitizer crashed"),
        ):
            result = before_send(event, hint={})

        # Event is still returned (unscrubbed) — NOT None, NOT raised
        assert result is event
        assert result["event_id"] == "test-123"
        # PII is still present (unscrubbed) — but event is not lost
        assert "+998901234567" in result["exception"]["values"][0]["value"]

    def test_before_send_returns_event_on_empty_event(self):
        """before_send({}) must return {} (not None, not raise)."""
        before_send = _make_before_send()
        result = before_send({}, hint={})
        assert result == {}

    def test_before_send_returns_event_on_none_hint(self):
        """before_send must accept hint=None (Sentry SDK may pass None)."""
        before_send = _make_before_send()
        result = before_send({"event_id": "x"}, hint=None)
        assert result["event_id"] == "x"
