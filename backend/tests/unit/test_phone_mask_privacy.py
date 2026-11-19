"""Synthetic regressions for phone redaction in fields and diagnostics."""

from __future__ import annotations

import json
import logging

import pytest

from app.core.logging_config import PIIMaskingFilter as AppLogFilter
from app.core.pii_masker import (
    PIIMaskingFilter as CoreLogFilter,
)
from app.core.pii_masker import (
    mask_identifier,
    mask_phone,
    mask_pii,
    mask_pii_text,
)


@pytest.mark.parametrize(
    "phone",
    [
        "000000000",
        "+000000000000",
        "+000 00 000 00 00",
        "+000 (00) 000-00-00",
        "+000\u00a000\u00a0000\u00a000\u00a000",
        "+000\u201100\u2011000\u201100\u201100",
    ],
)
def test_phone_fields_keep_only_the_last_three_digits(phone: str) -> None:
    assert mask_phone(phone) == "•••000"
    assert mask_pii({"phone": phone}) == {"phone": "•••000"}
    assert json.loads(mask_pii(json.dumps({"phone": phone}))) == {"phone": "•••000"}


@pytest.mark.parametrize("phone", ["unrecognized", "12", "+000"])
def test_unrecognized_phone_field_fails_closed(phone: str) -> None:
    assert mask_phone(phone) == "***"
    assert mask_pii({"phone_number": phone}) == {"phone_number": "***"}


@pytest.mark.parametrize(
    "phone",
    [
        "000000000",
        "+000 00 000 00 00",
        "+000\u00a000\u00a0000\u00a000\u00a000",
        "+000\u201100\u2011000\u201100\u201100",
    ],
)
def test_diagnostic_text_scrubs_local_and_formatted_phones(phone: str) -> None:
    masked = mask_pii_text(f"SYNTHETIC contact: {phone}")
    assert masked == "SYNTHETIC contact: •••000"
    assert mask_pii_text(masked) == masked


def test_numeric_login_identifier_keeps_only_the_tail() -> None:
    assert mask_identifier("000000000") == "•••000"
    assert mask_identifier("000\u00a0000\u00a0000") == "•••000"


def test_phone_followed_by_letters_does_not_expose_its_digits() -> None:
    assert mask_pii_text("SYNTHETIC 000 000 000ext") == "SYNTHETIC •••000ext"
    assert mask_pii_text("SYNTHETICphone000000000") == "SYNTHETICphone•••000"


def test_previously_partial_phone_is_masked_again() -> None:
    assert mask_pii_text("SYNTHETIC +000000•••000") == "SYNTHETIC •••000"
    assert mask_pii({"phone": "+000000•••000"}) == {"phone": "•••000"}


def test_ambiguous_document_length_is_fully_redacted_in_text() -> None:
    assert mask_pii_text("SYNTHETIC 00000000000000") == "SYNTHETIC [REDACTED]"


def test_urlencoded_phone_in_diagnostics_is_scrubbed() -> None:
    message = "SYNTHETIC phone=%2B000%2000%20000%2000%2000"
    assert mask_pii_text(message) == "SYNTHETIC phone=•••000"
    assert mask_pii_text("SYNTHETIC phone=000+000+000") == "SYNTHETIC phone=•••000"
    assert mask_pii_text("SYNTHETIC phone=000%200000") == "SYNTHETIC phone=•••000"


@pytest.mark.parametrize("label", ["phone", "phone_number", "mobile", "tel", "телефон"])
def test_short_labeled_phone_in_diagnostics_is_scrubbed(label: str) -> None:
    assert mask_pii_text(f"SYNTHETIC {label}=0000000") == f"SYNTHETIC {label}=•••000"


def test_short_labeled_phone_with_quotes_or_parentheses_is_scrubbed() -> None:
    assert mask_pii_text('SYNTHETIC {"phone":"0000000') == 'SYNTHETIC {"phone":"•••000'
    assert mask_pii_text("SYNTHETIC phone=(000) 0000") == "SYNTHETIC phone=•••000"
    assert mask_pii_text("SYNTHETIC phone=000") == "SYNTHETIC phone=***"


@pytest.mark.parametrize("filter_class", [AppLogFilter, CoreLogFilter])
def test_log_message_scrubs_formatted_number_without_special_keywords(
    filter_class,
) -> None:
    record = logging.LogRecord(
        name="synthetic.phone.mask",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="SYNTHETIC contact: +000 00 000 00 00",
        args=(),
        exc_info=None,
    )
    assert filter_class().filter(record) is True
    assert record.getMessage() == "SYNTHETIC contact: •••000"


def test_field_masking_is_idempotent() -> None:
    masked = mask_pii({"phone": "+000 00 000 00 00"})
    assert mask_pii(masked) == masked


def test_nonphone_short_diagnostics_are_unchanged() -> None:
    message = "SYNTHETIC status: 2 retries at 12:34"
    assert mask_pii_text(message) == message
