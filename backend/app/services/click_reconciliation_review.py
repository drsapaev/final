"""Evidence helpers for an audited Click review; never changes payment state.

A trusted administrator must independently check an authentic provider
statement or portal document. A digest or a callback's unsigned `error` field
alone is not evidence of a debit outcome. The public workflow and the guarded
resolution consumer are not yet wired to these helpers.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from app.services.click_receipt_service import ClickReceiptError, receipt_key_commitment

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}\Z")
_DOMAIN = b"click-review-evidence-aes-siv-v1"


class ClickReviewError(ValueError):
    """A review is unavailable; no payment state or evidence was changed."""


@dataclass(frozen=True, repr=False)
class ReviewContext:
    actor_id: int
    actor_epoch: int
    session_digest: str
    receipt_id: int
    receipt_sha256: str
    event_id: int
    event_snapshot_sha256: str
    target_context_sha256: str
    issued_attempt_id: int
    prepare_id: int
    proof_sha256: str
    source_kind: str
    result: str
    reason_code: str
    expires_at: int


def _valid_context(context: ReviewContext) -> None:
    integers = (context.actor_id, context.receipt_id, context.event_id, context.issued_attempt_id, context.prepare_id)
    if (any(type(value) is not int or not 0 < value <= 2_147_483_647 for value in integers)
            or type(context.actor_epoch) is not int or not 0 <= context.actor_epoch <= 9_223_372_036_854_775_807
            or type(context.expires_at) is not int or not 0 < context.expires_at <= 9_223_372_036_854_775_807
            or any(not isinstance(value, str) or not _HEX.fullmatch(value)
                   for value in (context.session_digest, context.receipt_sha256, context.event_snapshot_sha256,
                                 context.target_context_sha256, context.proof_sha256))
            or context.source_kind not in {"provider_portal", "official_document"}
            or (context.result, context.reason_code) not in {
                ("no_debit", "provider_cancelled"), ("no_debit", "provider_failed"),
                ("debit_confirmed", "provider_confirmed_debit")
            }):
        raise ClickReviewError("review unavailable")


def proof_digest(proof: bytes) -> str:
    """Hash a bounded PDF; authenticity requires an administrator's review."""
    if (not isinstance(proof, bytes) or not 10 <= len(proof) <= 262_144
            or not proof.startswith(b"%PDF-") or not proof.rstrip().endswith(b"%%EOF")):
        raise ClickReviewError("provider document unavailable")
    return hashlib.sha256(proof).hexdigest()


def _aad(context: ReviewContext, key_version: str) -> list[bytes]:
    _valid_context(context)
    if not isinstance(key_version, str) or not _VERSION.fullmatch(key_version):
        raise ClickReviewError("review key unavailable")
    values = (str(context.actor_id), str(context.receipt_id), str(context.event_id),
              str(context.issued_attempt_id), str(context.prepare_id), context.receipt_sha256,
              context.event_snapshot_sha256, context.target_context_sha256, context.proof_sha256, context.source_kind, context.result, context.reason_code, key_version)
    return [_DOMAIN, *(value.encode() for value in values)]


def encrypt_proof(proof: bytes, *, context: ReviewContext, key_version: str, key: bytes) -> bytes:
    if not hmac.compare_digest(proof_digest(proof), context.proof_sha256):
        raise ClickReviewError("provider document unavailable")
    try:
        receipt_key_commitment(key)
        return AESSIV(key).encrypt(proof, _aad(context, key_version))
    except (ClickReceiptError, ValueError):
        raise ClickReviewError("review key unavailable") from None


def decrypt_proof(ciphertext: bytes, *, context: ReviewContext, key_version: str, key: bytes) -> bytes:
    try:
        receipt_key_commitment(key)
        proof = AESSIV(key).decrypt(ciphertext, _aad(context, key_version))
        if not hmac.compare_digest(proof_digest(proof), context.proof_sha256):
            raise ClickReviewError("review proof unavailable")
        return proof
    except (ClickReceiptError, InvalidTag, TypeError, ValueError):
        raise ClickReviewError("review proof unavailable") from None


