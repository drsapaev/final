"""Synthetic vectors from Click LLC's Shop API field ordering."""
import hashlib
import json
from decimal import Decimal
from urllib.parse import urlencode

import pytest

from app.services.click_webhook_protocol import (
    ClickProtocolError,
    authenticate_click_receipt,
    parse_click_fields,
    verify_click_fields,
)

_SECRET = "SYNTHETIC_SECRET"
_PREPARE = {
    "click_trans_id": "12345", "service_id": "100", "click_paydoc_id": "42",
    "merchant_trans_id": "invoice_1", "amount": "23.45", "action": "0",
    "error": "0", "error_note": "Success", "sign_time": "2026-11-17 12:00:00",
    "sign_string": "72977c105886373b1b7d1f45f858a02b",
}
_COMPLETE = {
    **_PREPARE, "action": "1", "merchant_prepare_id": "77",
    "sign_time": "2026-11-17 12:01:00", "sign_string": "25a20b004ef4db7d83ac6723e4c68bcf",
}


def _verify(fields):
    return verify_click_fields(fields, service_id="100", secret_key=_SECRET)


@pytest.mark.parametrize("data", [_PREPARE, _COMPLETE])
@pytest.mark.parametrize("kind", ["json", "form"])
def test_official_phase_vectors_preserve_exact_amount(data, kind):
    if kind == "json":
        body = json.dumps(data).encode()
        media = "application/json; charset=utf-8"
    else:
        body = urlencode(data).encode()
        media = "application/x-www-form-urlencoded"
    result = _verify(parse_click_fields(body, media))
    assert result.amount_raw == "23.45"
    assert result.amount_major == Decimal("23.45")
    assert result.amount_minor == "2345"
    assert result.action == int(data["action"])
    assert result.merchant_trans_id == "invoice_1"
    assert result.merchant_prepare_id == data.get("merchant_prepare_id")
    assert result.reported_error == "0"  # This is not signed proof of success.
    assert "invoice_1" not in repr(result)


@pytest.mark.parametrize("name,value", [
    ("click_trans_id", "12346"), ("service_id", "101"),
    ("merchant_trans_id", "invoice_2"), ("merchant_prepare_id", "78"),
    ("amount", "23.46"), ("amount", "23.450"), ("sign_time", "2026-11-17 12:02:00"),
    ("action", "0"),
])
def test_signed_field_tampering_rejected(name, value):
    with pytest.raises(ClickProtocolError):
        _verify({**_COMPLETE, name: value})


def test_error_is_an_unsigned_observation_not_payment_evidence():
    data = {**_COMPLETE, "error": "-9", "error_note": "changed"}
    result = _verify(data)
    assert result.reported_error == "-9"
    assert result.amount_minor == "2345"


def test_published_signature_is_ambiguous_without_independent_binding():
    # Same exact concatenation, despite a different order and amount. The
    # durable prepared checkout must decide which pair actually belongs.
    other = {**_PREPARE, "merchant_trans_id": "invoice_12", "amount": "3.45"}
    assert _verify(other).amount_minor == "345"
    assert _verify(_PREPARE).amount_minor == "2345"


@pytest.mark.parametrize("body,media", [
    (b'{"action":0,"action":1}', "application/json"),
    (b'action=0&action=1', "application/x-www-form-urlencoded"),
    (b'action=%ZZ', "application/x-www-form-urlencoded"),
    (b'action=%FF', "application/x-www-form-urlencoded"),
    (b'{"amount":NaN}', "application/json"),
    (b'{"amount":"\\ud800"}', "application/json"),
    (b'{"amount":true}', "application/json"),
    (b'{"amount":null}', "application/json"),
    (b'{"nested":{"x":1}}', "application/json"),
    (b'[]', "application/json"),
    (b'\xff', "application/json"),
    (b'{}', "text/plain"),
    (b'x' * (256 * 1024 + 1), "application/json"),
])
def test_malformed_and_ambiguous_body_rejected(body, media):
    with pytest.raises(ClickProtocolError):
        parse_click_fields(body, media)


def test_json_numeric_token_remains_lexical_for_signature():
    # JSON parsers must not change 23.450 into a binary float 23.45.
    fields = parse_click_fields(b'{"amount":23.450,"action":0}', "application/json")
    assert fields == {"amount": "23.450", "action": "0"}


def test_json_numeric_signed_field_requires_reconciliation():
    raw = json.dumps(_PREPARE).replace('"amount": "23.45"', '"amount": 23.45').encode()
    fields = parse_click_fields(raw, "application/json")
    assert fields["amount"] == "23.45"
    with pytest.raises(ClickProtocolError, match="retain original callback"):
        _verify(fields)


def test_probable_json_retains_original_numeric_spelling():
    raw = json.dumps(_PREPARE).replace('"amount": "23.45"', '"amount": 23.450').encode()
    fields = parse_click_fields(raw, "application/json")
    observation, confidence = authenticate_click_receipt(fields, service_id="100", secret_key=_SECRET)
    assert confidence == "probable"
    assert observation.amount_raw == "23.450"
    assert observation.amount_major == Decimal("23.450")
    assert observation.amount_minor == "2345"


@pytest.mark.parametrize("value,major,minor", [
    ("1.00", Decimal("1.00"), "100"), ("0.29", Decimal("0.29"), "29"),
    ("0.0700", Decimal("0.0700"), "7"), ("0", Decimal("0"), "0"),
    ("1.001", Decimal("1.001"), None), ("1e-1000", None, None),
    ("9" * 128, Decimal("9" * 128), None),
    ("9" * 129, None, None), ("00.10", None, None), ("0.", None, None),
    (".10", None, None), ("0.1.2", None, None), ("２.１", None, None),
    ("2.１", None, None), ("+1", None, None), ("1\n", None, None),
])
def test_signed_unrepresentable_amount_remains_an_observation(value, major, minor):
    # Test parsing separately from authentication; no credential is a real one.
    from app.services.click_webhook_protocol import _major_and_minor

    assert _major_and_minor(value) == (major, minor)


def test_verified_subcent_amount_is_retained_for_reconciliation():
    fields = {**_PREPARE, "amount": "0.001"}
    message = "12345100SYNTHETIC_SECRETinvoice_10.00102026-11-17 12:00:00"
    fields["sign_string"] = hashlib.md5(message.encode(), usedforsecurity=False).hexdigest()
    observation = _verify(fields)
    assert observation.amount_raw == "0.001"
    assert observation.amount_major == Decimal("0.001")
    assert observation.amount_minor is None


def test_missing_prepare_wrong_service_and_old_unbound_signature_rejected():
    with pytest.raises(ClickProtocolError):
        _verify({key: value for key, value in _COMPLETE.items() if key != "merchant_prepare_id"})
    with pytest.raises(ClickProtocolError):
        verify_click_fields(_COMPLETE, service_id="101", secret_key=_SECRET)
    # Pre-fix implementation signed different fields and omitted target.
    old_signature = "c42eb47f6addc0f5d84fb211e8fb8475"
    with pytest.raises(ClickProtocolError):
        _verify({**_COMPLETE, "sign_string": old_signature})
