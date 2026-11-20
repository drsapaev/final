"""Verify the committed registration before returning an idempotent cart response."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.all_free_request import AllFreeRequest
from app.models.encounter import Encounter
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit
from app.services.encounter_financial_fence import (
    _financial_schema,
    _lock_full_financial_closure,
    _verify_complete_backend_reads,
)
from app.services.money_input import MoneyInputError, parse_exact_json, parse_money
from app.services.patient_subject_lock import lock_patient_subject


@dataclass(frozen=True)
class RegistrarCartReceipt:
    invoice_id: int
    total_amount: Decimal
    visit_states: tuple[tuple[int, str, str], ...]


def _is_record_id(value: object) -> bool:
    return type(value) is int and 0 < value <= 2147483647


def parse_registrar_cart_receipt(body: bytes) -> RegistrarCartReceipt | None:
    try:
        receipt = parse_exact_json(body)
        if not isinstance(receipt, dict) or receipt.get("success") is not True:
            return None
        invoice_id, visit_ids = receipt.get("invoice_id"), receipt.get("visit_ids")
        details = receipt.get("created_visits")
        if (
            not _is_record_id(invoice_id)
            or not isinstance(visit_ids, list) or not 1 <= len(visit_ids) <= 1000
            or not all(_is_record_id(visit_id) for visit_id in visit_ids)
            or len(set(visit_ids)) != len(visit_ids)
            or not isinstance(details, list) or len(details) != len(visit_ids)
            or receipt.get("print_tickets") != []
        ):
            return None
        states = []
        for visit_id, detail in zip(visit_ids, details, strict=True):
            if (
                not isinstance(detail, dict) or not _is_record_id(detail.get("visit_id"))
                or detail["visit_id"] != visit_id
                or detail.get("confirmation_required") is not False
                or detail.get("confirmation_token") is not None
                or not isinstance(detail.get("status"), str)
                or not isinstance(detail.get("approval_status"), str)
            ):
                return None
            states.append((visit_id, detail["status"], detail["approval_status"]))
        return RegistrarCartReceipt(invoice_id, parse_money(receipt.get("total_amount")), tuple(sorted(states)))
    except MoneyInputError:
        return None


def registrar_cart_receipt_is_current(db: Session, *, actor_id: int, receipt: RegistrarCartReceipt) -> bool:
    """Validate under the actor, patient, and financial row locks in that order."""
    dialect = db.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        return False
    schema = _financial_schema(db) if dialect == "postgresql" else None
    if schema is not None:
        _verify_complete_backend_reads(db, schema)
    patient_id = db.query(PaymentInvoice.patient_id).filter(PaymentInvoice.id == receipt.invoice_id).scalar()
    if not _is_record_id(patient_id) or not lock_patient_subject(db, patient_id):
        return False

    expected_ids = [visit_id for visit_id, _, _ in receipt.visit_states]
    visit_ids, groups, invoices, links = _lock_full_financial_closure(db, set(expected_ids), schema)
    if (
        visit_ids != expected_ids or len(groups) != 1 or invoices != [receipt.invoice_id]
        or sorted(visit_id for _, _, visit_id in links) != expected_ids
    ):
        return False
    encounter = db.query(Encounter.patient_id, Encounter.generation, Encounter.provenance).filter(
        Encounter.id == groups[0]
    ).one_or_none()
    invoice = db.query(
        PaymentInvoice.patient_id, PaymentInvoice.registrar_encounter_id_snapshot,
        PaymentInvoice.registrar_encounter_generation_snapshot, PaymentInvoice.total_amount,
    ).filter(PaymentInvoice.id == receipt.invoice_id).one_or_none()
    if (
        encounter is None or encounter.patient_id != patient_id or encounter.provenance != "new"
        or invoice is None or invoice.patient_id != patient_id
        or invoice.registrar_encounter_id_snapshot != groups[0]
        or invoice.registrar_encounter_generation_snapshot != encounter.generation
        or invoice.total_amount != receipt.total_amount
    ):
        return False

    allocations = db.query(PaymentInvoiceVisit.visit_amount).filter(
        PaymentInvoiceVisit.invoice_id == receipt.invoice_id
    ).all()
    if sum((parse_money(amount) for (amount,) in allocations), Decimal(0)) != receipt.total_amount:
        return False

    visits = db.query(
        Visit.id, Visit.patient_id, Visit.encounter_id, Visit.status, Visit.approval_status,
        Visit.confirmed_by, Visit.discount_mode, Visit.confirmation_context_epoch,
    ).filter(Visit.id.in_(visit_ids)).order_by(Visit.id).all()
    if tuple((visit.id, visit.status, visit.approval_status) for visit in visits) != receipt.visit_states:
        return False
    for visit in visits:
        if visit.patient_id != patient_id or visit.encounter_id != groups[0]:
            return False
        if visit.discount_mode != "all_free" or visit.approval_status != "pending":
            if visit.confirmed_by != f"registrar_{actor_id}":
                return False
            continue
        application = db.query(AllFreeRequest.id).filter(
            AllFreeRequest.visit_id == visit.id,
            AllFreeRequest.patient_id == patient_id,
            AllFreeRequest.encounter_id == groups[0],
            AllFreeRequest.encounter_generation == encounter.generation,
            AllFreeRequest.visit_context_epoch == visit.confirmation_context_epoch,
            AllFreeRequest.requested_by_user_id == actor_id,
            AllFreeRequest.status == "pending",
        ).first()
        if application is None:
            return False
    return True
