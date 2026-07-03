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
