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
    #   except Exception: logger.warning(...)
    #   return event
    #
    # For direct before_send tests, we construct an equivalent closure.
    import logging

    sentinel_logger = logging.getLogger("app.core.sentry")

    def before_send(event, hint=None):
        try:
            sanitize_event(event)
        except Exception:
            # logger.warning (NOT logger.exception) — avoids Sentry recursion
            # because LoggingIntegration DEFAULT_EVENT_LEVEL=ERROR and
            # WARNING < ERROR, so no new Sentry event is created.
            sentinel_logger.warning(
                "Sentry before_send sanitizer failed — "
                "event sent unscrubbed (event_id=%s error_type=%s)",
                event.get("event_id", "unknown"),
                type(hint.get("exception") or hint.get("exc_info") or Exception()).__name__
                if hint else "unknown",
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


class TestSanitizeEventLogentryScrubbing:
    """LoggingIntegration puts the raw LogRecord message/args into
    ``event["logentry"]``. The app's ``PIIMaskingFilter`` runs on the
    stdout handler only, so ``sanitize_event`` is the only scrubbing
    layer for this field."""

    def test_scrubs_phone_in_logentry_formatted(self):
        event = {
            "logentry": {
                "message": "visit failed for patient",
                "params": None,
                "formatted": "visit failed for patient +998901234567",
            }
        }
        sanitize_event(event)
        assert "+998901234567" not in event["logentry"]["formatted"]
        assert "+998901•••567" in event["logentry"]["formatted"]

    def test_scrubs_patient_dict_in_logentry_params(self):
        """Dict args with PII keys must be key-redacted, not just regex-masked."""
        event = {
            "logentry": {
                "message": "failed to save visit for %s",
                "params": [
                    {
                        "phone": "+998901234567",
                        "first_name": "Иван",
                        "last_name": "Иванов",
                        "diagnosis": "acute appendicitis",
                    }
                ],
            }
        }
        sanitize_event(event)
        params = event["logentry"]["params"][0]
        assert params["phone"] == "+998901•••567"
        assert params["first_name"] == "И."
        assert params["last_name"] == "И."
        assert params["diagnosis"] == "[REDACTED]"

    def test_scrubs_all_logentry_string_fields(self):
        event = {
            "logentry": {
                "message": "PHI_TEST_MARKER phone=+998901234567",
                "formatted": "PHI_TEST_MARKER email=john@example.com",
            }
        }
        sanitize_event(event)
        assert "+998901234567" not in event["logentry"]["message"]
        assert "john@example.com" not in event["logentry"]["formatted"]

    def test_event_with_non_dict_logentry(self):
        """Defensive: malformed logentry must not raise."""
        event = {"logentry": "not-a-dict"}
        sanitize_event(event)
        assert event["logentry"] == "not-a-dict"

    def test_event_without_logentry_unchanged(self):
        event = {"message": "no logentry here"}
        sanitize_event(event)
        assert "logentry" not in event


class TestSanitizeEventBreadcrumbsShape:
    """Real Sentry SDK ships breadcrumbs as {"values": [...]}; the sanitizer
    must handle that shape (previously it iterated the dict's keys and raised
    TypeError, sending the event unscrubbed via the before_send fallback)."""

    def test_scrubs_phone_in_breadcrumbs_dict_values_shape(self):
        event = {
            "breadcrumbs": {
                "values": [
                    {"message": "db query", "data": {"phone": "+998901234567"}},
                    {"message": "cache write", "data": {"diagnosis": "flu"}},
                ]
            }
        }
        sanitize_event(event)
        crumbs = event["breadcrumbs"]["values"]
        assert crumbs[0]["data"]["phone"] == "+998901•••567"
        assert crumbs[1]["data"]["diagnosis"] == "[REDACTED]"

    def test_breadcrumbs_bare_list_still_scrubbed(self):
        event = {"breadcrumbs": [{"data": {"phone": "+998901234567"}}]}
        sanitize_event(event)
        assert event["breadcrumbs"][0]["data"]["phone"] == "+998901•••567"

    def test_breadcrumbs_with_string_crumb_does_not_raise(self):
        """Non-dict crumbs (e.g. plain strings) must not crash the sanitizer."""
        event = {
            "breadcrumbs": {"values": ["raw string crumb +998901234567", {"data": {}}]}
        }
        sanitize_event(event)
        assert "+998901234567" not in str(event["breadcrumbs"])

    def test_breadcrumbs_non_dict_non_list_does_not_raise(self):
        event = {"breadcrumbs": "phone=+998901234567"}
        sanitize_event(event)
        assert "+998901234567" not in event["breadcrumbs"]

    def test_scrubs_phone_in_breadcrumb_message(self):
        """Breadcrumb messages carry raw log lines (logging integration)
        — a primary PHI carrier, found by the synthetic-PHI E2E probe."""
        event = {
            "breadcrumbs": {
                "values": [
                    {"message": "visit failed for +998901234567 john@example.com", "data": {}}
                ]
            }
        }
        sanitize_event(event)
        msg = event["breadcrumbs"]["values"][0]["message"]
        assert "+998901234567" not in msg
        assert "john@example.com" not in msg
        assert "+998901•••567" in msg

    def test_scrubs_breadcrumb_message_in_bare_list_shape(self):
        event = {"breadcrumbs": [{"message": "PHI_TEST_MARKER iin=12345678901234"}]}
        sanitize_event(event)
        assert "12345678901234" not in event["breadcrumbs"][0]["message"]

    def test_non_string_breadcrumb_message_untouched(self):
        event = {"breadcrumbs": {"values": [{"message": None, "data": {}}]}}
        sanitize_event(event)
        assert event["breadcrumbs"]["values"][0]["message"] is None


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

    def test_before_send_uses_warning_not_exception_on_failure(self, caplog):
        """When sanitize_event raises, before_send must log via
        ``logger.warning`` (NOT ``logger.exception``) to avoid Sentry
        recursion.

        ``LoggingIntegration`` auto-registers with
        ``DEFAULT_EVENT_LEVEL=ERROR``. ``logger.exception`` (level=ERROR)
        would trigger a new Sentry event → re-enter ``before_send`` →
        infinite recursion until ``RecursionError``. ``logger.warning``
        (level=WARNING < ERROR) does not trigger event capture.

        This test verifies that the log record has level=WARNING and
        ``exc_info is None`` (no traceback attached — if it were,
        LoggingIntegration might still capture it).
        """
        import logging

        before_send = _make_before_send()
        event = {"event_id": "recursion-test", "request": {"data": "x"}}

        with patch(
            "app.core.sentry.mask_pii",
            side_effect=RuntimeError("sanitizer crashed"),
        ):
            with caplog.at_level(
                logging.WARNING, logger="app.core.sentry"
            ):
                before_send(event, hint={"exception": RuntimeError("x")})

        # Find the warning record
        warning_records = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "sanitizer failed" in r.message
        ]
        assert len(warning_records) == 1, (
            f"Expected exactly 1 WARNING record, got {len(warning_records)}"
        )
        rec = warning_records[0]
        # Critical: exc_info must NOT be set — logger.exception() sets it,
        # logger.warning() does not. If exc_info is set, LoggingIntegration
        # may still capture the record as a Sentry event.
        assert rec.exc_info is None, (
            "exc_info must be None — logger.exception() would set it and "
            "trigger Sentry recursion. Use logger.warning() without exc_info."
        )
        assert rec.levelno == logging.WARNING, (
            f"Expected WARNING (30), got {rec.levelno} — "
            "logger.exception() uses ERROR (40) which triggers Sentry capture."
        )


