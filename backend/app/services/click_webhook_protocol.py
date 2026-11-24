"""Pure Click Shop API parsing and signature observation.

Not wired to a route. Verification alone authorizes neither settlement nor a
provider ACK: ``error`` is unsigned, and Click's concatenated signature has
no field delimiters. The caller must bind both phases to durable issuance and
prepare records, persist a receipt, and independently verify provider status.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, replace
from decimal import Decimal
from urllib.parse import parse_qsl

_MAX_BODY = 256 * 1024
_MAX_FIELD = 1024
_MAX_FIELDS = 64
_MAX_AMOUNT_LENGTH = 128
_BAD_PERCENT_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_HEX_DIGEST = re.compile(r"[0-9a-fA-F]{32}\Z")


class ClickProtocolError(ValueError):
    """Malformed or unauthenticated input; does not contain callback data."""


class _JsonNumber(str):
    """Retain source spelling without asserting provider numeric coercion."""


@dataclass(frozen=True, repr=False)
class ClickObservation:
    """Authenticated fields and separately reported, *unsigned* outcome.

    ``amount_minor`` is None when a validly signed amount cannot fit the
    current reconciliation money representation. Keep ``amount_raw`` for a
    durable exception receipt; never round it or silently discard this object.
    """

    transaction_id: str
    service_id: str
    merchant_trans_id: str
    merchant_prepare_id: str | None
    amount_raw: str
    amount_major: Decimal | None
    amount_minor: str | None
    action: int
    sign_time: str
    reported_error: str
    reported_error_note: str


def _no_constant(_: str) -> None:
    raise ClickProtocolError("invalid JSON number")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ClickProtocolError("duplicate field")
        result[name] = value
    return result


def parse_click_fields(body: bytes, content_type: str) -> dict[str, str]:
    """Bounded UTF-8 parser preserving the literal number used in the MAC."""
    if not isinstance(body, bytes) or len(body) > _MAX_BODY:
        raise ClickProtocolError("invalid callback size")
    if not isinstance(content_type, str):
        raise ClickProtocolError("unsupported content type")
    media_type = content_type.split(";", 1)[0].strip().lower()
    try:
        raw = body.decode("utf-8", errors="strict")
        if media_type == "application/json":
            data = json.loads(raw, parse_int=_JsonNumber, parse_float=_JsonNumber,
                              parse_constant=_no_constant, object_pairs_hook=_unique_object)
        elif media_type == "application/x-www-form-urlencoded":
            if _BAD_PERCENT_ESCAPE.search(raw):
                raise ClickProtocolError("invalid form encoding")
            data = _unique_object(parse_qsl(raw, keep_blank_values=True, strict_parsing=True,
                                           encoding="utf-8", errors="strict", max_num_fields=_MAX_FIELDS))
        else:
            raise ClickProtocolError("unsupported content type")
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ClickProtocolError):
            raise
        raise ClickProtocolError("invalid callback") from None
    if not isinstance(data, dict) or len(data) > _MAX_FIELDS:
        raise ClickProtocolError("invalid callback fields")
    if any(not isinstance(k, str) or not k or len(k) > _MAX_FIELD
           or not isinstance(v, str) or len(v) > _MAX_FIELD for k, v in data.items()):
        raise ClickProtocolError("invalid callback field")
    try:
        for key, value in data.items():
            key.encode("utf-8", errors="strict")
            value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ClickProtocolError("invalid callback encoding") from None
    return data


def _amount_parts(raw: str) -> tuple[str, str] | None:
    if len(raw) > _MAX_AMOUNT_LENGTH:
        return None
    whole, dot, fraction = raw.partition(".")
    if not whole.isascii() or not whole.isdecimal() or (len(whole) > 1 and whole.startswith("0")):
        return None
    if dot and not (fraction.isascii() and fraction.isdecimal()):
        return None
    return whole, fraction


def _major_and_minor(raw: str) -> tuple[Decimal | None, str | None]:
    # Protocol signature verification must be possible even if the exact
    # amount cannot be represented by the financial schema. A signed unusual
    # amount must go to an exception receipt, not be rounded or discarded.
    parts = _amount_parts(raw)
    if parts is None:
        return None, None
    whole, fraction = parts
    amount = Decimal(raw)
    if len(fraction.rstrip("0")) > 2:
        return amount, None
    minor = (whole + fraction[:2].ljust(2, "0")).lstrip("0") or "0"
    if len(minor) > _MAX_AMOUNT_LENGTH:
        return amount, None
    return amount, minor


def verify_click_fields(fields: dict[str, str], *, service_id: str, secret_key: str) -> ClickObservation:
    """Verify a callback; numeric JSON coercion and debit outcome remain unknown.

    The caller must retain the original bounded request bytes for durable
    reconciliation when a signed value arrived as a JSON number: PHP's
    number-to-string conversion is not specified by the observed contract.
    """
    if not isinstance(fields, dict) or not isinstance(service_id, str) or not service_id or not isinstance(secret_key, str) or not secret_key:
        raise ClickProtocolError("invalid verification context")
    required = ("click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "error", "error_note", "sign_time", "sign_string", "click_paydoc_id")
    if any(not isinstance(fields.get(name), str) or len(fields[name]) > _MAX_FIELD for name in required):
        raise ClickProtocolError("missing callback field")
    if any(not fields[name] for name in required if name != "error_note"):
        raise ClickProtocolError("missing callback field")
    signed_fields = ("click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time")
    if any(isinstance(fields[name], _JsonNumber) for name in signed_fields):
        raise ClickProtocolError("ambiguous JSON number; retain original callback for reconciliation")
    action_raw = fields["action"]
    if action_raw not in ("0", "1") or fields["service_id"] != service_id:
        raise ClickProtocolError("invalid service or action")
    prepare = fields.get("merchant_prepare_id") if action_raw == "1" else None
    if action_raw == "1" and (not isinstance(prepare, str) or not prepare or len(prepare) > _MAX_FIELD):
        raise ClickProtocolError("missing prepare reference")
    if isinstance(prepare, _JsonNumber):
        raise ClickProtocolError("ambiguous JSON number; retain original callback for reconciliation")
    signature = fields["sign_string"]
    if not _HEX_DIGEST.fullmatch(signature):
        raise ClickProtocolError("invalid signature")
    source = (fields["click_trans_id"] + fields["service_id"] + secret_key
              + fields["merchant_trans_id"] + (prepare or "")
              + fields["amount"] + action_raw + fields["sign_time"])
    try:
        message = source.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ClickProtocolError("invalid callback encoding") from None
    expected = hashlib.md5(message, usedforsecurity=False).hexdigest()
    if not hmac.compare_digest(signature.lower(), expected):
        raise ClickProtocolError("invalid signature")
    major, minor = _major_and_minor(fields["amount"])
    return ClickObservation(
        transaction_id=fields["click_trans_id"], service_id=fields["service_id"],
        merchant_trans_id=fields["merchant_trans_id"], merchant_prepare_id=prepare,
        amount_raw=fields["amount"], amount_major=major, amount_minor=minor,
        action=int(action_raw), sign_time=fields["sign_time"],
        reported_error=fields["error"], reported_error_note=fields["error_note"],
    )


def authenticate_click_receipt(fields: dict[str, str], *, service_id: str, secret_key: str) -> tuple[ClickObservation, str]:
    """Identify a callback worth storing; probable evidence never settles.

    Numeric JSON coercion in the upstream provider is not established. If a
    signature matches a plausible representation, retain the exact original
    bytes under the lesser confidence label. A mismatch has no storage right.
    """
    numeric = any(isinstance(value, _JsonNumber) for value in fields.values())
    if not numeric:
        return verify_click_fields(fields, service_id=service_id, secret_key=secret_key), "authenticated"
    if isinstance(fields.get("sign_string"), _JsonNumber):
        raise ClickProtocolError("invalid signature")
    candidate = {key: str(value) for key, value in fields.items()}

    def probable(result: ClickObservation) -> tuple[ClickObservation, str]:
        raw_amount = str(fields["amount"])
        major, minor = _major_and_minor(raw_amount)
        return replace(result, amount_raw=raw_amount, amount_major=major, amount_minor=minor), "probable"

    try:
        return probable(verify_click_fields(candidate, service_id=service_id, secret_key=secret_key))
    except ClickProtocolError:
        # A common PHP conversion removes decimal trailing zeroes. This is
        # only a candidate for evidence retention, never proof of settlement.
        value = fields.get("amount")
        parts = _amount_parts(value) if isinstance(value, _JsonNumber) else None
        if parts is None:
            raise ClickProtocolError("unverified callback") from None
        whole, fraction = parts
        if not fraction:
            raise ClickProtocolError("unverified callback") from None
        significant_fraction = fraction.rstrip("0")
        candidate["amount"] = f"{whole}.{significant_fraction}" if significant_fraction else whole
        return probable(verify_click_fields(candidate, service_id=service_id, secret_key=secret_key))
