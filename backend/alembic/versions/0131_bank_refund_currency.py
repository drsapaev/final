"""Preserve the currency of a new automatic bank refund request."""

import sqlalchemy as sa

from alembic import op

revision = "0131_bank_refund_currency"
down_revision = "0130_invitation_nonce_guard"
branch_labels = None
depends_on = None

_TABLE = "refund_requests"
_CURRENCY = "payment_currency_snapshot"
_TRIGGER = "trg_protect_bank_refund_evidence"
_IDENTITY_FIELDS = (
    "payment_id", "patient_id", "original_amount", "refund_amount", "commission_amount",
    "refund_type", "is_automatic", "created_at",
)
_PAID_PAYMENT = """
      WHERE p.id=NEW.payment_id AND v.patient_id=NEW.patient_id
        AND (NEW.visit_id IS NULL OR p.visit_id=NEW.visit_id)
        AND p.status='paid' AND p.currency=NEW.payment_currency_snapshot
        AND p.amount=NEW.original_amount
        AND COALESCE(p.refunded_amount,0)>=0 AND NEW.refund_amount>0
        AND NEW.refund_amount<=p.amount-COALESCE(p.refunded_amount,0)
"""
_NEW_BANK_REQUEST = """
      NEW.is_automatic=true AND NEW.refund_type='bank_transfer'
      AND NEW.status='pending' AND NEW.commission_amount=0
"""


def _target() -> tuple[str, str, str]:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    quoted = context.dialect.identifier_preparer.quote_schema(schema)
    delimiter = "$bank_refund_evidence$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"
    return schema, quoted, delimiter


def _postgres_guard(quoted: str, delimiter: str) -> None:
    new_identity = ",".join(f"NEW.{field}" for field in _IDENTITY_FIELDS)
    old_identity = ",".join(f"OLD.{field}" for field in _IDENTITY_FIELDS)
    op.execute(f"""
      CREATE FUNCTION {quoted}.protect_bank_refund_evidence() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS {delimiter}
      BEGIN
        IF TG_OP='DELETE' THEN
          IF OLD.{_CURRENCY} IS NOT NULL THEN RAISE EXCEPTION 'immutable bank refund evidence'; END IF;
          RETURN OLD;
        END IF;
        IF TG_OP='UPDATE' THEN
          IF NEW.{_CURRENCY} IS DISTINCT FROM OLD.{_CURRENCY}
            OR (OLD.{_CURRENCY} IS NOT NULL AND (
              ROW({new_identity}) IS DISTINCT FROM ROW({old_identity})
              OR (NEW.visit_id IS DISTINCT FROM OLD.visit_id AND NEW.visit_id IS NOT NULL)
              OR (NEW.status IS DISTINCT FROM OLD.status AND NOT (
                OLD.status='pending' AND NEW.status IN ('rejected','cancelled'))))) THEN
            RAISE EXCEPTION 'immutable bank refund evidence';
          END IF;
          RETURN NEW;
        END IF;
        IF NEW.{_CURRENCY} IS NOT NULL THEN
          IF ({_NEW_BANK_REQUEST}) IS NOT TRUE OR NOT EXISTS (
            SELECT 1 FROM {quoted}.payments p JOIN {quoted}.visits v ON v.id=p.visit_id
            {_PAID_PAYMENT} FOR NO KEY UPDATE OF p
          ) THEN RAISE EXCEPTION 'invalid bank refund evidence'; END IF;
        END IF;
        RETURN NEW;
      END {delimiter}
    """)
    op.execute(f"""
      CREATE TRIGGER {_TRIGGER} BEFORE INSERT OR UPDATE OR DELETE ON {quoted}.{_TABLE}
      FOR EACH ROW EXECUTE FUNCTION {quoted}.protect_bank_refund_evidence()
    """)


def _sqlite_guard() -> None:
    changed = " OR ".join(f"NEW.{field} IS NOT OLD.{field}" for field in _IDENTITY_FIELDS)
    op.execute(f"""
      CREATE TRIGGER {_TRIGGER}_insert BEFORE INSERT ON {_TABLE}
      WHEN NEW.{_CURRENCY} IS NOT NULL AND (({_NEW_BANK_REQUEST}) IS NOT TRUE OR NOT EXISTS (
        SELECT 1 FROM payments p JOIN visits v ON v.id=p.visit_id {_PAID_PAYMENT}
      ))
      BEGIN SELECT RAISE(ABORT,'invalid bank refund evidence'); END
    """)
    op.execute(f"""
      CREATE TRIGGER {_TRIGGER}_update BEFORE UPDATE ON {_TABLE}
      WHEN NEW.{_CURRENCY} IS NOT OLD.{_CURRENCY} OR (OLD.{_CURRENCY} IS NOT NULL AND (
        {changed} OR (NEW.visit_id IS NOT OLD.visit_id AND NEW.visit_id IS NOT NULL)
        OR (NEW.status IS NOT OLD.status AND NOT (OLD.status='pending' AND NEW.status IN ('rejected','cancelled')))))
      BEGIN SELECT RAISE(ABORT,'immutable bank refund evidence'); END
    """)
    op.execute(f"""
      CREATE TRIGGER {_TRIGGER}_delete BEFORE DELETE ON {_TABLE} WHEN OLD.{_CURRENCY} IS NOT NULL
      BEGIN SELECT RAISE(ABORT,'immutable bank refund evidence'); END
    """)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema, quoted, delimiter = _target()
        op.add_column(_TABLE, sa.Column(_CURRENCY, sa.String(3)), schema=schema)
        op.create_check_constraint(
            "ck_bank_refund_currency", _TABLE, f"{_CURRENCY} COLLATE \"C\" ~ '^[A-Z]{{3}}$'", schema=schema,
        )
        _postgres_guard(quoted, delimiter)
    elif dialect == "sqlite":
        op.add_column(_TABLE, sa.Column(_CURRENCY, sa.String(3), sa.CheckConstraint(
            f"{_CURRENCY} GLOB '[A-Z][A-Z][A-Z]'", name="ck_bank_refund_currency",
        )))
        _sqlite_guard()
    else:
        raise RuntimeError("Unsupported bank refund currency dialect")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema, quoted, delimiter = _target()
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {quoted}.{_TABLE} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""DO {delimiter} BEGIN
          IF EXISTS (SELECT 1 FROM {quoted}.{_TABLE} WHERE {_CURRENCY} IS NOT NULL) THEN
            RAISE EXCEPTION 'bank refund evidence prevents downgrade';
          END IF;
        END {delimiter}""")
        op.execute(f"DROP TRIGGER {_TRIGGER} ON {quoted}.{_TABLE}")
        op.execute(f"DROP FUNCTION {quoted}.protect_bank_refund_evidence()")
        op.drop_constraint("ck_bank_refund_currency", _TABLE, type_="check", schema=schema)
        op.drop_column(_TABLE, _CURRENCY, schema=schema)
    elif dialect == "sqlite":
        op.execute(f"UPDATE {_TABLE} SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE bank_currency_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute(f"""INSERT INTO bank_currency_downgrade_guard SELECT CASE WHEN EXISTS (
          SELECT 1 FROM {_TABLE} WHERE {_CURRENCY} IS NOT NULL) THEN 0 ELSE 1 END""")
        op.execute("DROP TABLE bank_currency_downgrade_guard")
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER {_TRIGGER}_{event}")
        op.drop_column(_TABLE, _CURRENCY)
    else:
        raise RuntimeError("Unsupported bank refund currency dialect")