def session_digest(jti: str | None, actor_id: int, actor_epoch: int) -> str:
    if not isinstance(jti, str) or not jti or len(jti) > 1024:
        raise ClickReviewError("review session unavailable")
    raw = json.dumps(["click-review-session-v1", actor_id, actor_epoch, jti], separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def review_token(context: ReviewContext, secret: str) -> str:
    _valid_context(context)
    if not isinstance(secret, str) or not secret:
        raise ClickReviewError("review signing unavailable")
    values = ["click-review-v1", context.actor_id, context.actor_epoch, context.session_digest,
              context.receipt_id, context.receipt_sha256, context.event_id, context.event_snapshot_sha256,
              context.target_context_sha256, context.issued_attempt_id,
              context.prepare_id, context.proof_sha256, context.source_kind, context.result,
              context.reason_code, context.expires_at]
    key = hmac.new(secret.encode(), b"click-review-signing-v1", hashlib.sha256).digest()
    return hmac.new(key, json.dumps(values, separators=(",", ":"), ensure_ascii=True).encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True, repr=False)
class ReviewGraph:
    """A database-loaded snapshot; caller must lock and re-read all members."""
    receipt_id: int
    receipt_phase: str
    receipt_confidence: str
    receipt_event_key: str
    raw_receipt_sha256: str
    event_id: int
    event_provider: str
    event_source: str
    event_phase: str
    event_status: str
    event_key: str
    event_raw_sha256: str
    event_reference_sha256: str
    event_transaction_id: str
    event_target_kind: str
    event_live_target_id: int | None
    event_target_id_snapshot: int
    event_amount_minor: str
    event_currency: str
    link_receipt_id: int
    link_event_id: int
    issued_id: int
    issued_attempt_id: int
    issued_order: str
    issued_merchant_hash: str
    issued_amount_minor: str
    issued_currency: str
    prepare_id: int
    prepare_receipt_id: int
    prepare_bound_receipt_id: int
    prepare_receipt_confidence: str
    prepare_receipt_action: int
    prepare_receipt_transaction_id: str
    prepare_receipt_service_id: str
    prepare_receipt_order: str
    prepare_receipt_amount_minor: str | None
    prepare_attempt_id: int
    prepare_transaction_id: str
    prepare_service_id: str
    prepare_order: str
    prepare_merchant_hash: str
    prepare_amount_minor: str
    complete_transaction_id: str
    complete_service_id: str
    complete_order: str
    complete_prepare_ref: str
    complete_amount_minor: str | None
    attempt_id: int
    attempt_public_id: str
    attempt_status: str
    attempt_target_kind: str
    attempt_live_target_id: int | None
    attempt_target_id_snapshot: int
    confirmed_merchant_id: str


def provider_reference_digest(service_id: str, transaction_id: str, order_ref: str, prepare_id: str) -> str:
    fields = (service_id, transaction_id, order_ref, prepare_id)
    if any(not isinstance(value, str) or not value or len(value) > 1024 for value in fields):
        raise ClickReviewError("provider reference unavailable")
    value = json.dumps(["click-provider-reference-v1", *fields], separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(value).hexdigest()


def verify_review_graph(graph: ReviewGraph) -> None:
    """Require a proved issued attempt and exact phase-bound receipt binding.

    Independent human verification of the attached provider document remains
    mandatory; this function does not establish a no-debit or debit outcome.
    """
    from app.services.click_webhook_reducer import _MINOR, _ORDER

    if (not all(type(value) is int and 0 < value <= 2_147_483_647 for value in (
            graph.receipt_id, graph.event_id, graph.issued_id, graph.issued_attempt_id,
            graph.prepare_id, graph.prepare_receipt_id, graph.prepare_bound_receipt_id,
            graph.attempt_id, graph.event_target_id_snapshot, graph.attempt_target_id_snapshot))
            or graph.receipt_phase != "complete" or graph.receipt_confidence != "authenticated"
            or graph.event_provider != "click" or graph.event_source != "webhook" or graph.event_phase != "complete"
            or graph.event_status != "needs_review" or graph.attempt_status not in {"dispatching", "unknown"}
            or graph.event_target_kind not in {"payment", "payment_invoice"}
            or graph.event_target_kind != graph.attempt_target_kind
            or type(graph.event_live_target_id) is not int or graph.event_live_target_id != graph.event_target_id_snapshot
            or type(graph.attempt_live_target_id) is not int or graph.attempt_live_target_id != graph.attempt_target_id_snapshot
            or graph.event_target_id_snapshot != graph.attempt_target_id_snapshot
            or graph.link_receipt_id != graph.receipt_id or graph.link_event_id != graph.event_id
            or graph.issued_attempt_id != graph.prepare_attempt_id or graph.attempt_id != graph.issued_attempt_id
            or graph.prepare_receipt_id != graph.prepare_bound_receipt_id or graph.prepare_receipt_confidence != "authenticated"
            or graph.prepare_receipt_action != 0 or graph.prepare_receipt_transaction_id != graph.prepare_transaction_id
            or graph.prepare_receipt_service_id != graph.prepare_service_id or graph.prepare_receipt_order != graph.prepare_order
            or graph.prepare_receipt_amount_minor != graph.prepare_amount_minor
            or not isinstance(graph.issued_order, str) or not _ORDER.fullmatch(graph.issued_order)
            or not isinstance(graph.attempt_public_id, str)
            or graph.issued_order != f"{'clinic' if graph.attempt_target_kind == 'payment' else 'invoice'}_{graph.attempt_target_id_snapshot}_{graph.attempt_public_id}"
            or graph.issued_order != graph.prepare_order or graph.issued_order != graph.complete_order
            or graph.prepare_transaction_id != graph.complete_transaction_id
            or graph.event_transaction_id != graph.complete_transaction_id
            or graph.prepare_service_id != graph.complete_service_id
            or graph.complete_prepare_ref != str(graph.prepare_id)
            or not isinstance(graph.issued_amount_minor, str) or not _MINOR.fullmatch(graph.issued_amount_minor)
            or graph.issued_amount_minor == "0" or graph.issued_amount_minor != graph.prepare_amount_minor
            or graph.issued_amount_minor != graph.event_amount_minor or graph.issued_amount_minor != graph.complete_amount_minor
            or graph.issued_currency != "UZS" or graph.event_currency != "UZS"
            or not isinstance(graph.raw_receipt_sha256, str) or not _HEX.fullmatch(graph.raw_receipt_sha256)
            or not isinstance(graph.event_raw_sha256, str) or not _HEX.fullmatch(graph.event_raw_sha256)
            or not hmac.compare_digest(graph.raw_receipt_sha256, graph.event_raw_sha256)
            or not isinstance(graph.receipt_event_key, str) or not _HEX.fullmatch(graph.receipt_event_key)
            or not isinstance(graph.event_key, str) or not _HEX.fullmatch(graph.event_key)
            or not hmac.compare_digest(graph.receipt_event_key, graph.event_key)
            or not isinstance(graph.issued_merchant_hash, str) or not _HEX.fullmatch(graph.issued_merchant_hash)
            or not isinstance(graph.prepare_merchant_hash, str) or not _HEX.fullmatch(graph.prepare_merchant_hash)
            or not hmac.compare_digest(graph.issued_merchant_hash, graph.prepare_merchant_hash)
            or not isinstance(graph.confirmed_merchant_id, str) or not graph.confirmed_merchant_id
            or len(graph.confirmed_merchant_id) > 512):
        raise ClickReviewError("provider evidence does not match issuance")
    merchant = json.dumps(["click", graph.confirmed_merchant_id, graph.complete_service_id],
                          sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    actual_merchant_hash = hashlib.sha256(merchant).hexdigest()
    reference = provider_reference_digest(graph.complete_service_id, graph.complete_transaction_id,
                                           graph.complete_order, graph.complete_prepare_ref)
    if (not hmac.compare_digest(graph.issued_merchant_hash, actual_merchant_hash)
            or not isinstance(graph.event_reference_sha256, str) or not _HEX.fullmatch(graph.event_reference_sha256)
            or not hmac.compare_digest(graph.event_reference_sha256, reference)):
        raise ClickReviewError("provider evidence does not match issuance")
