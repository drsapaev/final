from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa
from app.api.v1.endpoints.registrar_wizard._helpers import (
    _build_repeat_eligibility_preview_item,
    _load_registration_discount_settings,
)  # noqa: F401


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
        # Получаем invoice
        invoice = (
            db.query(PaymentInvoice)
            .filter(PaymentInvoice.id == payment_req.invoice_id)
            .first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice не найден")

        if invoice.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Invoice уже обработан: {invoice.status}"
            )

        # Инициализируем провайдер платежей
        provider_name = payment_req.provider.lower()
        if provider_name not in SUPPORTED_INVOICE_PAYMENT_PROVIDERS:
            return InvoicePaymentResponse(
                success=False,
                error_message=f"Провайдер {payment_req.provider} не поддерживается",
            )

        # Создаём платёж
        result = get_payment_manager().create_payment(
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

            if provider_name in SUPPORTED_INVOICE_PAYMENT_PROVIDERS:
                result = get_payment_manager().check_payment_status(
                    provider_name, invoice.provider_payment_id
                )

                if result.success:
                    # Обновляем статус invoice
                    if result.status == "completed":
                        invoice.status = "paid"
                        invoice.paid_at = datetime.now(UTC)

                        # [OK] ИСПРАВЛЕНО: Создаем платежи для всех визитов через SSOT
                        from app.services.billing_service import BillingService

                        billing_service = BillingService(db)

                        # Помечаем все визиты как оплаченные и создаем платежи
                        invoice_visits = (
                            db.query(PaymentInvoiceVisit)
                            .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
                            .all()
                        )

                        for iv in invoice_visits:
                            visit = (
                                db.query(Visit).filter(Visit.id == iv.visit_id).first()
                            )
                            if visit:
                                # Проверяем, не создан ли уже платеж
                                from app.models.payment import Payment

                                existing_payment = (
                                    db.query(Payment)
                                    .filter(
                                        Payment.visit_id == visit.id,
                                        Payment.status == "paid",
                                    )
                                    .first()
                                )

                                if not existing_payment:
                                    # Issue #06 Phase 4b B1+: Replaced
                                    # BillingService.create_payment() with
                                    # PaymentInvariantService.create_payment_for_visit().
                                    #
                                    # This caller creates PAID payments (after
                                    # provider confirmation via webhook), so it
                                    # uses create_payment_for_visit() (cashier
                                    # path), NOT create_pending_payment().
                                    #
                                    # commit=False because this is inside a
                                    # composition (payment + visit confirmation
                                    # committed together at line 200).
                                    from app.services.payment_invariant_service import PaymentInvariantService
                                    from decimal import Decimal

                                    payment = PaymentInvariantService(db).create_payment_for_visit(
                                        visit_id=visit.id,
                                        amount=Decimal(str(iv.visit_amount)),
                                        method="online",
                                        note=f"Оплата через {invoice.provider} (invoice {invoice.id})",
                                        current_user=current_user,
                                        provider=invoice.provider,
                                        commit=False,  # composition — caller commits
                                    )
                                    logger.info(
                                        "check_invoice_status: Создан платеж ID=%d для визита %d",
                                        payment.id,
                                        visit.id,
                                    )

                                # Issue #06 Phase 4b Fix #4: Replaced direct
                                # visit.status = "confirmed" with
                                # VisitLifecycleService.confirm_visit(commit=False).
                                #
                                # Business semantics: this is a PAYMENT-DRIVEN
                                # confirmation — the visit was in pending_confirmation
                                # status, and after the online payment is confirmed
                                # by the provider, the visit transitions to confirmed.
                                # This is NOT a user-driven confirmation (registrar
                                # clicking "confirm" button).
                                #
                                # commit=False because this is inside a larger
                                # transaction (invoice status + payment + visit
                                # status all committed together at line 171).
                                from app.services.visit_lifecycle_service import VisitLifecycleService

                                class _InvoiceActor:
                                    def __init__(self, invoice_id: int) -> None:
                                        self.id = f"invoice_{invoice_id}"

                                VisitLifecycleService(db).confirm_visit(
                                    visit_id=visit.id,
                                    current_user=_InvoiceActor(invoice.id),
                                    confirmed_by=f"invoice_{invoice.id}",
                                    commit=False,  # caller owns the transaction
                                )

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

