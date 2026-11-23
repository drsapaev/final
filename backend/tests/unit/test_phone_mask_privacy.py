"""Synthetic regressions for phone redaction in fields and diagnostics."""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path

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
    "field",
    [
        "patient_phone",
        "contact_phone",
        "contactPhone",
        "doctor_phone",
        "recovery_phone",
        "emergency_phone",
        "company_phone",
        "new_phone",
        "phoneNumber",
        "phone_masked",
        "phone_e164",
        "mobile",
        "mobileNumber",
        "maskedPhone",
    ],
)
def test_existing_phone_field_aliases_fail_closed(field: str) -> None:
    data = {field: "0000000"}
    expected = {field: "•••000"}
    assert mask_pii(data) == expected
    assert json.loads(mask_pii(json.dumps(data))) == expected
    assert mask_pii({field: "00"}) == {field: "***"}
    assert mask_pii({field: 0}) == {field: "[REDACTED]"}
    assert mask_pii(expected) == expected


def test_nonphone_fields_are_not_classified_as_phone_aliases() -> None:
    data = {"phone_verified": True, "microphone": False}
    assert mask_pii(data) == data


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


def test_canonical_idempotency_log_preserves_only_its_hmac_fingerprint() -> None:
    fingerprint = "000000000abcdefa"
    record = logging.LogRecord(
        name="app.middleware.idempotency_middleware",
        level=logging.INFO,
        pathname="/synthetic/app/middleware/idempotency_middleware.py",
        lineno=1,
        msg="user=%s key_fingerprint=%s phone=%s",
        args=("synthetic", fingerprint, "000000000"),
        exc_info=None,
        func="dispatch",
    )
    assert AppLogFilter().filter(record) is True
    assert (
        record.getMessage()
        == f"user=synthetic key_fingerprint={fingerprint} phone=•••000"
    )


@pytest.mark.parametrize(
    ("name", "pathname", "func", "message"),
    [
        (
            "other.logger",
            "/synthetic/app/middleware/idempotency_middleware.py",
            "dispatch",
            "key_fingerprint=%s",
        ),
        (
            "app.middleware.idempotency_middleware",
            "/synthetic/other.py",
            "dispatch",
            "key_fingerprint=%s",
        ),
        (
            "app.middleware.idempotency_middleware",
            "/synthetic/app/middleware/idempotency_middleware.py",
            "other",
            "key_fingerprint=%s",
        ),
        (
            "app.middleware.idempotency_middleware",
            "/synthetic/app/middleware/idempotency_middleware.py",
            "dispatch",
            "key_fingerprint=%r",
        ),
    ],
)
def test_untrusted_fingerprint_looking_log_values_are_still_masked(
    name: str, pathname: str, func: str, message: str
) -> None:
    record = logging.LogRecord(
        name, logging.INFO, pathname, 1, message, ("000000000abcdefa",), None, func
    )
    assert AppLogFilter().filter(record) is True
    assert "000000000" not in record.getMessage()


def test_idempotency_fingerprint_log_arguments_are_server_generated() -> None:
    source = Path(__file__).parents[2] / "app/middleware/idempotency_middleware.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    dispatch = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "dispatch"
    )
    stores = [
        node
        for node in ast.walk(dispatch)
        if isinstance(node, ast.Name)
        and node.id == "key_fingerprint"
        and isinstance(node.ctx, ast.Store)
    ]
    assignments = [
        node
        for node in ast.walk(dispatch)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "key_fingerprint"
            for target in node.targets
        )
    ]
    assert len(stores) == len(assignments) == 1
    producer = assignments[0].value
    assert isinstance(producer, ast.Call)
    assert isinstance(producer.func, ast.Name)
    assert producer.func.id == "_idempotency_key_log_fingerprint"
    assert len(producer.args) == 1
    assert (
        isinstance(producer.args[0], ast.Name)
        and producer.args[0].id == "idempotency_key"
    )

    log_calls = [
        node
        for node in ast.walk(dispatch)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
    ]
    assert log_calls
    fingerprint_calls = 0
    for call in log_calls:
        assert call.args and isinstance(call.args[0], ast.Constant)
        template = call.args[0].value
        assert isinstance(template, str)
        if "key_fingerprint=%s" not in template:
            continue
        fingerprint_calls += 1
        prefix = template.split("key_fingerprint=%s", 1)[0]
        placeholders = re.findall(r"%%|%s", prefix)
        assert "%" not in re.sub(r"%%|%s", "", prefix)
        index = sum(item == "%s" for item in placeholders)
        assert len(call.args) > index + 1
        argument = call.args[index + 1]
        assert isinstance(argument, ast.Name) and argument.id == "key_fingerprint"
    assert fingerprint_calls
