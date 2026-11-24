"""Bind manual deposit mutations to durable, immutable receipts."""

import sqlalchemy as sa

from alembic import op

revision = "0137_deposit_manual_receipts"
down_revision = "0136_deposit_refund_evidence"
branch_labels = None
depends_on = None

_TABLE = "deposit_transactions"
_INDEX = "uq_deposit_manual_request"
_GUARD = "trg_protect_manual_deposit_receipt"
_FUNCTION = "protect_manual_deposit_receipt"
_COMMAND_FIELDS = ("client_request_id", "command_fingerprint", "command_currency", "command_is_active")
_NO_COMMAND = " AND ".join(f"NEW.{field} IS NULL" for field in _COMMAND_FIELDS)
_IDENTITY = (
    "id", "deposit_id", "transaction_type", "amount", "balance_after", "description",
    "refund_request_id", "payment_id", "visit_id", "created_at", "refund_currency_snapshot",
    *_COMMAND_FIELDS,
)
_MANUAL_RECEIPT = """
    NEW.client_request_id IS NOT NULL AND length(NEW.command_fingerprint)=64
    AND length(NEW.command_currency) BETWEEN 1 AND 8 AND NEW.command_is_active IS NOT NULL
    AND NEW.performed_by IS NOT NULL AND NEW.amount>0 AND NEW.balance_after>=0
    AND NEW.refund_request_id IS NULL AND NEW.refund_currency_snapshot IS NULL
    AND (
      NEW.transaction_type='debit'
      OR (NEW.transaction_type='credit' AND NEW.visit_id IS NULL AND NEW.payment_id IS NULL)
    )
"""


def _schema() -> tuple[str, str]:
    context = op.get_context()
    name = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not name:
        raise RuntimeError("Trusted application schema required")
    return name, context.dialect.identifier_preparer.quote_schema(name)


def _install_postgresql_guard(quoted: str) -> None:
    op.execute(f"""
      CREATE FUNCTION {quoted}.{_FUNCTION}() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $manual_deposit$
      BEGIN
        IF TG_OP='INSERT' THEN
          IF (({_NO_COMMAND}) OR ({_MANUAL_RECEIPT})) IS NOT TRUE THEN
            RAISE EXCEPTION 'invalid manual deposit receipt' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END IF;
        IF TG_OP='DELETE' THEN
          IF OLD.client_request_id IS NOT NULL THEN
            RAISE EXCEPTION 'immutable manual deposit receipt' USING ERRCODE='23514';
          END IF;
          RETURN OLD;
        END IF;
        IF (OLD.client_request_id IS NULL AND NOT ({_NO_COMMAND}))
          OR (OLD.client_request_id IS NOT NULL AND (
            (pg_catalog.to_jsonb(NEW)-'performed_by') IS DISTINCT FROM (pg_catalog.to_jsonb(OLD)-'performed_by')
            OR (NEW.performed_by IS DISTINCT FROM OLD.performed_by AND NEW.performed_by IS NOT NULL))) THEN
          RAISE EXCEPTION 'immutable manual deposit receipt' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $manual_deposit$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {quoted}.{_FUNCTION}() FROM PUBLIC")
    op.execute(f"""
      CREATE TRIGGER {_GUARD} BEFORE INSERT OR UPDATE OR DELETE ON {quoted}.{_TABLE}
      FOR EACH ROW EXECUTE FUNCTION {quoted}.{_FUNCTION}()
    """)


def _install_sqlite_guards() -> None:
    changed = " OR ".join(f"NEW.{field} IS NOT OLD.{field}" for field in _IDENTITY)
    op.execute(f"""
      CREATE TRIGGER {_GUARD}_insert BEFORE INSERT ON {_TABLE}
      WHEN (({_NO_COMMAND}) OR ({_MANUAL_RECEIPT})) IS NOT TRUE
      BEGIN SELECT RAISE(ABORT, 'invalid manual deposit receipt'); END
    """)
    op.execute(f"""
      CREATE TRIGGER {_GUARD}_update BEFORE UPDATE ON {_TABLE}
      WHEN (OLD.client_request_id IS NULL AND NOT ({_NO_COMMAND}))
        OR (OLD.client_request_id IS NOT NULL AND (
          {changed} OR (NEW.performed_by IS NOT OLD.performed_by AND NEW.performed_by IS NOT NULL)))
      BEGIN SELECT RAISE(ABORT, 'immutable manual deposit receipt'); END
    """)
    op.execute(f"""
      CREATE TRIGGER {_GUARD}_delete BEFORE DELETE ON {_TABLE}
      WHEN OLD.client_request_id IS NOT NULL
      BEGIN SELECT RAISE(ABORT, 'immutable manual deposit receipt'); END
    """)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported manual deposit receipt dialect")
    name = _schema()[0] if dialect == "postgresql" else None
    for column in (
        sa.Column("client_request_id", sa.Uuid()),
        sa.Column("command_fingerprint", sa.String(64)),
        sa.Column("command_currency", sa.String(8)),
        sa.Column("command_is_active", sa.Boolean()),
    ):
        op.add_column(_TABLE, column, schema=name)
    op.create_index(
        _INDEX, _TABLE, ["client_request_id"], unique=True, schema=name,
        postgresql_where=sa.text("client_request_id IS NOT NULL"),
        sqlite_where=sa.text("client_request_id IS NOT NULL"),
    )
    if dialect == "postgresql":
        _install_postgresql_guard(_schema()[1])
    else:
        _install_sqlite_guards()


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        name, quoted = _schema()
        delimiter = "$manual_deposit_rollback$"
        while delimiter in quoted:
            delimiter = delimiter[:-1] + "_x$"
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {quoted}.{_TABLE} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""DO {delimiter} BEGIN
          IF EXISTS (SELECT 1 FROM {quoted}.{_TABLE} WHERE client_request_id IS NOT NULL) THEN
            RAISE EXCEPTION 'manual deposit receipts prevent downgrade';
          END IF;
        END {delimiter}""")
        op.execute(f"DROP TRIGGER {_GUARD} ON {quoted}.{_TABLE}")
        op.execute(f"DROP FUNCTION {quoted}.{_FUNCTION}()")
    elif dialect == "sqlite":
        name = None
        op.execute(f"UPDATE {_TABLE} SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE manual_deposit_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute(f"""
          INSERT INTO manual_deposit_downgrade_guard SELECT CASE WHEN EXISTS (
            SELECT 1 FROM {_TABLE} WHERE client_request_id IS NOT NULL
          ) THEN 0 ELSE 1 END
        """)
        op.execute("DROP TABLE manual_deposit_downgrade_guard")
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER {_GUARD}_{event}")
    else:
        raise RuntimeError("Unsupported manual deposit receipt dialect")
    op.drop_index(_INDEX, table_name=_TABLE, schema=name)
    for field in reversed(_COMMAND_FIELDS):
        op.drop_column(_TABLE, field, schema=name)