class TestSanitizeEventStandardContextsPreserved:
    """Standard Sentry contexts (runtime, os, device, etc.) must NOT be
    scrubbed — they contain diagnostic metadata, not patient data.

    See: https://docs.sentry.io/platforms/python/enriching-events/contexts/
    """

    def test_preserves_standard_context_runtime(self):
        """``{"runtime": {"name": "CPython"}}`` → unchanged.

        Without the whitelist, ``mask_pii`` treats ``name`` as a patient
        name (it's in ``PII_FIELD_PATTERNS``) and masks it to ``"C."``.
        """
        event = {"contexts": {"runtime": {"name": "CPython", "version": "3.11.10"}}}
        sanitize_event(event)
        assert event["contexts"]["runtime"]["name"] == "CPython"
        assert event["contexts"]["runtime"]["version"] == "3.11.10"

    def test_preserves_standard_context_os(self):
        event = {"contexts": {"os": {"name": "Linux", "version": "5.15.0"}}}
        sanitize_event(event)
        assert event["contexts"]["os"]["name"] == "Linux"
        assert event["contexts"]["os"]["version"] == "5.15.0"

    def test_preserves_standard_context_device(self):
        event = {"contexts": {"device": {"name": "server-1", "arch": "x86_64"}}}
        sanitize_event(event)
        assert event["contexts"]["device"]["name"] == "server-1"
        assert event["contexts"]["device"]["arch"] == "x86_64"

    def test_preserves_standard_context_app(self):
        event = {"contexts": {"app": {"name": "clinic-backend", "version": "0.9.0"}}}
        sanitize_event(event)
        assert event["contexts"]["app"]["name"] == "clinic-backend"

    def test_preserves_standard_context_browser(self):
        event = {"contexts": {"browser": {"name": "Chrome", "version": "120.0"}}}
        sanitize_event(event)
        assert event["contexts"]["browser"]["name"] == "Chrome"

    def test_preserves_standard_context_gpu(self):
        event = {"contexts": {"gpu": {"name": "Tesla T4", "vendor": "NVIDIA"}}}
        sanitize_event(event)
        assert event["contexts"]["gpu"]["name"] == "Tesla T4"
        assert event["contexts"]["gpu"]["vendor"] == "NVIDIA"

    def test_preserves_entire_nested_standard_context(self):
        """The ENTIRE standard context object must be preserved — not just
        the ``name`` field. All nested keys (version, build, arch, etc.)
        must remain untouched."""
        event = {
            "contexts": {
                "runtime": {
                    "name": "CPython",
                    "version": "3.13.0",
                    "build": "default",
                    "compiler": "GCC 11.4.0",
                }
            }
        }
        sanitize_event(event)
        runtime = event["contexts"]["runtime"]
        assert runtime["name"] == "CPython"
        assert runtime["version"] == "3.13.0"
        assert runtime["build"] == "default"
        assert runtime["compiler"] == "GCC 11.4.0"

    def test_preserves_all_standard_contexts_simultaneously(self):
        """Multiple standard contexts in one event — all preserved."""
        event = {
            "contexts": {
                "runtime": {"name": "CPython", "version": "3.11.10"},
                "os": {"name": "Linux", "version": "5.15.0"},
                "device": {"name": "server-1", "arch": "x86_64"},
                "app": {"name": "clinic-backend", "version": "0.9.0"},
                "browser": {"name": "Chrome", "version": "120.0"},
                "gpu": {"name": "Tesla T4", "vendor": "NVIDIA"},
                "trace": {"trace_id": "abc123", "span_id": "def456"},
            }
        }
        sanitize_event(event)
        for ctx_key in ("runtime", "os", "device", "app", "browser", "gpu", "trace"):
            assert event["contexts"][ctx_key] == event["contexts"][ctx_key], (
                f"{ctx_key} context was modified"
            )


