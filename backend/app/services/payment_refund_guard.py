"""Shared financial evidence checks for collection, refunds and repricing."""

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoiceVisit
from app.models.provider_attempt import ProviderActiveVisitReservation
from app.models.refund_deposit import (
    DepositTransaction,
    DepositTransactionType,
    RefundRequest,
)
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    _financial_schema,
    _verify_payment_reference_fence,
    require_preflighted_payment_visits,
)

CASHIER_IMMEDIATE_PAID_METHODS = frozenset({"cash", "card"})

_EXTERNAL_REFUND_READS = {
    "refund_requests": ("id", "payment_id", "status"),
    "deposit_transactions": ("id", "payment_id", "transaction_type"),
}


def recorded_payment_currency(value: object) -> str | None:
    if isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value.isupper():
        return value
    return None


def local_refund_requires_reconciliation(payment: Payment) -> bool:
    return (
        bool(payment.provider or payment.provider_payment_id)
        or payment.method not in CASHIER_IMMEDIATE_PAID_METHODS
        or recorded_payment_currency(payment.currency) is None
    )


def _require_visible_evidence(db: Session, schema: str, reads: dict[str, tuple[str, ...]], message: str) -> None:
    # Hold relation locks through policy verification and the evidence read.
    for table, columns in reads.items():
        db.execute(text(f"SELECT {', '.join(columns)} FROM {schema}.{table} WHERE false"))
    valid = db.execute(text("""
      SELECT count(*)=:expected AND COALESCE(bool_and(NOT c.relrowsecurity OR (
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
        AND pg_catalog.to_regclass(pg_catalog.quote_ident(c.relname)) = c.oid
    """), {"schema": db.get_bind().dialect.default_schema_name,
           "tables": list(reads), "expected": len(reads)}).scalar_one()
    if valid is not True:
        raise FinancialFenceError(message)


def require_visible_external_refunds(db: Session, schema: str) -> None:
    _require_visible_evidence(db, schema, _EXTERNAL_REFUND_READS, "История возвратов временно недоступна")


def _require_visible_current_schema(
    db: Session, reads: dict[str, tuple[str, ...]], message: str,
) -> None:
    dialect = db.get_bind().dialect
    if dialect.name != "postgresql":
        return
    schema = dialect.default_schema_name
    isolation = db.execute(text("SELECT pg_catalog.current_setting('transaction_isolation')")).scalar_one()
    if schema is None or isolation != "read committed":
        raise FinancialFenceError(message)
    _require_visible_evidence(db, dialect.identifier_preparer.quote_schema(schema), reads, message)


def require_visible_visit_payments(db: Session) -> None:
    _require_visible_current_schema(
        db,
        {
            "payments": ("id", "visit_id", "status"),
            "payment_visits": ("payment_id", "visit_id"),
            "payment_invoices": ("id", "status"),
            "payment_invoice_visits": ("invoice_id", "visit_id", "visit_amount"),
            "provider_active_visit_reservations": ("visit_id",),
        },
        "История платежей визита требует сверки",
    )


def require_visible_checkout_queue(db: Session) -> None:
    _require_visible_current_schema(
        db, {"queue_entries": ("id", "visit_id", "status")},
        "Состояние очереди визита требует сверки",
    )


def require_visible_unpaid_draft_evidence(db: Session) -> None:
    _require_visible_current_schema(
        db,
        {
            "deposit_transactions": ("visit_id",),
            "refund_requests": ("visit_id",),
            "queue_entries": ("visit_id", "diagnostics_started_at", "served_at"),
        },
        "История обслуживания или возвратов требует сверки",
    )


def _require_clear_debit_history(
    db: Session, visit_ids: tuple[int, ...], schema: str | None,
) -> None:
    if schema is not None:
        _require_visible_evidence(
            db, schema,
            {"deposit_transactions": ("id", "visit_id", "payment_id", "transaction_type")},
            "История списаний с депозита временно недоступна",
        )
    history = db.query(DepositTransaction.id).filter(
        DepositTransaction.visit_id.in_(visit_ids),
        DepositTransaction.payment_id.is_(None),
        DepositTransaction.transaction_type == DepositTransactionType.DEBIT.value,
    ).first()
    if history is not None:
        raise FinancialFenceError("Историческое списание с депозита требует сверки")


def require_clear_visit_debit_history(db: Session, visit_id: int) -> None:
    """Use the locked financial closure before accepting new funds."""
    visit_ids = require_preflighted_payment_visits(db, visit_id)
    schema = _financial_schema(db) if db.get_bind().dialect.name == "postgresql" else None
    _require_clear_debit_history(db, visit_ids, schema)


def require_unbilled_visit_group(db: Session, visit_id: int) -> None:
    """Check financial evidence after the caller locks the complete visit group."""
    visit_ids = require_preflighted_payment_visits(db, visit_id)
    schema = _financial_schema(db) if db.get_bind().dialect.name == "postgresql" else None
    if schema is not None:
        _verify_payment_reference_fence(db, schema)

    if (
        db.query(Payment.id).filter(Payment.visit_id.in_(visit_ids)).first()
        or db.query(PaymentVisit.id).filter(PaymentVisit.visit_id.in_(visit_ids)).first()
        or db.query(PaymentInvoiceVisit.id).filter(PaymentInvoiceVisit.visit_id.in_(visit_ids)).first()
        or db.query(ProviderActiveVisitReservation.visit_id)
        .filter(ProviderActiveVisitReservation.visit_id.in_(visit_ids))
        .first()
    ):
        raise FinancialFenceError("По визиту есть финансовые операции. Обратитесь в кассу")

    _require_clear_debit_history(db, visit_ids, schema)


def lock_refund_evidence(db: Session) -> None:
    """Pin evidence visibility before acquiring the visit and payment locks."""
    if db.get_bind().dialect.name == "postgresql":
        if db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
            raise FinancialFenceError("История возвратов временно недоступна")
        require_visible_external_refunds(db, _financial_schema(db))
    else:
        db.execute(text("UPDATE payments SET id=id WHERE 0"))


def has_external_refund(db: Session, payment_id: int) -> bool:
    """Check other refund channels while holding this payment's lock."""
    external_request = db.query(RefundRequest.id).filter(
        RefundRequest.payment_id == payment_id,
        or_(RefundRequest.status.is_(None), RefundRequest.status.not_in(("rejected", "cancelled"))),
    ).first()
    if external_request is not None:
        return True
    deposit_credit = db.query(DepositTransaction.id).filter(
        DepositTransaction.payment_id == payment_id,
        or_(DepositTransaction.transaction_type.is_(None), DepositTransaction.transaction_type != "debit"),
    ).first()
    return deposit_credit is not None
