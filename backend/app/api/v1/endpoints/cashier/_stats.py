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

@router.get("/stats", response_model=CashierStatsResponse)
async def get_cashier_stats(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
    date_from: date | None = Query(None, description="Дата начала"),
    date_to: date | None = Query(None, description="Дата окончания"),
):
    """
    Получить агрегированную статистику платежей за период.
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
        pending_amount = Decimal("0")
        paid_count = 0
        cancelled_count = 0


        for p in payments:
            if p.status in ["paid", "completed"]:
                total_amount += p.amount
                paid_count += 1
                if hasattr(p, 'method') and p.method == "cash":
                    cash_amount += p.amount
                elif hasattr(p, 'method') and p.method == "card":
                    card_amount += p.amount
            elif p.status in ["cancelled", "refunded"]:
                cancelled_count += 1


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
            # Получаем суммы платежей для каждого визита
            from collections import defaultdict
            paid_by_visit = defaultdict(Decimal)
            existing = db.query(Payment).filter(
                Payment.visit_id.in_(visit_ids),
                Payment.status.in_(["paid", "completed"])
            ).all()
            for ep in existing:
                paid_by_visit[ep.visit_id] += ep.amount

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
            pending_count=pending_count,
            pending_amount=pending_amount,
            paid_count=paid_count,
            cancelled_count=cancelled_count,

        )

    except Exception as e:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/payments/export", response_model=dict[str, Any])
async def export_payments(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
    date_from: date | None = Query(None, description="Дата начала"),
    date_to: date | None = Query(None, description="Дата окончания"),
):
    """
    Экспорт всех платежей за период в CSV.
    """
    import csv
    import io

    from fastapi.responses import StreamingResponse

    try:
        query = db.query(Payment)

        if date_from:
            query = query.filter(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.filter(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))

        query = query.order_by(Payment.created_at.desc()).limit(10000)
        payments = query.all()

        # Batch load visits and patients
        visit_ids = [p.visit_id for p in payments if p.visit_id]
        visits_map = {}
        patients_map = {}

        if visit_ids:
            visits = db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
            visits_map = {v.id: v for v in visits}

            patient_ids = [v.patient_id for v in visits if v.patient_id]
            if patient_ids:
                patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
                patients_map = {p.id: p for p in patients}

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        # Header
        writer.writerow(['Дата', 'Время', 'Пациент', 'Способ оплаты', 'Сумма', 'Статус', 'Примечание'])

        for p in payments:
            patient_name = "Неизвестно"
            if p.visit_id and p.visit_id in visits_map:
                visit = visits_map[p.visit_id]
                patient = patients_map.get(visit.patient_id)
                patient_name = get_patient_name(patient, visit.patient_id)

            date_str = p.created_at.strftime('%d.%m.%Y') if p.created_at else ''
            time_str = p.created_at.strftime('%H:%M') if p.created_at else ''
            method_str = 'Наличные' if p.method == 'cash' else 'Карта' if p.method == 'card' else p.method
            status_str = 'Оплачено' if p.status in ['paid', 'completed'] else 'Отменён' if p.status == 'cancelled' else 'Ожидает'

            writer.writerow([
                date_str,
                time_str,
                patient_name,
                method_str,
                str(p.amount),
                status_str,
                p.note or ''
            ])

        output.seek(0)

        # Return as streaming response with proper encoding for Cyrillic
        def generate():
            yield '\ufeff'  # BOM for Excel
            yield output.getvalue()

        filename = f"payments_{date_from or 'all'}_{date_to or 'all'}.csv"

        return StreamingResponse(
            generate(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
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

    except Exception as e:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


