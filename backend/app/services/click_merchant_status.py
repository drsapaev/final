"""Read-only, bounded Click Merchant observations; not payment authority.

The PHP example uses a conflicting method for status-by-order. This client
uses GET as documented by Click-compatible Merchant API clients; a provider
rejection is unresolved. Returned codes are not mapped to paid. An authorized
reducer must bind the observation to a durable 0111 issuance and prepare,
verify exact amount and all Visit snapshots, and interpret the provider's
contract before changing financial state.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.logging_config import protect_click_transport_logs

_ORIGIN = "https://api.click.uz"
_POSITIVE_ID = re.compile(r"[1-9][0-9]{0,18}\Z")
_ORDER = re.compile(r"(?:invoice|clinic)_[1-9][0-9]{0,9}_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_MAX_RESPONSE = 65536


class ClickMerchantStatusError(ValueError):
    """The status cannot safely be used; contains no provider data."""


@dataclass(frozen=True, repr=False)
class ClickMerchantStatusObservation:
    order_ref: str
    provider_payment_id: str
    status_code: int
    order_response_sha256: str
    status_response_sha256: str
    order_recheck_sha256: str
    # No amount, debit evidence or boolean indicating paid is implied.


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ClickMerchantStatusError("ambiguous provider response")
        result[key] = value
    return result


def _id(value: object) -> str:
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not _POSITIVE_ID.fullmatch(value):
        raise ClickMerchantStatusError("provider response unavailable")
    return value


class ClickMerchantStatus:
    """Explicit credentials and test-only MockTransport; no dynamic origin."""

    def __init__(self, *, service_id: str, merchant_user_id: str, secret_key: str,
                 transport: httpx.MockTransport | None = None):
        self._service_id = _id(service_id)
        self._merchant_user_id = _id(merchant_user_id)
        if not isinstance(secret_key, str) or not secret_key or len(secret_key) > 2048 or any(c in secret_key for c in "\r\n\x00"):
            raise ClickMerchantStatusError("merchant credentials unavailable")
        try:
            secret_key.encode("utf-8", errors="strict")
        except UnicodeError:
            raise ClickMerchantStatusError("merchant credentials unavailable") from None
        if transport is not None and not isinstance(transport, httpx.MockTransport):
            raise ClickMerchantStatusError("unsupported test transport")
        self._secret_key = secret_key
        self._transport = transport

    def _get(self, client: httpx.Client, path: str) -> tuple[dict[str, Any], str]:
        try:
            timestamp = str(int(time.time()))
        except (OverflowError, ValueError):
            raise ClickMerchantStatusError("merchant clock unavailable") from None
        if not re.fullmatch(r"[0-9]{10}", timestamp):
            raise ClickMerchantStatusError("merchant clock unavailable")
        digest = hashlib.sha1((timestamp + self._secret_key).encode(), usedforsecurity=False).hexdigest()
        headers = {"Auth": f"{self._merchant_user_id}:{digest}:{timestamp}",
                   "Accept": "application/json", "Accept-Encoding": "identity"}
        try:
            with client.stream("GET", _ORIGIN + path, headers=headers) as response:
                if response.status_code != 200 or response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ClickMerchantStatusError("merchant status unavailable")
                content_length = response.headers.get("content-length")
                if content_length is not None and (not content_length.isascii() or not content_length.isdigit() or len(content_length) > 6
                                                   or int(content_length) > _MAX_RESPONSE):
                    raise ClickMerchantStatusError("merchant response unavailable")
                parts: list[bytes] = []
                size = 0
                for chunk in response.iter_raw():
                    size += len(chunk)
                    if size > _MAX_RESPONSE:
                        raise ClickMerchantStatusError("merchant response unavailable")
                    parts.append(chunk)
        except httpx.HTTPError:
            raise ClickMerchantStatusError("merchant status unavailable") from None
        raw = b"".join(parts)
        try:
            payload = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_pairs,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError, RecursionError):
            raise ClickMerchantStatusError("merchant response unavailable") from None
        if not isinstance(payload, dict):
            raise ClickMerchantStatusError("merchant response unavailable")
        return payload, hashlib.sha256(raw).hexdigest()

    def lookup(self, order_ref: str) -> ClickMerchantStatusObservation:
        """Observe one uniquely-issued order; caller supplies locked provenance."""
        if not isinstance(order_ref, str) or not _ORDER.fullmatch(order_ref):
            raise ClickMerchantStatusError("issued order unavailable")
        try:
            with protect_click_transport_logs(), httpx.Client(transport=self._transport, verify=True, trust_env=False,
                              follow_redirects=False, timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                by_order, order_digest = self._get(
                    client, f"/v2/merchant/payment/status_by_mti/{self._service_id}/{order_ref}")
                if type(by_order.get("error_code")) is not int or by_order["error_code"] != 0 or by_order.get("merchant_trans_id") != order_ref:
                    raise ClickMerchantStatusError("merchant order mismatch")
                provider_payment_id = _id(by_order.get("payment_id"))
                by_payment, status_digest = self._get(
                    client, f"/v2/merchant/payment/status/{self._service_id}/{provider_payment_id}")
                if type(by_payment.get("error_code")) is not int or by_payment["error_code"] != 0 or _id(by_payment.get("payment_id")) != provider_payment_id:
                    raise ClickMerchantStatusError("merchant payment mismatch")
                present = [by_payment[key] for key in ("status", "payment_status") if key in by_payment]
                if not present or any(type(value) is not int for value in present) or len(set(present)) != 1:
                    raise ClickMerchantStatusError("merchant outcome unavailable")
                if "merchant_trans_id" in by_payment and by_payment["merchant_trans_id"] != order_ref:
                    raise ClickMerchantStatusError("merchant payment mismatch")
                rechecked, recheck_digest = self._get(
                    client, f"/v2/merchant/payment/status_by_mti/{self._service_id}/{order_ref}")
                if (type(rechecked.get("error_code")) is not int or rechecked["error_code"] != 0
                    or rechecked.get("merchant_trans_id") != order_ref
                    or _id(rechecked.get("payment_id")) != provider_payment_id):
                    raise ClickMerchantStatusError("merchant order changed")
                return ClickMerchantStatusObservation(order_ref=order_ref, provider_payment_id=provider_payment_id,
                    status_code=present[0], order_response_sha256=order_digest, status_response_sha256=status_digest,
                    order_recheck_sha256=recheck_digest)
        except httpx.HTTPError:
            raise ClickMerchantStatusError("merchant status unavailable") from None
