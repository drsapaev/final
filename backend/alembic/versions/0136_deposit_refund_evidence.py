"""Record new, settled deposit refunds with immutable currency evidence."""

import sqlalchemy as sa

from alembic import op

revision = "0136_deposit_refund_evidence"
down_revision = "0135_registrar_benefit_decision"
branch_labels = None
depends_on = None

_TABLE = "deposit_transactions"
_CURRENCY = "refund_currency_snapshot"
_CHECK = "ck_deposit_refund_currency"
_FUNCTION = "protect_deposit_refund_evidence"
_GUARD = "trg_protect_deposit_refund_evidence"
_BIND = "trg_bind_deposit_refund_claim"
_VALID = """
      NEW.refund_currency_snapshot='UZS' AND NEW.transaction_type='credit'
      AND NEW.payment_id IS NOT NULL AND NEW.visit_id IS NOT NULL
      AND NEW.refund_request_id IS NULL AND NEW.amount>0 AND NEW.amount<=9999999999.99
"""
_PAYMENT = """
      p.id=NEW.payment_id AND p.visit_id=NEW.visit_id AND p.status='paid'
      AND p.currency=NEW.refund_currency_snapshot AND p.amount=NEW.amount
      AND COALESCE(p.refunded_amount,0)=0
"""
_IDENTITY = (
    "id", "deposit_id", "transaction_type", "payment_id", "visit_id",
    "refund_request_id", "amount", "balance_after", "description", "created_at",
)


def _quoted_schema() -> tuple[str, str]:
    context = op.get_context()
    name = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not name:
        raise RuntimeError("Trusted application schema required")
    return name, context.dialect.identifier_preparer.quote_schema(name)


def _delimiter(quoted: str) -> str:
    delimiter = "$deposit_refund$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"
    return delimiter


def _postgres_body(quoted: str) -> str:
    return f"""
    DECLARE
      subject_id integer;
      linked_visits integer;
      full_visit_payment boolean;
    BEGIN
      IF TG_OP='DELETE' THEN
        IF OLD.{_CURRENCY} IS NOT NULL THEN
          RAISE EXCEPTION 'immutable deposit refund evidence' USING ERRCODE='23514';
        END IF;
        RETURN OLD;
      ELSIF TG_OP='UPDATE' THEN
        IF NEW.{_CURRENCY} IS DISTINCT FROM OLD.{_CURRENCY}
          OR (OLD.{_CURRENCY} IS NOT NULL AND (
            (pg_catalog.to_jsonb(NEW)-'performed_by') IS DISTINCT FROM (pg_catalog.to_jsonb(OLD)-'performed_by')
            OR (NEW.performed_by IS DISTINCT FROM OLD.performed_by AND NEW.performed_by IS NOT NULL))) THEN
          RAISE EXCEPTION 'immutable deposit refund evidence' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF NEW.{_CURRENCY} IS NULL THEN RETURN NEW; END IF;

      IF pg_catalog.has_function_privilege(SESSION_USER, (
        SELECT t.tgfoid FROM pg_catalog.pg_trigger t WHERE t.tgrelid=TG_RELID AND t.tgname=TG_NAME
      ), 'EXECUTE') IS NOT TRUE THEN
        RAISE EXCEPTION 'deposit refund capability required' USING ERRCODE='42501';
      END IF;
      IF TG_WHEN='AFTER' THEN
        UPDATE {quoted}.payment_refund_claims SET deposit_transaction_id=NEW.id
        WHERE payment_id=NEW.payment_id AND channel='deposit'
          AND deposit_transaction_id IS NULL AND refund_request_id IS NULL;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'deposit refund claim unavailable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;

      IF ({_VALID}) IS NOT TRUE THEN
        RAISE EXCEPTION 'invalid deposit refund evidence' USING ERRCODE='23514';
      END IF;
      -- The application may already hold the payment lock. Never wait for
      -- a visit editor which could be waiting for that payment.
      SELECT v.patient_id INTO subject_id FROM {quoted}.visits v
        WHERE v.id=NEW.visit_id FOR SHARE NOWAIT;
      IF subject_id IS NULL THEN
        RAISE EXCEPTION 'invalid deposit refund evidence' USING ERRCODE='23514';
      END IF;
      -- Hold the payment against new FK allocations while checking its links.
      PERFORM 1 FROM {quoted}.payments p WHERE {_PAYMENT} FOR UPDATE NOWAIT;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid deposit refund evidence' USING ERRCODE='23514';
      END IF;
      SELECT count(*), COALESCE(bool_and(visit_id=NEW.visit_id AND amount=NEW.amount),true)
      INTO linked_visits, full_visit_payment
      FROM (
        SELECT visit_id,amount FROM {quoted}.payment_visits
        WHERE payment_id=NEW.payment_id ORDER BY id LIMIT 2 FOR SHARE NOWAIT
      ) AS links;
      IF linked_visits>1 OR NOT full_visit_payment THEN
        RAISE EXCEPTION 'invalid deposit refund evidence' USING ERRCODE='23514';
      END IF;
      UPDATE {quoted}.patient_deposits SET balance=balance+NEW.amount,
        updated_at=pg_catalog.statement_timestamp()
        WHERE id=NEW.deposit_id AND patient_id=subject_id
          AND currency=NEW.{_CURRENCY} AND balance BETWEEN 0 AND 9999999999.99-NEW.amount
        RETURNING balance INTO NEW.balance_after;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'invalid deposit refund evidence' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END
    """


