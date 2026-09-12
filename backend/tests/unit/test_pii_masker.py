"""Unit tests for app.core.pii_masker.

Covers:
- Per-field maskers (phone, email, passport, IIN, name, birth_date)
- Recursive mask_pii() on nested dict/list structures
- _mask_string_inplace() regex-based scrubbing on free text
- PIIMaskingFilter integration with logging.LogRecord
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pytest

from app.core.pii_masker import (
    PIIMaskingFilter,
    mask_birth_date,
    mask_email,
    mask_iin,
    mask_name,
    mask_passport,
    mask_phone,
    mask_pii,
)


# ---------------------------------------------------------------------------
# Per-field maskers
# ---------------------------------------------------------------------------


class TestMaskPhone:
    def test_full_uz_phone_number(self):
        assert mask_phone("+998901234567") == "+998901•••567"

    def test_returns_none_for_none(self):
        assert mask_phone(None) is None

    def test_returns_empty_for_empty(self):
        assert mask_phone("") == ""

    def test_leaves_non_phone_string_untouched(self):
        # No 9+ digits after country code → no match
        assert mask_phone("hello") == "hello"

    def test_masks_only_valid_phone_pattern(self):
        # Too short to match (less than 7 digits before last 3)
        assert mask_phone("+99812345") == "+99812345"


class TestMaskEmail:
    def test_masks_local_part(self):
        result = mask_email("john.doe@example.com")
        assert result == "j•••@example.com"
        assert "john.doe" not in result

    def test_returns_none_for_none(self):
        assert mask_email(None) is None

    def test_returns_empty_for_empty(self):
        assert mask_email("") == ""

    def test_preserves_domain(self):
        result = mask_email("alice@mail.example.org")
        assert result.endswith("@mail.example.org")

    def test_single_char_local(self):
        # Single char local part should still produce j•••@domain
        result = mask_email("a@example.com")
        assert "@example.com" in result


class TestMaskPassport:
    def test_masks_uz_passport_format(self):
        result = mask_passport("AB1234567")
        assert "1234567" not in result
        assert result.startswith("AB")

    def test_returns_none_for_none(self):
        assert mask_passport(None) is None

    def test_leaves_non_passport_untouched(self):
        assert mask_passport("hello world") == "hello world"


class TestMaskIin:
    def test_masks_14_digit_iin(self):
        result = mask_iin("12345678901234")
        assert "567890" not in result
        assert result.startswith("1234")
        assert result.endswith("1234")

    def test_returns_none_for_none(self):
        assert mask_iin(None) is None


class TestMaskName:
    def test_masks_full_name_to_initials(self):
        assert mask_name("Иван Иванов") == "И.И."

    def test_masks_three_part_name(self):
        assert mask_name("Иван Иванов Иванович") == "И.И.И."

    def test_handles_single_name(self):
        assert mask_name("Akmal") == "A."

    def test_returns_none_for_none(self):
        assert mask_name(None) is None

    def test_returns_empty_for_empty(self):
        assert mask_name("") == ""

    def test_handles_extra_whitespace(self):
        result = mask_name("  Akmal   Karimov  ")
        assert result == "A.K."


class TestMaskBirthDate:
    def test_masks_date_object(self):
        d = date(1985, 6, 15)
        result = mask_birth_date(d)
        assert "1985" in result
        assert "06" not in result
        assert "15" not in result

    def test_masks_iso_string(self):
        result = mask_birth_date("1985-06-15")
        assert result == "1985-••-••"

    def test_returns_none_for_none(self):
        assert mask_birth_date(None) is None

    def test_returns_year_only(self):
        # Year should always be visible
        result = mask_birth_date(date(2000, 1, 1))
        assert "2000" in result


# ---------------------------------------------------------------------------
# Recursive mask_pii
# ---------------------------------------------------------------------------


class TestMaskPii:
    def test_returns_none_for_none(self):
        assert mask_pii(None) is None

    def test_returns_scalar_unchanged(self):
        assert mask_pii(42) == 42
        assert mask_pii(True) is True

    def test_masks_dict_with_pii_fields(self):
        patient = {
            "first_name": "Akmal",
            "last_name": "Karimov",
            "phone": "+998901234567",
            "email": "akmal@example.com",
            "iin": "12345678901234",
            "diagnosis": "I10 Essential hypertension",
            "id": 42,  # not PII
        }
        result = mask_pii(patient)
        assert result["first_name"] == "A."
        assert result["last_name"] == "K."
        assert result["phone"] == "+998901•••567"
        assert "akmal" not in result["email"]
        assert result["iin"] == "[REDACTED]"
        assert result["diagnosis"] == "[REDACTED]"
        assert result["id"] == 42  # untouched

    def test_recurses_into_nested_dict(self):
        data = {
            "patient": {
                "phone": "+998901234567",
                "address": "ул. Мирзо Улугбека, 42",
            },
            "metadata": {"count": 1},
        }
        result = mask_pii(data)
        assert result["patient"]["phone"] == "+998901•••567"
        assert result["patient"]["address"] == "[REDACTED]"
        assert result["metadata"]["count"] == 1

    def test_recurses_into_list(self):
        data = [
            {"phone": "+998901234567"},
            {"phone": "+998911234567"},
        ]
        result = mask_pii(data)
        assert len(result) == 2
        for item in result:
            assert "1234567" not in item["phone"]

    def test_recurses_into_list_of_strings(self):
        # Strings inside a list get regex-masked
        data = ["Call +998901234567 for help", "no PII here"]
        result = mask_pii(data)
        assert "1234567" not in result[0]
        assert "+998901•••567" in result[0]
        assert result[1] == "no PII here"

    def test_handles_empty_structures(self):
        assert mask_pii({}) == {}
        assert mask_pii([]) == []

    def test_redacts_all_known_pii_keys(self):
        """Every field in PII_FIELD_PATTERNS should be redacted."""
        pii_keys = [
            "iin", "passport_number", "doc_number",
            "diagnosis", "icd10_code", "complaints",
            "prescription", "medications", "allergies",
            "visit_reason", "doctor_notes",
            "address",
        ]
        for key in pii_keys:
            data = {key: "some value"}
            result = mask_pii(data)
            assert result[key] == "[REDACTED]", f"Field {key!r} not redacted: {result[key]!r}"


# ---------------------------------------------------------------------------
# _mask_string_inplace (called via mask_pii on string-typed values)
# ---------------------------------------------------------------------------


class TestMaskStringInplace:
    def test_masks_phone_in_free_text(self):
        text = "Patient called from +998901234567"
        result = mask_pii(text)
        assert "1234567" not in result
        assert "+998901•••567" in result

    def test_masks_email_in_free_text(self):
        text = "Contact: john.doe@example.com please"
        result = mask_pii(text)
        assert "john.doe" not in result

    def test_masks_passport_in_free_text(self):
        text = "Passport AB1234567 issued"
        result = mask_pii(text)
        assert "1234567" not in result

    def test_masks_iin_in_free_text(self):
        text = "IIN: 12345678901234"
        result = mask_pii(text)
        assert "567890" not in result

    def test_masks_multiple_pii_in_one_string(self):
        text = "Phone +998901234567, email john@example.com, IIN 12345678901234"
        result = mask_pii(text)
        assert "1234567" not in result
        assert "john" not in result
        assert "567890" not in result


# ---------------------------------------------------------------------------
# PIIMaskingFilter (logging integration)
# ---------------------------------------------------------------------------


class TestPIIMaskingFilter:
    def setup_method(self):
        self.filter = PIIMaskingFilter()
        self.logger = logging.getLogger("test.pii_filter")

    def _make_record(self, msg: str, args: Any = None) -> logging.LogRecord:
        return self.logger.makeRecord(
            name="test.pii_filter",
            level=logging.INFO,
            fn="test.py",
            lno=1,
            msg=msg,
            args=args,
            exc_info=None,
        )

    def test_filter_returns_true_always(self):
        record = self._make_record("hello")
        assert self.filter.filter(record) is True

    def test_filter_masks_phone_in_args(self):
        record = self._make_record("Phone: %s", ("+998901234567",))
        self.filter.filter(record)
        # Args are tuple — after masking becomes tuple
        assert "1234567" not in str(record.args)

    def test_filter_masks_phone_in_message_string(self):
        record = self._make_record("Phone +998901234567 called")
        self.filter.filter(record)
        assert "1234567" not in record.msg
        assert "+998901•••567" in record.msg

    def test_filter_does_not_touch_non_pii_message(self):
        record = self._make_record("User logged in successfully")
        original = record.msg
        self.filter.filter(record)
        assert record.msg == original

    def test_filter_never_raises_on_bad_input(self):
        # Pass weird args that would crash masking — filter should swallow
        record = self._make_record("Data: %s", (object(),))
        # Should not raise
        result = self.filter.filter(record)
        assert result is True

    def test_filter_masks_dict_arg(self):
        patient = {"first_name": "Akmal", "phone": "+998901234567"}
        record = self._make_record("Patient %s", (patient,))
        self.filter.filter(record)
        masked = record.args[0]
        assert masked["first_name"] == "A."
        assert masked["phone"] == "+998901•••567"

    def test_filter_skips_when_no_args(self):
        record = self._make_record("Plain message no args")
        original = record.msg
        self.filter.filter(record)
        assert record.msg == original


# ---------------------------------------------------------------------------
# PR-6: secret credential fields (push device registry)
# Provider credentials must never leave the infrastructure through Sentry
# captures or structured logs — codex P1 on the PR-6 registry.
# ---------------------------------------------------------------------------


class TestSecretFieldRedaction:
    def test_redacts_push_credential_keys(self):
        from app.core.pii_masker import SECRET_FIELD_PATTERNS

        for key in ("token", "previous_token", "device_token", "fcm_token", "push_token"):
            assert key in SECRET_FIELD_PATTERNS
            result = mask_pii({key: "super-secret-credential-value"})
            assert result[key] == "[REDACTED]", f"{key!r} leaked: {result[key]!r}"

    def test_redacts_token_inside_nested_request_body(self):
        # Sentry attaches the request body of /push/devices/* on a 5xx
        body = {
            "provider": "fcm",
            "platform": "android",
            "token": "pr6-secret-credential",
            "previous_token": "pr6-old-credential",
            "device_id": "dev-1",
        }
        result = mask_pii(body)
        assert result["token"] == "[REDACTED]"
        assert result["previous_token"] == "[REDACTED]"
        assert result["provider"] == "fcm"  # non-secret metadata survives
        assert result["device_id"] == "dev-1"

    def test_redacts_credential_shaped_json_in_raw_string(self):
        # Raw string request bodies (not parsed into a dict) — the JSON
        # credential regex must catch the string form.
        raw = '{"provider":"fcm","token":"pr6-secret-credential","device_id":"dev-1"}'
        masked = mask_pii(raw)
        assert "pr6-secret-credential" not in masked
        assert '"token":"[REDACTED]"' in masked or '"token": "[REDACTED]"' in masked
        assert '"device_id":"dev-1"' in masked or '"device_id": "dev-1"' in masked

    def test_redacts_previous_token_json_in_raw_string(self):
        raw = '{"token":"new-cred","previous_token":"old-secret-cred"}'
        masked = mask_pii(raw)
        assert "old-secret-cred" not in masked

    def test_prose_word_token_is_not_redacted(self):
        # Conservative by design: only credential-shaped JSON keys are
        # redacted, never prose.
        prose = "The token refresh happened at noon"
        assert mask_pii(prose) == prose

    def test_token_fingerprint_key_survives(self):
        # The non-secret fingerprint is the intended identifier — it must
        # NOT be redacted by the secret-field list. Value is deliberately
        # low-entropy prose so secret scanners never flag this test file.
        result = mask_pii({"token_fingerprint": "sample-fingerprint-value"})
        assert result["token_fingerprint"] == "sample-fingerprint-value"

    def test_nested_dict_credential_redacted_recursively(self):
        data = {"request": {"data": {"token": "pr6-secret", "keep": 1}}}
        result = mask_pii(data)
        assert result["request"]["data"]["token"] == "[REDACTED]"
        assert result["request"]["data"]["keep"] == 1


# ---------------------------------------------------------------------------
# PR-6 round 4 (codex P1): string values under ordinary dict keys must go
# through the free-text scrub pass. Fresh evidence: Sentry may represent
# request.data as a RAW JSON STRING under the key "data" — key-based
# redaction leaves ordinary string-valued fields unchanged, so the
# credential-shaped JSON regex was never reached and the full credential
# survived in the outbound event.
# ---------------------------------------------------------------------------


class TestNestedStringValueScrubbing:
    def test_raw_json_string_under_data_key_is_scrubbed(self):
        raw = '{"provider":"fcm","token":"pr6-secret-credential","device_id":"dev-1"}'
        result = mask_pii({"data": raw})
        assert "pr6-secret-credential" not in result["data"]
        assert '"token":"[REDACTED]"' in result["data"]

    def test_raw_json_string_in_sentry_request_shape(self):
        # The exact shape codex flagged: event["request"] with data as a
        # raw JSON string instead of a parsed dict.
        event_request = {
            "url": "https://clinic.invalid/api/v1/push/devices/register",
            "method": "POST",
            "data": '{"token":"pr6-secret-credential","previous_token":"pr6-old-credential"}',
        }
        result = mask_pii(event_request)
        assert "pr6-secret-credential" not in result["data"]
        assert "pr6-old-credential" not in result["data"]

    def test_plain_string_values_keep_free_text_masking(self):
        # Phone/email inside string values are still scrubbed, prose and
        # diagnostic values survive untouched.
        result = mask_pii(
            {"data": "call +998901234567", "model": "iPhone 15 Pro"}
        )
        assert "+998901•••567" in result["data"]
        assert result["model"] == "iPhone 15 Pro"

    def test_nested_string_inside_lists_is_scrubbed(self):
        result = mask_pii({"frames": [{'body': '{"token":"pr6-secret-credential"}'}]})
        assert "pr6-secret-credential" not in result["frames"][0]["body"]

    def test_scrubbing_is_idempotent_on_string_values(self):
        raw = '{"token":"pr6-secret-credential"}'
        once = mask_pii({"data": raw})
        twice = mask_pii(once)
        assert twice == once

    def test_redacts_escaped_webpush_subscription_in_raw_string(self):
        # A webpush credential is a serialized subscription object: in a
        # raw request body its quotes arrive ESCAPED. A plain [^"]+ value
        # matcher stopped at the first escaped quote and left the endpoint
        # and key material exposed — the value part must be escape-aware.
        raw = (
            '{"token":"{\\"endpoint\\":\\"https://push.example.com/send/abc\\",'
            '\\"keys\\":{\\"p256dh\\":\\"key-material\\",\\"auth\\":\\"auth-material\\"}}"}'
        )
        result = mask_pii({"data": raw})
        assert "endpoint" not in result["data"]
        assert "key-material" not in result["data"]
        assert "auth-material" not in result["data"]
        assert "push.example.com" not in result["data"]
        assert '"token":"[REDACTED]"' in result["data"]

    def test_escape_aware_matcher_keeps_plain_tokens_working(self):
        # The escape-aware value part must still redact ordinary tokens
        # that contain no escapes at all.
        result = mask_pii({"data": '{"token":"pr6-plain-credential"}'})
        assert "pr6-plain-credential" not in result["data"]
        assert '"token":"[REDACTED]"' in result["data"]

    def test_redacts_json_unicode_escaped_credential_key(self):
        # Valid JSON may spell the key itself as a unicode escape
        # ("\u0074oken" == "token") — Pydantic accepts it after decoding,
        # but a literal-key regex would miss it. JSON-aware parsing
        # routes every key spelling through key-based redaction.
        raw = '{"\\u0074oken":"pr6-secret-credential"}'
        result = mask_pii({"data": raw})
        assert "pr6-secret-credential" not in result["data"]
        assert '"token":"[REDACTED]"' in result["data"]

    def test_json_document_string_is_reserialized_compactly(self):
        # Structural scrubbing re-serializes compactly: non-secret fields
        # survive with stable key order and compact separators.
        raw = '{"provider":"fcm","token":"pr6-secret-credential","device_id":"dev-1"}'
        result = mask_pii({"data": raw})
        assert '"provider":"fcm"' in result["data"]
        assert '"device_id":"dev-1"' in result["data"]
        assert '"token":"[REDACTED]"' in result["data"]

    def test_non_json_prose_still_uses_regex_pass(self):
        # Prose that merely starts with a brace but does not parse as JSON
        # must still go through the free-text regex pass.
        prose = '{"not json here — call +998901234567'
        result = mask_pii({"data": prose})
        assert "+998901•••567" in result["data"]

    def test_form_encoded_credential_assignment_is_scrubbed(self):
        # Round 10 (codex P1): form/urlencoded bodies carry credentials as
        # UNQUOTED assignments — invisible to the quoted-JSON regex.
        raw = "token=pr6-secret-credential&provider=fcm"
        result = mask_pii({"data": raw})
        assert "pr6-secret-credential" not in result["data"]
        assert "token=[REDACTED]" in result["data"]
        assert "provider=fcm" in result["data"]

    def test_percent_encoded_form_credential_is_scrubbed(self):
        # Round 11 (codex P1): valid form bodies may percent-encode the KEY
        # itself ("%74oken" == "token") — the masker must decode before
        # applying credential redaction.
        raw = "%74oken=pr6-secret-credential&provider=fcm"
        result = mask_pii({"data": raw})
        assert "pr6-secret-credential" not in result["data"]
        assert "token=[REDACTED]" in result["data"]

    def test_encoded_delimiter_inside_value_is_fully_redacted(self):
        # Round 12 (codex P1): an encoded & (%26) INSIDE the credential
        # value must not split it — pairs are parsed on RAW delimiters and
        # the credential field redacted WHOLE before any value decoding.
        raw = (
            "token=https%3A%2F%2Fpush.example%2Fsend%3Fa%3D1%26key%3Dsecret"
            "&provider=fcm"
        )
        result = mask_pii({"data": raw})
        assert "secret" not in result["data"]
        assert "key=" not in result["data"].replace("send?a=1", "")
        assert "provider=fcm" in result["data"]
