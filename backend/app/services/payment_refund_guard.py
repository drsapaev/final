"""Shared evidence checks for protected staff refunds."""

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.refund_deposit import DepositTransaction, RefundRequest
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    _financial_schema,
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


def require_visible_external_refunds(db: Session, schema: str) -> None:
    # Hold relation locks through policy verification and the evidence read.
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