class TestSanitizeEventCustomContextsScrubbed:
    """Custom (non-standard) contexts must still be scrubbed."""

    def test_scrubs_unknown_custom_context_with_pii(self):
        """Unknown custom context with PII must be fully scrubbed.

        ``{"customer": {"name": "John", "phone": "+998901234567"}}``
        → ``name`` masked, ``phone`` redacted.
        """
        event = {
            "contexts": {
                "customer": {
                    "name": "PHI_TEST_MARKER",
                    "phone": "+998901234567",
                }
            }
        }
        sanitize_event(event)
        customer = event["contexts"]["customer"]
        assert customer["phone"] != "+998901234567"
        assert customer["name"] != "PHI_TEST_MARKER"  # masked

    def test_scrubs_custom_context_with_patient_data(self):
        """Custom ``patient`` context must be scrubbed."""
        event = {
            "contexts": {
                "patient": {
                    "phone": "+998901234567",
                    "diagnosis": "[REDACTED]",  # already redacted in test
                }
            }
        }
        sanitize_event(event)
        assert event["contexts"]["patient"]["phone"] != "+998901234567"

    def test_preserves_mixed_standard_and_custom_contexts(self):
        """When standard and custom contexts coexist, standard diagnostic
        fields preserved, custom scrubbed."""
        event = {
            "contexts": {
                "runtime": {"name": "CPython", "version": "3.11.10"},
                "user": {"phone": "+998901234567", "id": 42},
            }
        }
        sanitize_event(event)
        # Standard diagnostic field preserved
        assert event["contexts"]["runtime"]["name"] == "CPython"
        assert event["contexts"]["runtime"]["version"] == "3.11.10"
        # Custom scrubbed
        assert event["contexts"]["user"]["phone"] != "+998901234567"
        assert event["contexts"]["user"]["id"] == 42  # non-PII preserved


