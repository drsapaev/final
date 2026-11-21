"""Pure checks shared by future Click issuance and webhook reduction.

No database access, provider ACK or payment transition is performed here.
Callers must independently lock and re-read the complete financial context.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from app.services.click_webhook_protocol import ClickObservation

_MINOR = re.compile(r"(?:0|[1-9][0-9]{0,127})\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ORDER = re.compile(r"(?:invoice|clinic)_[1-9][0-9]{0,9}_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")


class ClickReductionError(ValueError):
    """An issued attempt or authenticated callback cannot safely be bound."""


@dataclass(frozen=True)
class AttemptAllocation:
    attempt_visit_id: int
    visit_id: int
    patient_id: int
    context_epoch: int
    amount_minor: str


@dataclass(frozen=True)
class InvoiceAllocation:
    link_id: int
    visit_id: int
    amount_minor: str


def _positive(value: object) -> bool:
    return type(value) is int and 0 < value <= 2_147_483_647


def _minor(value: object) -> bool:
    return isinstance(value, str) and _MINOR.fullmatch(value) is not None


def allocation_digest(allocations: list[AttemptAllocation], links: list[InvoiceAllocation]) -> str:
    """Digest exact, sorted per-visit and invoice-link snapshots including zero.

    Callers must lock the complete Visit/Encounter/Invoice closure before
    constructing these records, then re-read and compare live identities and
    financial values. The digest alone is not an ownership or RLS proof.
    """
    if not allocations or len(allocations) > 1000 or len(links) > 10000:
        raise ClickReductionError("allocation unavailable")
    if any(not all(_positive(x) for x in (a.attempt_visit_id, a.visit_id, a.patient_id))
           or type(a.context_epoch) is not int or not 0 < a.context_epoch <= 9_223_372_036_854_775_807
           or not _minor(a.amount_minor) for a in allocations):
        raise ClickReductionError("allocation unavailable")
    if any(not _positive(item.link_id) or not _positive(item.visit_id) or not _minor(item.amount_minor) for item in links):
        raise ClickReductionError("allocation unavailable")
    if (len({a.attempt_visit_id for a in allocations}) != len(allocations)
            or len({a.visit_id for a in allocations}) != len(allocations)
            or len({item.link_id for item in links}) != len(links)):
        raise ClickReductionError("allocation unavailable")
    by_visit = {a.visit_id: int(a.amount_minor) for a in allocations}
    linked = dict.fromkeys(by_visit, 0)
    for link in links:
        if link.visit_id not in linked:
            raise ClickReductionError("allocation unavailable")
        linked[link.visit_id] += int(link.amount_minor)
    if links and linked != by_visit:
        raise ClickReductionError("allocation unavailable")
    payload = ["click-allocation-v1",
               sorted([[a.attempt_visit_id, a.visit_id, a.patient_id, a.context_epoch, a.amount_minor] for a in allocations]),
               sorted([[link.link_id, link.visit_id, link.amount_minor] for link in links])]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def verify_prepare_binding(*, observation: ClickObservation, confidence: str, issued_order: str,
                           service_id: str, expected_minor: str, expected_merchant_hash: str,
                           actual_merchant_hash: str, expected_allocation_digest: str,
                           allocations: list[AttemptAllocation], links: list[InvoiceAllocation]) -> None:
    """Check signed Prepare against an already locked, server-issued snapshot."""
    if (confidence != "authenticated" or observation.action != 0 or observation.reported_error != "0"
            or not isinstance(issued_order, str) or not _ORDER.fullmatch(issued_order)
            or observation.merchant_trans_id != issued_order or observation.service_id != service_id
            or not _minor(expected_minor) or expected_minor == "0" or observation.amount_minor != expected_minor
            or not isinstance(expected_merchant_hash, str) or not _HASH.fullmatch(expected_merchant_hash)
            or not isinstance(actual_merchant_hash, str) or not _HASH.fullmatch(actual_merchant_hash)
            or not hmac.compare_digest(expected_merchant_hash, actual_merchant_hash)
            or not isinstance(expected_allocation_digest, str) or not _HASH.fullmatch(expected_allocation_digest)):
        raise ClickReductionError("prepare unavailable")
    calculated = allocation_digest(allocations, links)
    if (not hmac.compare_digest(calculated, expected_allocation_digest)
            or sum(int(a.amount_minor) for a in allocations) != int(expected_minor)):
        raise ClickReductionError("prepare unavailable")
