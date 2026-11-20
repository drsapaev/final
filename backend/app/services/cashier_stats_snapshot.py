"""Currency-separated cashier totals from one verified financial snapshot.

New deposit refunds use an immutable credit tied to the original payment.
Unproven external refunds require reconciliation.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import or_, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentVisit
from app.models.refund_deposit import (
    DepositTransaction,
    PaymentRefundClaim,
    RefundRequest,
)
from app.models.visit import Visit
from app.services.encounter_benefit_net import (
    BenefitQuoteError,
    _sqlite_snapshot,
    quote_from_financial_snapshot,
    require_postgres_quote_capability,
)
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    _financial_schema,
    _verify_complete_backend_reads,
)

_EXTERNAL_REFUND_READS = {
    "refund_requests": ("id", "payment_id", "status"),
    "deposit_transactions": ("id", "payment_id", "transaction_type"),
}
_DEPOSIT_TRIGGERS = {"trg_protect_deposit_refund_evidence": 31, "trg_bind_deposit_refund_claim": 5}
_DEPOSIT_GUARD_SHA256 = "4bb9c48268f38083e1c7588bb29cdcdc6057de29a82eea2671f21722f29599ab"


def _money(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result != result.quantize(Decimal("0.01")):
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=409, detail="Финансовые данные требуют сверки") from None
    return result


def _currency(value: object) -> str | None:
    if isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value.isupper():
        return value
    return None


def require_visible_external_refunds(db: Session, schema: str) -> None:
    # The SELECTs acquire relation locks before RLS and privilege checks, so
    # policy DDL cannot change the evidence visibility during this transaction.
    for table, columns in _EXTERNAL_REFUND_READS.items():
        db.execute(text(f"SELECT {', '.join(columns)} FROM {schema}.{table} WHERE false"))
    valid = db.execute(text("""
      SELECT count(*)=2 AND COALESCE(bool_and(NOT c.relrowsecurity OR (
        EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
          AND p.polpermissive AND p.polcmd IN ('r','*')
          AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
          AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
          AND NOT p.polpermissive AND p.polcmd IN ('r','*') AND EXISTS (
            SELECT 1 FROM pg_catalog.unnest(p.polroles) rid
            WHERE CASE WHEN rid=0 THEN true ELSE pg_catalog.pg_has_role(CURRENT_USER,rid,'MEMBER') END))
      )),false)
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname=:schema AND c.relname=ANY(:tables) AND c.relkind IN ('r','p')
    """), {"schema": db.get_bind().dialect.default_schema_name,
           "tables": list(_EXTERNAL_REFUND_READS)}).scalar_one()
    if valid is not True:
        raise FinancialFenceError("История возвратов временно недоступна")


def _require_deposit_refund_guard(db: Session, schema: str) -> None:
    # Hold the same relation lock through validation and snapshot collection.
    db.execute(text(f"SELECT amount, visit_id, refund_currency_snapshot FROM {schema}.deposit_transactions WHERE false"))
    rows = db.execute(text("""
      SELECT t.tgname,t.tgtype,p.prosrc
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_trigger t ON t.tgrelid=c.oid
      JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
      WHERE n.nspname=:name AND c.relname='deposit_transactions' AND c.relkind='r'
        AND c.relowner=n.nspowner AND t.tgname=ANY(:triggers)
        AND NOT t.tgisinternal AND t.tgenabled='O' AND t.tgqual IS NULL AND t.tgnargs=0
        AND p.proname='protect_deposit_refund_evidence' AND p.pronamespace=n.oid
        AND p.proowner=n.nspowner AND p.prosecdef AND p.prokind='f' AND p.provolatile='v'
        AND p.pronargs=0 AND p.prorettype='pg_catalog.trigger'::pg_catalog.regtype
        AND p.proconfig=ARRAY['search_path=pg_catalog','row_security=off']
        AND NOT pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'TRUNCATE,TRIGGER')
        AND pg_catalog.has_function_privilege(CURRENT_USER,p.oid,'EXECUTE')
        AND NOT EXISTS (
          SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
          WHERE a.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
            OR (a.grantee<>p.proowner AND a.is_grantable)
        )
    """), {"name": db.get_bind().dialect.default_schema_name, "triggers": list(_DEPOSIT_TRIGGERS)}).all()
    if ({name: kind for name, kind, _ in rows} != _DEPOSIT_TRIGGERS
            or any(sha256(body.strip().replace(f"{schema}.", "@schema@.").encode()).hexdigest()
                   != _DEPOSIT_GUARD_SHA256 for _, _, body in rows)):
        raise FinancialFenceError("История возвратов временно недоступна")


def _postgres_snapshot(db: Session, start: datetime | None, end: datetime | None, excluded: list[str]) -> dict:
    try:
        schema = _financial_schema(db)
        _verify_complete_backend_reads(db, schema)
        db.execute(text(f"SELECT method, refunded_amount FROM {schema}.payments WHERE false"))
        db.execute(text(f"SELECT amount FROM {schema}.payment_visits WHERE false"))
        require_visible_external_refunds(db, schema)
        _require_deposit_refund_guard(db, schema)
        private = require_postgres_quote_capability(db)
    except (FinancialFenceError, BenefitQuoteError):
        raise HTTPException(status_code=503, detail="Статистика временно недоступна") from None
    except DBAPIError as exc:
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if code not in {"42501", "42703"}:
            raise
        db.rollback()
        raise HTTPException(status_code=503, detail="Статистика временно недоступна") from None

    # All evidence and each STABLE benefit quote are evaluated in this one
    # statement, so READ COMMITTED uses a single MVCC snapshot.
    query = text(f"""
      WITH selected_visits AS (
        SELECT v.id,v.patient_id FROM {schema}.visits v
        WHERE v.status IS NOT NULL AND NOT (v.status=ANY(CAST(:excluded AS text[])))
          AND (CAST(:start_at AS timestamp) IS NULL OR v.created_at>=CAST(:start_at AS timestamp))
          AND (CAST(:end_at AS timestamp) IS NULL OR v.created_at<=CAST(:end_at AS timestamp))
      ), selected_payments AS (
        SELECT p.id,p.visit_id,p.amount,p.refunded_amount,p.currency,p.method,p.status,p.created_at,
          v.patient_id AS primary_patient,
          ((CAST(:start_at AS timestamp) IS NULL OR p.created_at>=CAST(:start_at AS timestamp))
            AND (CAST(:end_at AS timestamp) IS NULL OR p.created_at<=CAST(:end_at AS timestamp))) AS in_period
        FROM {schema}.payments p LEFT JOIN {schema}.visits v ON v.id=p.visit_id
        WHERE ((CAST(:start_at AS timestamp) IS NULL OR p.created_at>=CAST(:start_at AS timestamp))
          AND (CAST(:end_at AS timestamp) IS NULL OR p.created_at<=CAST(:end_at AS timestamp)))
          OR (p.status IN ('paid','completed') AND (p.visit_id IN (SELECT id FROM selected_visits)
            OR EXISTS (SELECT 1 FROM {schema}.payment_visits pv
              WHERE pv.payment_id=p.id AND pv.visit_id IN (SELECT id FROM selected_visits))))
      )
      SELECT pg_catalog.jsonb_build_object(
        'visits',COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
          'id',v.id,'patient',v.patient_id,'quote',{private}.encounter_benefit_quote(v.id)) ORDER BY v.id)
          FROM selected_visits v),'[]'::jsonb),
        'payments',COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
          'id',p.id,'visit',p.visit_id,'patient',p.primary_patient,'amount',p.amount::text,
          'refund',p.refunded_amount::text,'currency',p.currency,'method',p.method,
          'status',p.status,'period',p.in_period) ORDER BY p.id) FROM selected_payments p),'[]'::jsonb),
        'links',COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
          'payment',l.payment_id,'visit',l.visit_id,'patient',v.patient_id,'amount',l.amount::text) ORDER BY l.id)
          FROM {schema}.payment_visits l LEFT JOIN {schema}.visits v ON v.id=l.visit_id
          WHERE l.payment_id IN (SELECT id FROM selected_payments)),'[]'::jsonb),
        'external',COALESCE((SELECT pg_catalog.jsonb_agg(x.payment_id ORDER BY x.payment_id) FROM (
          SELECT r.payment_id FROM {schema}.refund_requests r
            WHERE (r.status IS NULL OR r.status NOT IN ('pending','rejected','cancelled'))
              AND r.payment_id IN (SELECT id FROM selected_payments)
          UNION ALL
          SELECT t.payment_id FROM {schema}.deposit_transactions t
            WHERE (t.transaction_type IS NULL OR t.transaction_type<>'debit')
              AND t.refund_currency_snapshot IS NULL
              AND t.payment_id IN (SELECT id FROM selected_payments)
        ) x),'[]'::jsonb),
        'deposit_refunds',COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
          'payment',t.payment_id,'visit',t.visit_id,'currency',t.refund_currency_snapshot,'amount',t.amount::text))
          FROM {schema}.deposit_transactions t
          WHERE t.refund_currency_snapshot IS NOT NULL
            AND t.payment_id IN (SELECT id FROM selected_payments)),'[]'::jsonb),
        'orphan_external', EXISTS (SELECT 1 FROM {schema}.refund_requests r
          LEFT JOIN {schema}.payments p ON p.id=r.payment_id
          WHERE (r.status IS NULL OR r.status NOT IN ('pending','rejected','cancelled')) AND p.id IS NULL)
          OR EXISTS (SELECT 1 FROM {schema}.deposit_transactions t
            LEFT JOIN {schema}.payments p ON p.id=t.payment_id
            WHERE (t.transaction_type IS NULL OR t.transaction_type<>'debit') AND p.id IS NULL)
      )
    """)
    result = db.execute(query, {"start_at": start, "end_at": end, "excluded": excluded}).scalar_one()
    if not isinstance(result, dict):
        raise HTTPException(status_code=503, detail="Статистика временно недоступна")
    return result


def _sqlite_snapshot_report(db: Session, start: datetime | None, end: datetime | None, excluded: list[str]) -> dict:
    db.execute(text("UPDATE visits SET id=id WHERE 0"))
    visits = db.query(Visit).filter(~Visit.status.in_(excluded))
    if start is not None:
        visits = visits.filter(Visit.created_at >= start)
    if end is not None:
        visits = visits.filter(Visit.created_at <= end)
    visit_rows = visits.order_by(Visit.id).populate_existing().all()
    visit_ids = {v.id for v in visit_rows}
    # SQLite writer reservation makes the following reads one stable snapshot.
    payments = db.query(Payment).populate_existing().all()
    links = db.query(PaymentVisit).populate_existing().all()
    relevant = {p.id for p in payments if (start is None or p.created_at >= start)
                and (end is None or p.created_at <= end)}
    relevant.update(p.id for p in payments if p.status in ("paid", "completed") and p.visit_id in visit_ids)
    relevant.update(link.payment_id for link in links if link.visit_id in visit_ids)
    selected = [p for p in payments if p.id in relevant]
    payment_ids = {p.id for p in selected}
    all_payment_ids = {p.id for p in payments}
    refunds = db.query(RefundRequest.id, RefundRequest.payment_id).filter(or_(
        RefundRequest.status.is_(None), ~RefundRequest.status.in_(("pending", "rejected", "cancelled")),
    )).all()
    credits = db.query(DepositTransaction).filter(
        or_(DepositTransaction.transaction_type.is_(None), DepositTransaction.transaction_type != "debit")).all()
    bound_claims = set(db.query(PaymentRefundClaim.payment_id, PaymentRefundClaim.deposit_transaction_id)
                       .filter(PaymentRefundClaim.channel == "deposit",
                               PaymentRefundClaim.refund_request_id.is_(None)).all())
    proven = []
    unproven = list(refunds)
    for credit in credits:
        if credit.refund_currency_snapshot is not None and (credit.payment_id, credit.id) in bound_claims:
            proven.append(credit)
        else:
            unproven.append((credit.id, credit.payment_id))
    patient_by_visit = {v.id: v.patient_id for v in db.query(Visit.id, Visit.patient_id).all()}
    return {
        "visits": [{"id": v.id, "patient": v.patient_id, "quote": _sqlite_snapshot(db, v.id)} for v in visit_rows],
        "payments": [{"id": p.id, "visit": p.visit_id, "patient": patient_by_visit.get(p.visit_id),
                      "amount": p.amount, "refund": p.refunded_amount, "currency": p.currency,
                      "method": p.method, "status": p.status,
                      "period": (start is None or p.created_at >= start) and (end is None or p.created_at <= end)}
                     for p in selected],
        "links": [{"payment": link.payment_id, "visit": link.visit_id, "patient": patient_by_visit.get(link.visit_id),
                   "amount": link.amount} for link in links if link.payment_id in payment_ids],
        "external": [payment_id for _, payment_id in unproven if payment_id in payment_ids],
        "deposit_refunds": [{"payment": credit.payment_id, "visit": credit.visit_id,
                             "currency": credit.refund_currency_snapshot, "amount": credit.amount}
                            for credit in proven if credit.payment_id in payment_ids],
        "orphan_external": any(payment_id not in all_payment_ids for _, payment_id in unproven),
    }


def _blank(currency: str | None) -> dict:
    return {"currency": currency, "requires_reconciliation": currency is None,
            "total_amount": Decimal("0.00"), "cash_amount": Decimal("0.00"), "card_amount": Decimal("0.00"),
            "refunded_amount": Decimal("0.00"), "net_total_amount": Decimal("0.00"),
            "net_cash_amount": Decimal("0.00"), "net_card_amount": Decimal("0.00"),
            "pending_amount": Decimal("0.00"), "paid_count": 0, "cancelled_count": 0, "pending_count": 0,
            "_gross_unknown": currency is None, "_net_unknown": False, "_pending_unknown": currency is None}


def daily_stats_from_snapshot(snapshot: object) -> list[dict]:
    if (not isinstance(snapshot, dict) or not all(isinstance(snapshot.get(k), list)
            for k in ("visits", "payments", "links", "external", "deposit_refunds"))
            or type(snapshot.get("orphan_external")) is not bool):
        raise HTTPException(status_code=503, detail="Статистика временно недоступна")
    buckets: dict[str | None, dict] = {}

    def bucket(currency: str | None) -> dict:
        if currency not in buckets:
            buckets[currency] = _blank(currency)
        return buckets[currency]

    payments = snapshot["payments"]
    if any(not isinstance(p, dict) or type(p.get("id")) is not int for p in payments):
        raise HTTPException(status_code=409, detail="Платежи требуют сверки")
    links: dict[int, list] = {}
    for link in snapshot["links"]:
        if not isinstance(link, dict) or type(link.get("payment")) is not int:
            raise HTTPException(status_code=409, detail="Распределение платежей требует сверки")
        links.setdefault(link["payment"], []).append(link)
    external = set(snapshot["external"])
    if any(type(item) is not int for item in external):
        raise HTTPException(status_code=409, detail="Возвраты требуют сверки")
    deposit_refunds = {}
    for receipt in snapshot["deposit_refunds"]:
        if not isinstance(receipt, dict) or type(receipt.get("payment")) is not int or receipt["payment"] in deposit_refunds:
            raise HTTPException(status_code=409, detail="Возвраты требуют сверки")
        deposit_refunds[receipt["payment"]] = receipt
    paid_by_visit: dict[int, Decimal] = {}
    currencies_by_visit: dict[int, set[str | None]] = {}
    uncertain_visits: set[int] = set()
    unknown_paid_period = False
    unknown_cancelled_period = False
    unknown_visit = False
    with localcontext() as context:
        context.prec = 50
        for payment in payments:
            currency = _currency(payment.get("currency"))
            amount = _money(payment.get("amount"))
            refund = _money(payment.get("refund") or "0")
            status, period = payment.get("status"), payment.get("period")
            if type(period) is not bool:
                raise HTTPException(status_code=409, detail="Период платежа требует сверки")
            item = bucket(currency) if period and status in ("paid", "completed", "cancelled", "refunded") else None
            if item is not None and status in ("cancelled", "refunded"):
                item["cancelled_count"] += 1
                if currency is None:
                    unknown_cancelled_period = True
                if payment["id"] in deposit_refunds:
                    item["_net_unknown"] = True
                    item["requires_reconciliation"] = True
            if status not in ("paid", "completed"):
                continue
            if type(payment.get("visit")) is int:
                currencies_by_visit.setdefault(payment["visit"], set()).add(currency)
            invalid_refund = refund > amount or payment["id"] in external
            settled_refund = refund
            receipt = deposit_refunds.get(payment["id"])
            if receipt is not None:
                credit = _money(receipt.get("amount"))
                invalid_refund |= (refund != 0 or credit <= 0 or credit != amount
                                   or receipt.get("currency") != currency or receipt.get("visit") != payment.get("visit"))
                settled_refund += credit
            linked = links.get(payment["id"], [])
            valid_link = not linked or (len(linked) == 1 and linked[0].get("visit") == payment.get("visit")
                                        and linked[0].get("patient") == payment.get("patient")
                                        and _money(linked[0].get("amount")) == amount)
            if item is not None:
                item["paid_count"] += 1
                if currency is None:
                    unknown_paid_period = True
                if currency is not None:
                    item["total_amount"] += amount
                    if payment.get("method") == "cash":
                        item["cash_amount"] += amount
                    elif payment.get("method") == "card":
                        item["card_amount"] += amount
                    if invalid_refund:
                        item["_net_unknown"] = True
                        item["requires_reconciliation"] = True
                    else:
                        item["refunded_amount"] += settled_refund
                        item["net_total_amount"] += amount - settled_refund
                        if payment.get("method") == "cash":
                            item["net_cash_amount"] += amount - settled_refund
                        elif payment.get("method") == "card":
                            item["net_card_amount"] += amount - settled_refund
            relevant_ids = {payment.get("visit"), *(link.get("visit") for link in linked)}
            if invalid_refund or not valid_link or currency is None or payment.get("patient") is None:
                uncertain_visits.update(visit_id for visit_id in relevant_ids if type(visit_id) is int)
            elif type(payment.get("visit")) is int:
                visit_id = payment["visit"]
                # A force-majeure transfer to a deposit does not reopen
                # the visit's receivable. Only a direct cashier refund does.
                paid_by_visit[visit_id] = paid_by_visit.get(visit_id, Decimal("0.00")) + amount - refund

        for visit in snapshot["visits"]:
            if not isinstance(visit, dict) or type(visit.get("id")) is not int:
                raise HTTPException(status_code=409, detail="Визиты требуют сверки")
            visit_id = visit["id"]
            if not isinstance(visit.get("quote"), dict) or visit["quote"].get("visible") is not True:
                raise HTTPException(status_code=503, detail="Статистика временно недоступна")
            try:
                quote = quote_from_financial_snapshot(visit.get("quote"), visit_id=visit_id)
            except BenefitQuoteError:
                unknown_visit = True
                item = bucket(None)
                item["requires_reconciliation"] = True
                item["_pending_unknown"] = True
                continue
            if quote.patient_id != visit.get("patient"):
                raise HTTPException(status_code=409, detail="Контекст визита требует сверки")
            # Zero charge has no outstanding debt in any currency, including
            # a legacy zero-price line whose currency is unknown.
            if quote.total == 0:
                continue
            item = bucket(quote.currency)
            if quote.currency is None or visit_id in uncertain_visits:
                if quote.currency is None:
                    unknown_visit = True
                item["requires_reconciliation"] = True
                item["_pending_unknown"] = True
                continue
            # Any relevant payment in a different currency is not convertible.
            if any(currency != quote.currency for currency in currencies_by_visit.get(visit_id, set())):
                item["requires_reconciliation"] = True
                item["_pending_unknown"] = True
                continue
            debt = max(quote.total - paid_by_visit.get(visit_id, Decimal("0.00")), Decimal("0.00"))
            if debt:
                item["pending_count"] += 1
                item["pending_amount"] += debt
    if snapshot["orphan_external"]:
        item = bucket(None)
        item["requires_reconciliation"] = True
        item["_net_unknown"] = True
        item["_pending_unknown"] = True
    if unknown_paid_period or unknown_cancelled_period or unknown_visit or snapshot["orphan_external"]:
        for currency, item in buckets.items():
            item["requires_reconciliation"] = True
            if currency is not None and (unknown_paid_period or snapshot["orphan_external"]):
                item["_gross_unknown"] = True
                item["_net_unknown"] = True
            if currency is not None and snapshot["orphan_external"]:
                item["_net_unknown"] = True
            if currency is not None and (unknown_visit or snapshot["orphan_external"]):
                item["_pending_unknown"] = True
    output = []
    monetary = ("total_amount", "cash_amount", "card_amount", "refunded_amount", "net_total_amount",
                "net_cash_amount", "net_card_amount", "pending_amount")
    for currency in sorted(buckets, key=lambda item: item or ""):
        item = buckets[currency]
        for field in monetary:
            uncertain = (currency is None or (item["_gross_unknown"] and field in
                         ("total_amount", "cash_amount", "card_amount")) or (item["_net_unknown"] and field in
                         ("refunded_amount", "net_total_amount", "net_cash_amount", "net_card_amount"))
                         or (item["_pending_unknown"] and field == "pending_amount"))
            item[field] = None if uncertain else format(item[field], ".2f")
        if item["_pending_unknown"]:
            item["pending_count"] = None
        if (currency is not None and item["_gross_unknown"]) or snapshot["orphan_external"]:
            item["paid_count"] = None
        if (currency is not None and unknown_cancelled_period) or snapshot["orphan_external"]:
            item["cancelled_count"] = None
        del item["_gross_unknown"], item["_net_unknown"], item["_pending_unknown"]
        output.append(item)
    return output


def cashier_daily_stats(db: Session, *, date_from: date | None, date_to: date | None,
                        excluded: tuple[str, ...]) -> list[dict]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Некорректный период")
    if db.new or db.dirty or db.deleted:
        raise HTTPException(status_code=409, detail="Сначала сохраните изменения")
    start = datetime.combine(date_from, datetime.min.time()) if date_from else None
    end = datetime.combine(date_to, datetime.max.time()) if date_to else None
    with db.no_autoflush:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            snapshot = _postgres_snapshot(db, start, end, list(excluded))
        elif dialect == "sqlite":
            snapshot = _sqlite_snapshot_report(db, start, end, list(excluded))
        else:
            raise HTTPException(status_code=503, detail="Статистика временно недоступна")
        return daily_stats_from_snapshot(snapshot)