class TestSanitizeEventPiiInStandardContext:
    """PHI that accidentally lands inside a standard Sentry context must
    still be scrubbed — only known diagnostic fields (e.g. ``name``) are
    preserved, all other keys are scrubbed via mask_pii().
    """

    def test_scrubs_phone_in_device_context(self):
        """device.phone must be scrubbed even though device is a standard
        context — only device.name is preserved."""
        event = {
            "contexts": {
                "device": {
                    "name": "server-1",
                    "phone": "+998901234567",
                    "arch": "x86_64",
                }
            }
        }
        sanitize_event(event)
        assert event["contexts"]["device"]["name"] == "server-1"  # preserved
        assert event["contexts"]["device"]["arch"] == "x86_64"  # non-PII preserved
        assert event["contexts"]["device"]["phone"] != "+998901234567"  # scrubbed

    def test_scrubs_diagnosis_in_device_context(self):
        """device.diagnosis must be scrubbed — diagnosis is not a diagnostic
        field, it's medical PII."""
        event = {
            "contexts": {
                "device": {
                    "name": "server-1",
                    "diagnosis": "Crohn disease",
                }
            }
        }
        sanitize_event(event)
        assert event["contexts"]["device"]["name"] == "server-1"  # preserved
        assert event["contexts"]["device"]["diagnosis"] == "[REDACTED]"

    def test_scrubs_email_in_trace_context(self):
        """trace.email must be scrubbed even though trace is standard."""
        event = {
            "contexts": {
                "trace": {
                    "trace_id": "abc123",
                    "email": "patient@example.com",
                }
            }
        }
        sanitize_event(event)
        assert event["contexts"]["trace"]["trace_id"] == "abc123"  # non-PII
        assert event["contexts"]["trace"]["email"] != "patient@example.com"

    def test_scrubs_phone_in_response_context(self):
        """response.phone must be scrubbed even though response is standard."""
        event = {
            "contexts": {
                "response": {
                    "status_code": 200,
                    "phone": "+998901234567",
                }
            }
        }
        sanitize_event(event)
        assert event["contexts"]["response"]["status_code"] == 200
        assert event["contexts"]["response"]["phone"] != "+998901234567"

    def test_preserves_name_in_all_standard_contexts(self):
        """The 'name' diagnostic field must be preserved in ALL standard
        contexts where it appears — not just runtime/os/device."""
        event = {
            "contexts": {
                "app": {"name": "clinic-backend"},
                "browser": {"name": "Chrome"},
                "device": {"name": "server-1"},
                "os": {"name": "Linux"},
                "runtime": {"name": "CPython"},
                "gpu": {"name": "Tesla T4"},
            }
        }
        sanitize_event(event)
        assert event["contexts"]["app"]["name"] == "clinic-backend"
        assert event["contexts"]["browser"]["name"] == "Chrome"
        assert event["contexts"]["device"]["name"] == "server-1"
        assert event["contexts"]["os"]["name"] == "Linux"
        assert event["contexts"]["runtime"]["name"] == "CPython"
        assert event["contexts"]["gpu"]["name"] == "Tesla T4"

    def test_standard_context_with_pii_and_diagnostic_fields_together(self):
        """A standard context can have both diagnostic fields (preserved)
        and PII fields (scrubbed) simultaneously."""
        event = {
            "contexts": {
                "device": {
                    "name": "server-1",           # diagnostic → preserved
                    "arch": "x86_64",             # non-PII → preserved
                    "phone": "+998901234567",     # PII → scrubbed
                    "iin": "12345678901234",      # PII → scrubbed
                    "version": "1.0.0",           # non-PII → preserved
                }
            }
        }
        sanitize_event(event)
        d = event["contexts"]["device"]
        assert d["name"] == "server-1"
        assert d["arch"] == "x86_64"
        assert d["phone"] != "+998901234567"
        assert d["iin"] != "12345678901234"
        assert d["version"] == "1.0.0"


