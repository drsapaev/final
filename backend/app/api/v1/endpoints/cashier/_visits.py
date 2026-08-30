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
    # Issue #06 (H-4 coverage gap): this endpoint previously created a
    # Payment via direct db.add() WITHOUT with_for_update() and WITHOUT
    # the paid_amount check — a second double-payment race that the
    # H-4 fix in create_payment did not cover.
    #
    # Issue #06 Phase 2: now delegates to PaymentInvariantService
    # (split from VisitLifecycleService), which is the single source
    # of truth for cashier-initiated payment creation. This ensures:
    #   1. Row-level lock on the visit (serializes concurrent mark-paid
    #      and create_payment requests on the same visit).
    #   2. paid_amount vs total_cost check (rejects if already paid).
    #   3. Overpayment-allowed-as-deposit policy (logged at WARNING).
    #   4. Defense-in-depth IntegrityError handler (409, not 500).
    from app.services.payment_invariant_service import PaymentInvariantService
    from app.services.visit_lifecycle_service import VisitLifecycleService

    try:
        payment_service = PaymentInvariantService(db)
        lifecycle_service = VisitLifecycleService(db)

        # Compute the full visit total — mark-paid creates a single
        # payment for the entire amount.
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )

        total_amount = payment_service.compute_total_cost(visit)

        if total_amount > 0:
            new_payment = payment_service.create_payment_for_visit(
                visit_id=visit_id,
                amount=total_amount,
                method="cash",
                note="Помечен как оплаченный",
                current_user=current_user,
            )

            # [FIX:PAYMENT_STATUS] Оплата не должна перезаписывать operational
            # статус визита и не должна менять registration type.
            # VisitLifecycleService.restore_operational_status_after_payment_change()
            # normalizes any legacy "paid" status to an operational status.
            visit = lifecycle_service.restore_operational_status_after_payment_change(visit_id)
            db.commit()

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

    except HTTPException:
        raise
    except Exception:
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
    except Exception:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ===================== ПОЧАСОВАЯ СТАТИСТИКА =====================

