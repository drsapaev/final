"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from cashier.py (1787 LOC god file → modular).
"""
from __future__ import annotations

from decimal import localcontext

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.trusted_financial_auth import _authenticate
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
from app.services.cashier_stats_snapshot import cashier_daily_stats
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    _financial_schema,
    _verify_complete_backend_reads,
)


async def _hourly_actor(
    token: str = Depends(deps.oauth2_scheme), db: Session = Depends(deps.get_db),
) -> User:
    """Pin the trusted schema before the shared authentication reads."""
    return await _authenticate(token, db, ("Admin", "Cashier"))


class DailyCurrencyStatItem(BaseModel):
    currency: str | None = Field(description="Код валюты; null означает неизвестную валюту")
    requires_reconciliation: bool
    total_amount: str | None
    cash_amount: str | None
    card_amount: str | None
    refunded_amount: str | None
    net_total_amount: str | None
    net_cash_amount: str | None
    net_card_amount: str | None
    pending_amount: str | None
    paid_count: int | None
    cancelled_count: int | None
    pending_count: int | None


@router.get("/stats", response_model=CashierStatsResponse)
async def get_cashier_stats(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_hourly_actor),
    date_from: date | None = Query(None, description="Дата начала"),
    date_to: date | None = Query(None, description="Дата окончания"),
):
    """Keep legacy UZS totals only when the full snapshot proves them."""
    try:
        buckets = cashier_daily_stats(db, date_from=date_from, date_to=date_to,
                                      excluded=CASHIER_PENDING_EXCLUDED_VISIT_STATUSES)
        if not buckets:
            return CashierStatsResponse(total_amount=0, cash_amount=0, card_amount=0, refunded_amount=0,
                                        net_total_amount=0, net_cash_amount=0, net_card_amount=0,
                                        pending_count=0, pending_amount=0, paid_count=0, cancelled_count=0)
        if len(buckets) != 1 or buckets[0]["currency"] != "UZS" or buckets[0]["requires_reconciliation"]:
            raise HTTPException(status_code=409, detail="Статистика требует разбивки по валютам или сверки")
        return CashierStatsResponse(**buckets[0])
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/stats/by-currency", response_model=list[DailyCurrencyStatItem])
async def get_cashier_stats_by_currency(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_hourly_actor),
    date_from: date | None = Query(None, description="Дата начала"),
    date_to: date | None = Query(None, description="Дата окончания"),
) -> list[dict[str, Any]]:
    """Return separate buckets; null amounts require explicit reconciliation."""
    try:
        return cashier_daily_stats(db, date_from=date_from, date_to=date_to,
                                   excluded=CASHIER_PENDING_EXCLUDED_VISIT_STATUSES)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled cashier currency report error")
        raise HTTPException(status_code=500, detail="Internal server error") from None


class HourlyCurrencyStatItem(BaseModel):
    hour: int = Field(ge=0, le=23)
    currency: str | None = Field(description="Код валюты платежа; null означает неизвестную валюту")
    count: int | None = Field(gt=0, description="Количество; null при неполной разбивке")
    amount: str | None = Field(pattern=r"^\d+\.\d{2}$", description="Точная сумма; null для неизвестной валюты")
    requires_reconciliation: bool


def _hourly_currency_buckets(db: Session, target_date: date) -> dict[tuple[int, str | None], tuple[int, Decimal | None]]:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        try:
            schema = _financial_schema(db)
            _verify_complete_backend_reads(db, schema)
            db.execute(text(f"SELECT created_at, currency, amount FROM {schema}.payments WHERE false"))
        except FinancialFenceError:
            raise HTTPException(status_code=503, detail="Статистика временно недоступна") from None
        except DBAPIError as exc:
            sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            if sqlstate != "42501":
                raise
            db.rollback()
            raise HTTPException(status_code=503, detail="Статистика временно недоступна") from None
    elif dialect != "sqlite":
        raise HTTPException(status_code=503, detail="Статистика временно недоступна")

    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    # One SQL statement gives all rows a single READ COMMITTED snapshot.
    rows = db.query(Payment.created_at, Payment.currency, Payment.amount).filter(
        Payment.created_at >= start_of_day,
        Payment.created_at <= end_of_day,
        Payment.status.in_(["paid", "completed"]),
    ).all()
    buckets: dict[tuple[int, str | None], tuple[int, Decimal | None]] = {}
    with localcontext() as context:
        context.prec = 50
        for created_at, currency, raw_amount in rows:
            amount = Decimal(str(raw_amount))
            if (not isinstance(created_at, datetime) or not amount.is_finite() or amount < 0
                    or amount != amount.quantize(Decimal("0.01"))):
                raise HTTPException(status_code=409, detail="Данные статистики требуют сверки")
            known = (isinstance(currency, str) and len(currency) == 3 and currency.isascii()
                     and currency.isalpha() and currency.isupper())
            key = (created_at.hour, currency if known else None)
            if key[1] is None:
                # Unknown labels do not prove these payments share a currency.
                count, _ = buckets.get(key, (0, None))
                buckets[key] = (count + 1, None)
            else:
                count, total = buckets.get(key, (0, Decimal("0.00")))
                if total is None:
                    raise HTTPException(status_code=409, detail="Данные статистики требуют сверки")
                buckets[key] = (count + 1, total + amount)
    return buckets


@router.get("/stats/hourly", response_model=list[HourlyStatItem])
async def get_hourly_stats(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_hourly_actor),
    target_date: date | None = Query(None, description="Дата для статистики (по умолчанию сегодня)"),
):
    """
    Получить почасовую статистику платежей за день.
    """
    try:
        if not target_date:
            target_date = date.today()

        buckets = _hourly_currency_buckets(db, target_date)
        if any(currency != "UZS" for _, currency in buckets):
            raise HTTPException(status_code=409, detail="Для статистики требуется разбивка по валютам")
        return [HourlyStatItem(hour=hour, count=buckets.get((hour, "UZS"), (0, Decimal("0.00")))[0],
                               amount=buckets.get((hour, "UZS"), (0, Decimal("0.00")))[1]) for hour in range(24)]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/stats/hourly/by-currency", response_model=list[HourlyCurrencyStatItem])
async def get_hourly_stats_by_currency(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_hourly_actor),
    target_date: date | None = Query(None, description="Дата статистики"),
) -> list[dict[str, Any]]:
    """Return only observed hours; unknown currency is explicitly null."""
    try:
        buckets = _hourly_currency_buckets(db, target_date or date.today())
        incomplete_hours = {hour for hour, currency in buckets if currency is None}
        return [{"hour": hour, "currency": currency,
                 "count": None if currency is not None and hour in incomplete_hours else count,
                 "amount": format(amount, ".2f") if amount is not None and hour not in incomplete_hours else None,
                 "requires_reconciliation": hour in incomplete_hours}
                for (hour, currency), (count, amount) in sorted(
                    buckets.items(), key=lambda item: (item[0][0], item[0][1] or ""))]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled cashier hourly currency report error")
        raise HTTPException(status_code=500, detail="Internal server error") from None


