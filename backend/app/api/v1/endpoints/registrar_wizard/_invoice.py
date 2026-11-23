from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import load_only, selectinload

from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa
from app.api.v1.endpoints.registrar_wizard._helpers import (
    _build_repeat_eligibility_preview_item,
    _load_registration_discount_settings,
)  # noqa: F401
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.payment import Payment
from app.services.all_free_approval import (
    all_free_decision_required_clause,
    awaits_all_free_decision,
)
from app.services.money_input import MoneyInputError, parse_money
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.payment_invoice_service import PaymentInvoiceService
from app.services.payment_providers.base import PaymentResult
from app.services.queue_status import (
    POSITION_VISIBLE_RAW_STATUSES,
    normalize_queue_status,
)
from app.services.visit_lifecycle_service import VisitLifecycleService

_FINAL_INVOICE_STATES = frozenset({"paid", "failed", "cancelled"})
_CLICK_FINAL_STATUS = {"completed": 2, "failed": -1, "cancelled": -2}
_INVOICE_RECONCILIATION_REQUIRED = "Результат оплаты требует сверки с провайдером"


def _read_invoice_links(db: Session, invoice_id: int) -> list[PaymentInvoiceVisit]:
    return (
        db.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.invoice_id == invoice_id)
        .order_by(PaymentInvoiceVisit.visit_id, PaymentInvoiceVisit.id)
        .populate_existing()
        .all()
    )