def _install_postgres_guards(quoted: str) -> None:
    delimiter = _delimiter(quoted)
    op.execute(f"""
      CREATE FUNCTION {quoted}.{_FUNCTION}() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=off
      AS {delimiter}{_postgres_body(quoted)}{delimiter}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {quoted}.{_FUNCTION}() FROM PUBLIC")
    op.execute(f"""
      CREATE TRIGGER {_GUARD} BEFORE INSERT OR UPDATE OR DELETE ON {quoted}.{_TABLE}
        FOR EACH ROW EXECUTE FUNCTION {quoted}.{_FUNCTION}()
    """)
    op.execute(f"""
      CREATE TRIGGER {_BIND} AFTER INSERT ON {quoted}.{_TABLE}
        FOR EACH ROW EXECUTE FUNCTION {quoted}.{_FUNCTION}()
    """)


def _install_sqlite_guards() -> None:
    changed = " OR ".join(f"NEW.{key} IS NOT OLD.{key}" for key in _IDENTITY)
    op.execute(f"""
      CREATE TRIGGER {_GUARD}_insert BEFORE INSERT ON {_TABLE}
      WHEN NEW.{_CURRENCY} IS NOT NULL AND (({_VALID}) IS NOT TRUE OR NOT EXISTS (
        SELECT 1 FROM payments p JOIN visits v ON v.id=p.visit_id
        JOIN patient_deposits d ON d.patient_id=v.patient_id
        WHERE {_PAYMENT} AND d.id=NEW.deposit_id AND d.currency=NEW.{_CURRENCY}
          AND d.balance=NEW.balance_after
      )) BEGIN SELECT RAISE(ABORT,'invalid deposit refund evidence'); END
    """)
    op.execute(f"""
      CREATE TRIGGER {_GUARD}_update BEFORE UPDATE ON {_TABLE}
      WHEN NEW.{_CURRENCY} IS NOT OLD.{_CURRENCY} OR (OLD.{_CURRENCY} IS NOT NULL AND (
        {changed} OR (NEW.performed_by IS NOT OLD.performed_by AND NEW.performed_by IS NOT NULL)))
      BEGIN SELECT RAISE(ABORT,'immutable deposit refund evidence'); END
    """)
    op.execute(f"""
      CREATE TRIGGER {_GUARD}_delete BEFORE DELETE ON {_TABLE} WHEN OLD.{_CURRENCY} IS NOT NULL
      BEGIN SELECT RAISE(ABORT,'immutable deposit refund evidence'); END
    """)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    currency_check = f"{_CURRENCY} IS NULL OR {_CURRENCY}='UZS'"
    if dialect == "postgresql":
        name, quoted = _quoted_schema()
        op.add_column(_TABLE, sa.Column(_CURRENCY, sa.String(3)), schema=name)
        op.create_check_constraint(_CHECK, _TABLE, currency_check, schema=name)
        _install_postgres_guards(quoted)
    elif dialect == "sqlite":
        op.add_column(_TABLE, sa.Column(_CURRENCY, sa.String(3), sa.CheckConstraint(currency_check, name=_CHECK)))
        _install_sqlite_guards()
    else:
        raise RuntimeError("Unsupported deposit refund evidence dialect")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        name, quoted = _quoted_schema()
        delimiter = _delimiter(quoted)
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {quoted}.{_TABLE} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""DO {delimiter} BEGIN
          IF EXISTS (SELECT 1 FROM {quoted}.{_TABLE} WHERE {_CURRENCY} IS NOT NULL) THEN
            RAISE EXCEPTION 'deposit refund evidence prevents downgrade';
          END IF;
        END {delimiter}""")
        op.execute(f"DROP TRIGGER {_BIND} ON {quoted}.{_TABLE}")
        op.execute(f"DROP TRIGGER {_GUARD} ON {quoted}.{_TABLE}")
        op.execute(f"DROP FUNCTION {quoted}.{_FUNCTION}()")
        op.drop_constraint(_CHECK, _TABLE, type_="check", schema=name)
        op.drop_column(_TABLE, _CURRENCY, schema=name)
    elif dialect == "sqlite":
        op.execute(f"UPDATE {_TABLE} SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE deposit_refund_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute(f"""
          INSERT INTO deposit_refund_downgrade_guard SELECT CASE WHEN EXISTS (
            SELECT 1 FROM {_TABLE} WHERE {_CURRENCY} IS NOT NULL
          ) THEN 0 ELSE 1 END
        """)
        op.execute("DROP TABLE deposit_refund_downgrade_guard")
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER {_GUARD}_{event}")
        op.drop_column(_TABLE, _CURRENCY)
    else:
        raise RuntimeError("Unsupported deposit refund evidence dialect")
