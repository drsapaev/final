from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa
from app.api.v1.endpoints.registrar_wizard._helpers import (
    _build_repeat_eligibility_preview_item,
    _load_registration_discount_settings,
)  # noqa: F401
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.payment_invoice_service import PaymentInvoiceService


def _lock_invoice_settlement_context(
    db: Session,
    invoice_id: int,
) -> tuple[PaymentInvoice, list[Visit], list[PaymentInvoiceVisit]]:
    """Lock invoice visits before the invoice and revalidate their linkage.

    Cash and grouped-payment commands lock visits first. Using the same order
    avoids a visit/invoice deadlock while preserving coordination with invoice
    edits, which lock the invoice before changing its amount or links.
    """
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
                .filter(
                    PaymentInvoiceVisit.invoice_id == invoice_id,
                    PaymentInvoiceVisit.visit_amount > 0,
                )
                .all()
            )
        }
    )
    if not initial_visit_ids:
        raise HTTPException(
            status_code=409,
            detail="Счёт не связан с оплачиваемыми визитами",
        )

    visits = (
        db.query(Visit)
        .filter(Visit.id.in_(initial_visit_ids))
        .order_by(Visit.id)
        .with_for_update(of=Visit)
        .populate_existing()
        .all()
    )
    if len(visits) != len(initial_visit_ids):
        raise HTTPException(
            status_code=409,
            detail="Состав счёта изменился. Обновите список счетов.",
        )

    invoice = (
        db.query(PaymentInvoice)
        .filter(PaymentInvoice.id == invoice_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice не найден")

    invoice_visits = (
        db.query(PaymentInvoiceVisit)
        .filter(
            PaymentInvoiceVisit.invoice_id == invoice.id,
            PaymentInvoiceVisit.visit_amount > 0,
        )
        .order_by(PaymentInvoiceVisit.visit_id, PaymentInvoiceVisit.id)
        .populate_existing()
        .all()
    )
    locked_visit_ids = sorted({int(link.visit_id) for link in invoice_visits})
    if locked_visit_ids != initial_visit_ids or any(
        visit.patient_id != invoice.patient_id for visit in visits
    ):
        raise HTTPException(
            status_code=409,
            detail="Состав счёта изменился. Обновите список счетов.",
        )
    linked_amount = sum(
        (Decimal(str(link.visit_amount)) for link in invoice_visits),
        Decimal("0"),
    )
    if linked_amount != Decimal(str(invoice.total_amount or 0)):
        raise HTTPException(
            status_code=409,
            detail=(
                "Распределение суммы счёта изменилось. "
                "Обновите список счетов перед оплатой."
            ),
        )
    # An edit may have held the invoice lock while changing VisitService rows.
    # Refresh those rows only after both lock sets are held so the balance and
    # invoice amount belong to the same committed state.
    visits = (
        db.query(Visit)
        .options(selectinload(Visit.services))
        .filter(Visit.id.in_(initial_visit_ids))
        .order_by(Visit.id)
        .populate_existing()
        .all()
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
        )

        if invoice.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Invoice уже обработан: {invoice.status}"
            )

        # Инициализируем провайдер платежей
        provider_name = payment_req.provider.lower()
        payment_manager = get_payment_manager()
        if not payment_manager.supports_registrar_invoice_payment(provider_name):
            return InvoicePaymentResponse(
                success=False,
                error_message=f"Провайдер {payment_req.provider} не поддерживается",
            )

        invariant_service = PaymentInvariantService(db)
        invariant_service.assert_no_processing_invoice_reservation(
            [visit.id for visit in visits]
        )
        settlement = invariant_service.summarize_visits(visits)
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
            return InvoicePaymentResponse(
                success=False, error_message=result.error_message
            )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/registrar/invoice/{invoice_id}/status", response_model=dict[str, Any])
def check_invoice_status(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Проверка статуса оплаты invoice
    """
    try:
        invoice = (
            db.query(PaymentInvoice).filter(PaymentInvoice.id == invoice_id).first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice не найден")

        # Если статус уже финальный, возвращаем как есть
        if invoice.status in ["paid", "failed", "cancelled"]:
            return {
                "invoice_id": invoice.id,
                "status": invoice.status,
                "total_amount": invoice.total_amount,
                "currency": invoice.currency,
                "provider_payment_id": invoice.provider_payment_id,
            }

        # Проверяем статус у провайдера
        if invoice.provider_payment_id and invoice.provider:
            provider_name = invoice.provider.lower()

            payment_manager = get_payment_manager()
            if payment_manager.supports_registrar_invoice_payment(provider_name):
                result = payment_manager.check_payment_status(
                    provider_name, invoice.provider_payment_id
                )

                if result.success:
                    # Обновляем статус invoice
                    if result.status == "completed":
                        (
                            invoice,
                            locked_visits,
                            invoice_visits,
                        ) = _lock_invoice_settlement_context(db, invoice.id)
                        if invoice.status == "paid":
                            return {
                                "invoice_id": invoice.id,
                                "status": invoice.status,
                                "total_amount": invoice.total_amount,
                                "currency": invoice.currency,
                                "provider_payment_id": invoice.provider_payment_id,
                                "paid_at": invoice.paid_at,
                            }
                        if invoice.status != "processing":
                            raise HTTPException(
                                status_code=409,
                                detail=(
                                    "Состояние счёта изменилось. "
                                    "Обновите список счетов."
                                ),
                            )

                        visits_by_id = {visit.id: visit for visit in locked_visits}
                        allocation_by_visit_id: dict[int, Decimal] = {}
                        for invoice_visit in invoice_visits:
                            allocation_by_visit_id[invoice_visit.visit_id] = (
                                allocation_by_visit_id.get(
                                    invoice_visit.visit_id,
                                    Decimal("0"),
                                )
                                + Decimal(str(invoice_visit.visit_amount))
                            )
                        invariant_service = PaymentInvariantService(db)

                        from app.models.payment import Payment
                        from app.services.visit_lifecycle_service import (
                            VisitLifecycleService,
                        )

                        class _InvoiceActor:
                            def __init__(self, invoice_id: int) -> None:
                                self.id = f"invoice_{invoice_id}"

                        for visit_id, visit_amount in sorted(
                            allocation_by_visit_id.items()
                        ):
                            visit = visits_by_id.get(visit_id)
                            if visit:
                                # Idempotency is tied to this provider checkout,
                                # not to any historical cash receipt for the visit.
                                existing_payment = (
                                    db.query(Payment)
                                    .filter(
                                        Payment.visit_id == visit.id,
                                        Payment.provider == invoice.provider,
                                        Payment.provider_payment_id
                                        == invoice.provider_payment_id,
                                        Payment.status.in_(["paid", "completed"]),
                                    )
                                    .first()
                                )

                                if not existing_payment:
                                    payment = invariant_service.create_payment_for_visit(
                                        visit_id=visit.id,
                                        amount=visit_amount,
                                        method="online",
                                        note=f"Оплата через {invoice.provider} (invoice {invoice.id})",
                                        current_user=current_user,
                                        provider=invoice.provider,
                                        allow_overpayment=False,
                                        settling_invoice_id=invoice.id,
                                        commit=False,
                                    )
                                    payment.provider_payment_id = (
                                        invoice.provider_payment_id
                                    )
                                    payment.provider_transaction_id = (
                                        invoice.provider_transaction_id
                                    )
                                    payment.provider_data = invoice.provider_data
                                    logger.info(
                                        "check_invoice_status: Создан платеж ID=%d для визита %d",
                                        payment.id,
                                        visit.id,
                                    )

                                VisitLifecycleService(db).confirm_visit(
                                    visit_id=visit.id,
                                    current_user=_InvoiceActor(invoice.id),
                                    confirmed_by=f"invoice_{invoice.id}",
                                    commit=False,
                                )

                        invoice.status = "paid"
                        invoice.paid_at = datetime.now(UTC)
                        db.commit()
                    elif result.status in ["failed", "cancelled"]:
                        invoice.status = result.status
                        db.commit()

        return {
            "invoice_id": invoice.id,
            "status": invoice.status,
            "total_amount": invoice.total_amount,
            "currency": invoice.currency,
            "provider_payment_id": invoice.provider_payment_id,
            "paid_at": invoice.paid_at,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


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