def _lock_invoice_settlement_context(
    db: Session,
    invoice_id: int,
    *,
    starting_payment: bool = False,
) -> tuple[PaymentInvoice, list[Visit], list[PaymentInvoiceVisit]]:
    """Use the shared lock order, then reread all links, including zero rows."""
    invoice_exists = (
        db.query(PaymentInvoice.id)
        .filter(PaymentInvoice.id == invoice_id)
        .first()
    )
    if invoice_exists is None:
        raise HTTPException(status_code=404, detail="Invoice не найден")

    initial_visit_ids = sorted(
        {
            int(row[0])
            for row in (
                db.query(PaymentInvoiceVisit.visit_id)
                .filter(PaymentInvoiceVisit.invoice_id == invoice_id)
                .all()
            )
        }
    )
    if not initial_visit_ids:
        raise HTTPException(
            status_code=409,
            detail="Счёт не связан с оплачиваемыми визитами",
        )

    invariant = PaymentInvariantService(db)
    if starting_payment:
        invariant.preflight_new_payment(initial_visit_ids)
    else:
        invariant.preflight_payment_groups(initial_visit_ids)

    invoice = (
        db.query(PaymentInvoice)
        .filter(PaymentInvoice.id == invoice_id)
        .populate_existing()
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice не найден")

    invoice_visits = _read_invoice_links(db, invoice_id)
    locked_visit_ids = sorted({int(link.visit_id) for link in invoice_visits})
    # The loss or addition of a link during the preflight changes the target.
    visits = (
        db.query(Visit)
        .options(selectinload(Visit.services))
        .filter(Visit.id.in_(initial_visit_ids))
        .order_by(Visit.id)
        .populate_existing()
        .all()
    )
    if (
        locked_visit_ids != initial_visit_ids
        or len(visits) != len(initial_visit_ids)
        or any(visit.patient_id != invoice.patient_id for visit in visits)
    ):
        raise HTTPException(
            status_code=409,
            detail="Состав счёта изменился. Обновите список счетов.",
        )
    if starting_payment:
        invariant.assert_all_free_decided(visits)
    try:
        linked_amount = sum((parse_money(link.visit_amount) for link in invoice_visits), Decimal("0"))
        invoice_total = parse_money(invoice.total_amount)
    except MoneyInputError as exc:
        raise HTTPException(status_code=409, detail="Распределение суммы счёта требует сверки") from exc
    if linked_amount != invoice_total:
        raise HTTPException(
            status_code=409,
            detail=(
                "Распределение суммы счёта изменилось. "
                "Обновите список счетов перед оплатой."
            ),
        )
    if linked_amount <= 0:
        raise HTTPException(status_code=409, detail="Счёт не связан с оплачиваемыми визитами")
    if invoice.status == "pending":
        allocation_by_visit = {visit.id: Decimal("0.00") for visit in visits}
        for link in invoice_visits:
            allocation_by_visit[link.visit_id] += Decimal(str(link.visit_amount))
        for visit in visits:
            # Equal-and-opposite changes to two visits can preserve the total
            # while leaving the allocation stale before provider checkout.
            outstanding = max(invariant.compute_total_cost(visit) - invariant.compute_paid_amount(visit.id), Decimal("0.00"))
            if allocation_by_visit[visit.id] != outstanding:
                raise HTTPException(
                    status_code=409,
                    detail="Распределение счёта по визитам изменилось. Обновите список счетов перед оплатой.",
                )
    return invoice, visits, invoice_visits


@router.post("/registrar/invoice/init-payment", response_model=InvoicePaymentResponse)
def init_invoice_payment(
    payment_req: InvoicePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Инициация оплаты для invoice через Click/PayMe
    """
    try:
        invoice, visits, invoice_visits = _lock_invoice_settlement_context(
            db,
            payment_req.invoice_id,
            starting_payment=True,
        )

        if invoice.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Invoice уже обработан: {invoice.status}"
            )

        # Инициализируем провайдер платежей
        provider_name = payment_req.provider.lower()
        payment_manager = get_payment_manager()
        if not payment_manager.supports_registrar_invoice_payment(provider_name):
            db.rollback()
            return InvoicePaymentResponse(
                success=False,
                error_message=f"Провайдер {payment_req.provider} не поддерживается",
            )

        invariant_service = PaymentInvariantService(db)
        invariant_service.assert_no_processing_invoice_reservation(
            [visit.id for visit in visits]
        )
        settlement = invariant_service.summarize_visits(visits)
        if settlement["currency"] != invoice.currency:
            raise HTTPException(status_code=409, detail="Валюта счёта требует сверки")
        ledger_remaining_amount = Decimal(str(settlement["remaining_amount"]))
        invoice_total = Decimal(str(invoice.total_amount or 0))
        remaining_amount = min(invoice_total, ledger_remaining_amount)
        paid_amount = max(invoice_total - remaining_amount, Decimal("0"))
        actions, _ = PaymentInvoiceService(
            db,
            payment_manager=payment_manager,
        ).resolve_online_payment_actions(
            invoice=invoice,
            has_linked_visits=True,
            paid_amount=paid_amount,
            remaining_amount=remaining_amount,
            ledger_remaining_amount=ledger_remaining_amount,
            linked_amount=sum(
                (Decimal(str(link.visit_amount)) for link in invoice_visits),
                Decimal("0"),
            ),
            actor_role=getattr(current_user, "role", None),
            has_processing_reservation=False,
        )
        allowed_providers = {action["provider"] for action in actions}
        if provider_name not in allowed_providers:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Сумма или способ оплаты счёта изменились. "
                    "Обновите список счетов перед оплатой."
                ),
            )

        # Создаём платёж
        result = payment_manager.create_payment(
            provider_name=provider_name,
            amount=invoice.total_amount,
            currency=invoice.currency,
            order_id=f"invoice_{invoice.id}",
            description=f"Оплата визитов #{invoice.id}",
            return_url=payment_req.return_url,
            cancel_url=payment_req.cancel_url,
        )

        if result.success:
            # Обновляем invoice
            invoice.provider_payment_id = result.payment_id
            invoice.payment_method = provider_name
            invoice.provider = provider_name
            invoice.status = "processing"
            invoice.provider_data = result.provider_data
            db.commit()

            return InvoicePaymentResponse(
                success=True,
                payment_url=result.payment_url,
                provider_payment_id=result.payment_id,
            )
        else:
            db.rollback()
            return InvoicePaymentResponse(
                success=False, error_message=result.error_message
            )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


def _invoice_checkout_binding(invoice: PaymentInvoice, links: list[PaymentInvoiceVisit]) -> tuple:
    return (
        invoice.patient_id,
        invoice.provider,
        invoice.provider_payment_id,
        invoice.provider_transaction_id,
        invoice.total_amount,
        invoice.currency,
        tuple((link.id, link.visit_id, link.visit_amount) for link in links),
    )


def _click_outcome_reference(invoice: PaymentInvoice, result: PaymentResult) -> str | None:
    """Check evidence returned by the provider, including the invoice amount."""
    data = getattr(result, "provider_data", None)
    if not isinstance(data, dict):
        raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED)
    raw_status = data.get("status")
    raw_amount = data.get("amount")
    error_code = data.get("error_code", 0)
    if (
        invoice.provider != "click"
        or result.payment_id != invoice.provider_payment_id
        or data.get("merchant_trans_id") != invoice.provider_payment_id
        or type(raw_status) is not int
        or raw_status != _CLICK_FINAL_STATUS[result.status]
        or type(error_code) is not int
        or error_code != 0
        or invoice.currency != "UZS"
        or data.get("currency", "UZS") != invoice.currency
        or type(raw_amount) not in (Decimal, str, int)
    ):
        raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED)
    try:
        exact_amount = parse_money(raw_amount)
    except MoneyInputError as exc:
        raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED) from exc
    if exact_amount != invoice.total_amount:
        raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED)
    if result.status != "completed":
        return None

    reference = data.get("click_trans_id")
    if type(reference) is int:
        reference = str(reference)
    if (
        not isinstance(reference, str)
        or not 1 <= len(reference) <= 19
        or not reference.isascii()
        or not reference.isdecimal()
        or reference.startswith("0")
        or invoice.provider_transaction_id not in (None, reference)
    ):
        raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED)
    return reference


def _record_completed_invoice(
    db: Session,
    invoice: PaymentInvoice,
    visits: list[Visit],
    links: list[PaymentInvoiceVisit],
    reference: str,
    actor: User,
) -> None:
    """Apply one verified provider receipt while the financial locks are held."""
    allocations: dict[int, Decimal] = {}
    for link in links:
        if link.visit_amount > 0:
            allocations[link.visit_id] = allocations.get(link.visit_id, Decimal("0.00")) + link.visit_amount
    if db.query(PaymentInvoice.id).filter(
        PaymentInvoice.id != invoice.id,
        PaymentInvoice.provider == invoice.provider,
        or_(PaymentInvoice.provider_payment_id == invoice.provider_payment_id,
            PaymentInvoice.provider_transaction_id == reference),
    ).first():
        raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED)

    existing_visits: set[int] = set()
    existing = db.query(Payment).filter(
        Payment.provider == invoice.provider,
        or_(Payment.provider_payment_id == invoice.provider_payment_id,
            Payment.provider_transaction_id == reference),
    ).populate_existing().all()
    for payment in existing:
        visit_id = payment.visit_id
        if (
            visit_id not in allocations or visit_id in existing_visits
            or payment.amount != allocations[visit_id] or payment.currency != invoice.currency
            or payment.status not in {"paid", "completed"}
            or payment.provider_payment_id != invoice.provider_payment_id
            or payment.provider_transaction_id != reference
        ):
            raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED)
        existing_visits.add(visit_id)

    invariant = PaymentInvariantService(db)
    for visit_id, amount in sorted(allocations.items()):
        if visit_id in existing_visits:
            continue
        payment = invariant.create_payment_for_visit(
            visit_id=visit_id,
            amount=amount,
            method="online",
            note=f"Оплата через {invoice.provider} (invoice {invoice.id})",
            current_user=actor,
            provider=invoice.provider,
            currency=invoice.currency,
            allow_overpayment=False,
            settling_invoice_id=invoice.id,
            commit=False,
        )
        payment.provider_payment_id = invoice.provider_payment_id
        payment.provider_transaction_id = reference
        payment.provider_data = invoice.provider_data

    # Clinical transitions can advance the visit context epoch. Run them only
    # after the entire receipt has been checked and staged under the same locks.
    lifecycle = VisitLifecycleService(db)
    actor_id = f"invoice_{invoice.id}"
    invoice_actor = SimpleNamespace(id=actor_id)
    for visit in visits:
        if visit.id in allocations and not awaits_all_free_decision(visit):
            lifecycle.confirm_visit(
                visit_id=visit.id,
                current_user=invoice_actor,
                confirmed_by=actor_id,
                commit=False,
            )
    invoice.provider_transaction_id = reference
    invoice.status = "paid"
    invoice.paid_at = datetime.now(UTC)


def _paid_invoice_print_tickets(
    db: Session, invoice: PaymentInvoice,
) -> list[dict[str, Any]]:
    """Project the clinic's issued numbers for this invoice and its patient."""
    linked_visit = (
        select(PaymentInvoiceVisit.id)
        .where(
            PaymentInvoiceVisit.invoice_id == invoice.id,
            PaymentInvoiceVisit.visit_id == Visit.id,
        )
        .exists()
    )
    statement = (
        select(
            OnlineQueueEntry.number.label("queue_number"),
            OnlineQueueEntry.status.label("queue_status"),
            DailyQueue.id.label("queue_id"),
            DailyQueue.active.label("queue_active"),
            DailyQueue.queue_tag,
            DailyQueue.cabinet_number,
            Visit.id.label("visit_id"),
            Visit.department,
            Visit.visit_date,
            Visit.visit_time,
            Patient,
            QueueResource.display_name.label("queue_name"),
            User.full_name.label("doctor_name"),
            Doctor.cabinet.label("doctor_cabinet"),
        )
        .select_from(OnlineQueueEntry)
        .join(Visit, Visit.id == OnlineQueueEntry.visit_id)
        .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
        .join(Patient, Patient.id == Visit.patient_id)
        .outerjoin(QueueResource, QueueResource.id == DailyQueue.queue_resource_id)
        .outerjoin(
            Doctor,
            and_(
                Doctor.id == DailyQueue.specialist_id,
                DailyQueue.queue_resource_id.is_(None),
            ),
        )
        .outerjoin(User, User.id == Doctor.user_id)
        .options(load_only(Patient.first_name, Patient.last_name, Patient.middle_name))
        .where(
            linked_visit,
            Visit.patient_id == invoice.patient_id,
            OnlineQueueEntry.patient_id == invoice.patient_id,
            DailyQueue.day == Visit.visit_date,
            OnlineQueueEntry.number > 0,
            ~all_free_decision_required_clause(),
            Visit.status.notin_(
                (
                    "pending_confirmation",
                    "confirmation_processing",
                    "cancelled",
                    "canceled",
                    "no_show",
                    "rescheduled",
                )
            ),
        )
        .order_by(Visit.id, DailyQueue.id, OnlineQueueEntry.number, OnlineQueueEntry.id)
    )

    tickets = []
    for row in db.execute(statement):
        status = normalize_queue_status(row.queue_status)
        if status != "served" and (
            not row.queue_active or status not in POSITION_VISIBLE_RAW_STATUSES
        ):
            continue
        tickets.append(
            {
                "visit_id": row.visit_id,
                "queue_tag": row.queue_tag,
                "queue_name": row.queue_name or row.queue_tag,
                "queue_number": row.queue_number,
                "queue_id": row.queue_id,
                "patient_id": row.Patient.id,
                "patient_name": row.Patient.short_name(),
                "doctor_name": row.doctor_name,
                "doctor_cabinet": row.cabinet_number or row.doctor_cabinet,
                "department": row.department,
                "visit_date": row.visit_date.isoformat(),
                "visit_time": row.visit_time,
            }
        )
    return tickets


def _invoice_status_response(
    db: Session, invoice: PaymentInvoice,
) -> dict[str, Any]:
    return {
        "invoice_id": invoice.id,
        "status": invoice.status,
        "total_amount": invoice.total_amount,
        "currency": invoice.currency,
        "provider_payment_id": invoice.provider_payment_id,
        "paid_at": invoice.paid_at,
        "print_tickets": _paid_invoice_print_tickets(db, invoice) if invoice.status == "paid" else [],
    }


def _invoice_status_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get(
    "/registrar/invoice/{invoice_id}/status",
    response_model=dict[str, Any],
    dependencies=[Depends(_invoice_status_no_store)],
)
def check_invoice_status(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Read the provider outside the transaction that records its receipt."""
    try:
        invoice = db.get(PaymentInvoice, invoice_id, populate_existing=True)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice не найден")
        if invoice.status != "processing" or not invoice.provider_payment_id or not invoice.provider:
            return _invoice_status_response(db, invoice)

        snapshot = _invoice_checkout_binding(invoice, _read_invoice_links(db, invoice_id))
        provider_name = invoice.provider.lower()
        provider_payment_id = invoice.provider_payment_id
        payment_manager = get_payment_manager()
        if not payment_manager.supports_registrar_invoice_payment(provider_name):
            return _invoice_status_response(db, invoice)

        db.rollback()
        result = payment_manager.check_payment_status(provider_name, provider_payment_id)
        if not result.success or result.status not in _CLICK_FINAL_STATUS:
            invoice = db.get(PaymentInvoice, invoice_id, populate_existing=True)
            if invoice is None:
                raise HTTPException(status_code=404, detail="Invoice не найден")
            return _invoice_status_response(db, invoice)

        invoice, visits, links = _lock_invoice_settlement_context(db, invoice_id)
        if invoice.status in _FINAL_INVOICE_STATES:
            status_payload = _invoice_status_response(db, invoice)
            db.rollback()
            return status_payload
        if invoice.status != "processing" or _invoice_checkout_binding(invoice, links) != snapshot:
            raise HTTPException(status_code=409, detail=_INVOICE_RECONCILIATION_REQUIRED)

        reference = _click_outcome_reference(invoice, result)
        if reference is not None:
            _record_completed_invoice(db, invoice, visits, links, reference, current_user)
        else:
            invoice.status = result.status
        db.commit()
        return _invoice_status_response(db, invoice)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/registrar/repeat-eligibility-preview",
    response_model=RepeatEligibilityPreviewResponse,
    summary="Preview eligibility for repeat discount in registrar wizard",
)
def preview_repeat_eligibility(
    payload: RepeatEligibilityPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    _ = current_user

    patient_exists = (
        db.query(Patient.id).filter(Patient.id == payload.patient_id).first() is not None
    )
    if not patient_exists:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    settings = _load_registration_discount_settings(db)
    repeat_visit_days = int(settings.get("repeat_visit_days", 21) or 21)
    repeat_discount_percent = int(settings.get("repeat_visit_discount", 0) or 0)

    items = [
        _build_repeat_eligibility_preview_item(
            db,
            patient_id=payload.patient_id,
            candidate=candidate,
            repeat_visit_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )
        for candidate in payload.candidates
    ]

    return RepeatEligibilityPreviewResponse(patient_id=payload.patient_id, items=items)


# ===================== ОСНОВНОЙ ENDPOINT =====================

