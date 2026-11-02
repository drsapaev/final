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
    _cashier_external_refunds_by_payment_id,
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


@router.get("/stats", response_model=CashierStatsResponse)
async def get_cashier_stats(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
    date_from: date | None = Query(None, description="Дата начала"),
    date_to: date | None = Query(None, description="Дата окончания"),
):
    """
    Получить агрегированную статистику платежей за период.

    CSH-FE-036 (#3813 follow-up): контракт фиксирован — ОБЕ финансовые
    величины. ``total_amount``/``cash_amount``/``card_amount`` — валовые
    поступления (исходные суммы ``paid``/``completed`` без вычета возвратов;
    значение существующих полей не меняется молча).
    ``refunded_amount``/``net_*`` — поступления за вычетом возвратов.
    ``pending_amount`` с CSH-FE-028 (#3814) считается за вычетом возвратов.
    """
    try:
        query = db.query(Payment)

        if date_from:
            query = query.filter(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.filter(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))

        payments = query.all()

        total_amount = Decimal("0")
        cash_amount = Decimal("0")
        card_amount = Decimal("0")
        refunded_amount = Decimal("0")
        refunded_cash_amount = Decimal("0")
        refunded_card_amount = Decimal("0")
        pending_amount = Decimal("0")
        paid_count = 0
        cancelled_count = 0
        gross_payments: list[Payment] = []


        for p in payments:
            if p.status in ["paid", "completed"]:
                total_amount += p.amount
                paid_count += 1
                gross_payments.append(p)
                # CSH-FE-036: partial refunds keep the payment inside the
                # gross set (status stays paid/completed, refunded_amount
                # grows). A FULL refund flips the status to 'refunded' —
                # such a payment has already left this set and never entered
                # the gross sums, so it is not counted here either.
                p_refunded = (
                    Decimal(str(p.refunded_amount or 0))
                    if getattr(p, "refunded_amount", None) is not None
                    else Decimal("0")
                )
                refunded_amount += p_refunded
                if hasattr(p, 'method') and p.method == "cash":
                    cash_amount += p.amount
                    refunded_cash_amount += p_refunded
                elif hasattr(p, 'method') and p.method == "card":
                    card_amount += p.amount
                    refunded_card_amount += p_refunded
            elif p.status in ["cancelled", "refunded"]:
                cancelled_count += 1

        # CSH-FE-036 (#3830 review): reconcile the refund channels through
        # the canonical invariant. Force-majeure legs return money WITHOUT
        # touching Payment.refunded_amount: a deposit credit rows a
        # DepositTransaction CREDIT (completed by construction — the patient
        # balance already rose) and a bank claim is money-returned only at
        # RefundRequest.status == 'completed' (pending/approved/processing
        # have sent nothing yet). The channels are mutually exclusive per
        # payment (payment_refund_claims) and disjoint from direct cashier
        # refunds above, so nothing is counted twice.
        external_refunds = _cashier_external_refunds_by_payment_id(
            db, [p.id for p in gross_payments]
        )
        for p in gross_payments:
            external = external_refunds.get(p.id)
            if external is None:
                continue
            # Anomaly guard (parity with PaymentInvariantService.
            # _net_settled_amount): a payment can never contribute negative
            # net receipts, so an over-refunded payment is capped at its
            # unrefunded remainder.
            remaining = max(
                Decimal(str(p.amount or 0))
                - Decimal(str(getattr(p, "refunded_amount", None) or 0)),
                Decimal("0"),
            )
            effective_external = min(Decimal(str(external)), remaining)
            refunded_amount += effective_external
            if hasattr(p, 'method') and p.method == "cash":
                refunded_cash_amount += effective_external
            elif hasattr(p, 'method') and p.method == "card":
                refunded_card_amount += effective_external


        # Считаем pending из Visit
        pending_query = db.query(Visit).options(joinedload(Visit.services)).filter(
            ~Visit.status.in_(CASHIER_PENDING_EXCLUDED_VISIT_STATUSES)
        )
        if date_from:
            pending_query = pending_query.filter(Visit.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            pending_query = pending_query.filter(Visit.created_at <= datetime.combine(date_to, datetime.max.time()))

        # Считаем только визиты без полной оплаты
        pending_count = 0
        visits = pending_query.all()
        visit_ids = [v.id for v in visits]

        if visit_ids:
            # CSH-FE-028: net settled (unrefunded) paid amounts via the
            # canonical invariant service — gross sums understate pending
            # debt after partial refunds.
            paid_by_visit = _cashier_paid_amounts_by_visit_id(db, visit_ids)

            for v in visits:
                # Считаем стоимость визита
                visit_total = Decimal("0")
                if hasattr(v, 'services') and v.services:
                    for vs in v.services:
                        price = Decimal(str(vs.price)) if hasattr(vs, 'price') and vs.price else Decimal("0")
                        qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1
                        visit_total += price * qty

                if visit_total == Decimal("0") and hasattr(v, 'total_price') and v.total_price:
                    visit_total = Decimal(str(v.total_price))

                paid_for_visit = paid_by_visit.get(v.id, Decimal("0"))
                if paid_for_visit < visit_total:
                    pending_count += 1
                    pending_amount += (visit_total - paid_for_visit)

        return CashierStatsResponse(
            total_amount=total_amount,
            cash_amount=cash_amount,
            card_amount=card_amount,
            refunded_amount=refunded_amount,
            net_total_amount=total_amount - refunded_amount,
            net_cash_amount=cash_amount - refunded_cash_amount,
            net_card_amount=card_amount - refunded_card_amount,
            pending_count=pending_count,
            pending_amount=pending_amount,
            paid_count=paid_count,
            cancelled_count=cancelled_count,

        )

    except Exception:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/stats/hourly", response_model=list[HourlyStatItem])
async def get_hourly_stats(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
    target_date: date | None = Query(None, description="Дата для статистики (по умолчанию сегодня)"),
):
    """
    Получить почасовую статистику платежей за день.
    """
    try:
        if not target_date:
            target_date = date.today()

        # Получаем все платежи за день
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        payments = db.query(Payment).filter(
            Payment.created_at >= start_of_day,
            Payment.created_at <= end_of_day,
            Payment.status.in_(["paid", "completed"])
        ).all()

        # Группируем по часам
        hourly_data = {}
        for h in range(24):
            hourly_data[h] = {"hour": h, "count": 0, "amount": Decimal("0")}

        for p in payments:
            hour = p.created_at.hour
            hourly_data[hour]["count"] += 1
            hourly_data[hour]["amount"] += p.amount

        return [HourlyStatItem(**data) for data in hourly_data.values()]

    except Exception:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


