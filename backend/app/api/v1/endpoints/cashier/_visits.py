"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from cashier.py (1787 LOC god file → modular).
"""
from __future__ import annotations

from app.api.v1.endpoints.cashier._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.cashier._helpers import (  # noqa: F401
    CancelPaymentRequest,
    CashierStatsResponse,
    CreateGroupedPaymentRequest,
    CreatePaymentRequest,
    GroupedPaymentAllocationItem,
    GroupedPaymentResponse,
    HourlyStatItem,
    PaginatedResponse,
    PaymentHistoryItem,
    PaymentResponse,
    PendingPaymentItem,
    RefundRequest,
    RefundResponse,
    T,
    _cashier_paid_amounts_by_visit_id,
    _cashier_payment_action_contract,
    _cashier_payment_available_amount,
    _cashier_payment_status,
    _cashier_visit_total_amount,
    _decimal_to_float,
    _emit_payment_notification,
    _preserve_cashier_visit_status,
    get_patient_name,
    router,
)

@router.post("/visits/{visit_id}/mark-paid", response_model=dict[str, Any])
async def mark_visit_as_paid(
    visit_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """
    Отметить визит как оплаченный.
    Создаёт платёж на полную сумму услуг визита.
    """
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Визит не найден"
        )

    try:
        # Вычисляем общую сумму услуг
        total_amount = Decimal("0")
        if hasattr(visit, 'services') and visit.services:
            for vs in visit.services:
                price = Decimal(str(vs.price)) if hasattr(vs, 'price') and vs.price else Decimal("0")
                qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1
                total_amount += price * qty

        # Создаём платёж на полную сумму
        if total_amount > 0:
            new_payment = Payment(
                visit_id=visit_id,
                amount=total_amount,
                method="cash",
                status="paid",
                note="Помечен как оплаченный",
                created_at=datetime.now(UTC),
                paid_at=datetime.now(UTC),
            )
            db.add(new_payment)

        # [FIX:PAYMENT_STATUS] Оплата не должна перезаписывать operational статус визита
        # и не должна менять registration type.
        visit.status = _preserve_cashier_visit_status(visit.status)

        db.commit()

        if total_amount > 0:
            await _emit_payment_notification(
                db=db,
                payment=new_payment,
                current_user=current_user,
                change_type="paid",
                patient_id=visit.patient_id,
                visit=visit,
            )

        return {
            "success": True,
            "message": "Визит отмечен как оплаченный",
            "visit_id": visit_id,
            "status": visit.status,
            "payment_status": "paid",
            "amount": float(total_amount)
        }

    except Exception as e:
        db.rollback()
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ===================== ВОЗВРАТ СРЕДСТВ =====================


@router.get("/payments/{payment_id}/receipt", response_model=dict[str, Any])
async def get_payment_receipt(
    payment_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """Генерация PDF-чека для платежа."""
    try:
        service = PaymentReadService(db)
        pdf_bytes = service.build_receipt_pdf(payment_id=payment_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="receipt_{payment_id}.pdf"'
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ===================== ПОЧАСОВАЯ СТАТИСТИКА =====================