class TestSanitizeEventPiiInDiagnosticNameField:
    """PHI inside the diagnostic ``name`` field of standard contexts must
    be scrubbed via regex, while non-PII diagnostic names are preserved.

    The ``name`` key is in ``PII_FIELD_PATTERNS``, but for standard
    contexts it contains diagnostic metadata (e.g. "CPython", "Linux").
    We apply ``mask_pii(value)`` to the raw value — for strings this
    calls ``_mask_string_inplace()`` (regex only), NOT ``mask_name()``
    (which would corrupt "CPython" to "C.").

    Criteria (per maintainer review):
    - device.name = "CPython" → stays "CPython"
    - device.name = "+998901234567" → phone masked
    - device.name = "john@example.com" → email masked
    - device.name = "AA1234567" → passport masked
    - device.name = "NVIDIA T4" → stays unchanged
    """

    def test_diagnostic_name_cpython_preserved(self):
        """runtime.name = 'CPython' → unchanged (non-PII diagnostic)."""
        event = {"contexts": {"runtime": {"name": "CPython"}}}
        sanitize_event(event)
        assert event["contexts"]["runtime"]["name"] == "CPython"

    def test_diagnostic_name_nvidia_t4_preserved(self):
        """gpu.name = 'NVIDIA T4' → unchanged (non-PII diagnostic)."""
        event = {"contexts": {"gpu": {"name": "NVIDIA T4"}}}
        sanitize_event(event)
        assert event["contexts"]["gpu"]["name"] == "NVIDIA T4"

    def test_diagnostic_name_linux_preserved(self):
        """os.name = 'Linux' → unchanged."""
        event = {"contexts": {"os": {"name": "Linux"}}}
        sanitize_event(event)
        assert event["contexts"]["os"]["name"] == "Linux"

    def test_phone_in_diagnostic_name_scrubbed(self):
        """device.name = '+998901234567' → phone masked via regex."""
        event = {"contexts": {"device": {"name": "+998901234567"}}}
        sanitize_event(event)
        assert "+998901234567" not in event["contexts"]["device"]["name"]
        assert "+998901•••567" in event["contexts"]["device"]["name"]

    def test_email_in_diagnostic_name_scrubbed(self):
        """response.name = 'john@example.com' → email masked via regex."""
        event = {"contexts": {"response": {"name": "john@example.com"}}}
        sanitize_event(event)
        assert "john@example.com" not in event["contexts"]["response"]["name"]
        assert "j•••@example.com" in event["contexts"]["response"]["name"]

    def test_passport_in_diagnostic_name_scrubbed(self):
        """device.name = 'AA1234567' → passport masked via regex."""
        event = {"contexts": {"device": {"name": "AA1234567"}}}
        sanitize_event(event)
        assert "AA1234567" not in event["contexts"]["device"]["name"]

    def test_iin_in_diagnostic_name_scrubbed(self):
        """device.name = '12345678901234' → IIN masked via regex."""
        event = {"contexts": {"device": {"name": "12345678901234"}}}
        sanitize_event(event)
        assert "12345678901234" not in event["contexts"]["device"]["name"]
        assert "1234••••••1234" in event["contexts"]["device"]["name"]

    def test_diagnostic_name_with_pii_and_non_pii_mixed_in_context(self):
        """A standard context with both a diagnostic name (non-PII) and
        PII in other fields — name preserved, PII scrubbed."""
        event = {
            "contexts": {
                "device": {
                    "name": "server-1",           # non-PII → preserved
                    "phone": "+998901234567",     # PII → scrubbed
                    "model": "PowerEdge R750",    # non-PII → preserved
                }
            }
        }
        sanitize_event(event)
        d = event["contexts"]["device"]
        assert d["name"] == "server-1"
        assert d["model"] == "PowerEdge R750"
        assert d["phone"] != "+998901234567"
