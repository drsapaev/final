"""Store current-patient ownership evidence for a verified Telegram chat."""

import sqlalchemy as sa

from alembic import op

revision = "0124_telegram_ownership"
down_revision = "0123_reconciliation_fence"
branch_labels = None
depends_on = None


_COLUMN = "patient_owner_generation_snapshot"
_CHECK = "ck_telegram_patient_owner_generation"
_LINK_FIELDS = ("patient_id", "chat_id", "active", "blocked", "notifications_enabled", "appointment_reminders")


def _postgres_target() -> tuple[str, str, str]:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    quoted = context.dialect.identifier_preparer.quote_schema(schema)
    delimiter = "$telegram_ownership$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"
    return schema, quoted, delimiter


def _replace_postgres_epoch(quoted: str, delimiter: str, *, track_ownership: bool) -> None:
    fields = (*_LINK_FIELDS, "user_id", _COLUMN) if track_ownership else _LINK_FIELDS
    new_fields = ",".join(f"NEW.{field}" for field in fields)
    old_fields = ",".join(f"OLD.{field}" for field in fields)
    op.execute(f"""
      CREATE OR REPLACE FUNCTION {quoted}.bump_telegram_patient_link_epoch()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS {delimiter}
      BEGIN
        IF TG_OP='INSERT' THEN
          NEW.patient_link_epoch := pg_catalog.nextval(pg_catalog.format('%I.telegram_patient_link_generation_seq',TG_TABLE_SCHEMA)::pg_catalog.regclass);
        ELSIF ROW({new_fields}) IS DISTINCT FROM ROW({old_fields}) THEN
          NEW.patient_link_epoch := pg_catalog.nextval(pg_catalog.format('%I.telegram_patient_link_generation_seq',TG_TABLE_SCHEMA)::pg_catalog.regclass);
        ELSE
          NEW.patient_link_epoch := OLD.patient_link_epoch;
        END IF;
        RETURN NEW;
      END {delimiter}
    """)


def _upgrade_postgres() -> None:
    schema, quoted, delimiter = _postgres_target()
    op.add_column("telegram_users", sa.Column(_COLUMN, sa.BigInteger()), schema=schema)
    op.create_check_constraint(_CHECK, "telegram_users", f"{_COLUMN} IS NULL OR {_COLUMN}>0", schema=schema)
    op.execute(f"""
      CREATE FUNCTION {quoted}.guard_telegram_patient_ownership() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS {delimiter}
      BEGIN
        IF TG_OP='UPDATE' THEN
          IF ROW(NEW.patient_id,NEW.user_id,NEW.chat_id) IS DISTINCT FROM ROW(OLD.patient_id,OLD.user_id,OLD.chat_id) THEN
            NEW.patient_owner_generation_snapshot := NULL;
            RETURN NEW;
          END IF;
          IF NEW.patient_owner_generation_snapshot IS NOT DISTINCT FROM OLD.patient_owner_generation_snapshot THEN
            RETURN NEW;
          END IF;
        END IF;
        IF NEW.patient_owner_generation_snapshot IS NULL THEN
          RETURN NEW;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
                       WHERE c.oid=TG_RELID AND r.rolname=CURRENT_USER) THEN
          RAISE EXCEPTION 'invalid Telegram ownership evidence';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM {quoted}.patients p WHERE p.id=NEW.patient_id AND p.is_deleted IS FALSE
                       AND p.notification_owner_generation=NEW.patient_owner_generation_snapshot) THEN
          RAISE EXCEPTION 'invalid Telegram ownership evidence';
        END IF;
        RETURN NEW;
      END {delimiter}
    """)
    op.execute(f"""CREATE TRIGGER trg_guard_telegram_patient_ownership
      BEFORE INSERT OR UPDATE ON {quoted}.telegram_users FOR EACH ROW
      EXECUTE FUNCTION {quoted}.guard_telegram_patient_ownership()""")
    # PostgreSQL fires the guard before trg_telegram_patient_link_epoch by
    # trigger name, so generation changes include the normalized proof.
    _replace_postgres_epoch(quoted, delimiter, track_ownership=True)


def _replace_sqlite_epoch(*, track_ownership: bool) -> None:
    fields = _LINK_FIELDS
    changed = [f"OLD.{field} IS NOT NEW.{field}" for field in fields]
    clear_proof = ""
    if track_ownership:
        fields = (*fields, "user_id", _COLUMN)
        changed.append("OLD.user_id IS NOT NEW.user_id")
        # The internal proof clear accompanies a new epoch. Skip a reentrant
        # bump for that write when recursive triggers are enabled.
        changed.append(f"(OLD.{_COLUMN} IS NOT NEW.{_COLUMN} AND OLD.patient_link_epoch=NEW.patient_link_epoch)")
        clear_proof = f""", {_COLUMN}=CASE WHEN
          OLD.patient_id IS NOT NEW.patient_id OR OLD.chat_id IS NOT NEW.chat_id OR OLD.user_id IS NOT NEW.user_id
          THEN NULL ELSE NEW.{_COLUMN} END"""
    op.execute("DROP TRIGGER trg_telegram_patient_link_epoch")
    op.execute(f"""
      CREATE TRIGGER trg_telegram_patient_link_epoch AFTER UPDATE OF {','.join(fields)} ON telegram_users
      WHEN {' OR '.join(changed)}
      BEGIN
        UPDATE telegram_patient_link_generation_clock SET value=value+1 WHERE id=1;
        UPDATE telegram_users SET patient_link_epoch=(SELECT value FROM telegram_patient_link_generation_clock WHERE id=1)
          {clear_proof} WHERE id=NEW.id;
      END
    """)


def _upgrade_sqlite() -> None:
    op.add_column("telegram_users", sa.Column(
        _COLUMN, sa.BigInteger(), sa.CheckConstraint(
            f"{_COLUMN} IS NULL OR (typeof({_COLUMN})='integer' AND {_COLUMN}>0)", name=_CHECK,
        ),
    ))
    for suffix, event, check_change in (
        ("insert", "INSERT", ""),
        ("update", f"UPDATE OF {_COLUMN}", f"AND OLD.{_COLUMN} IS NOT NEW.{_COLUMN}"),
    ):
        op.execute(f"""CREATE TRIGGER trg_guard_telegram_owner_{suffix} BEFORE {event} ON telegram_users
          WHEN NEW.{_COLUMN} IS NOT NULL {check_change} AND NOT EXISTS (
            SELECT 1 FROM patients p WHERE p.id=NEW.patient_id AND p.is_deleted IS FALSE
              AND p.notification_owner_generation=NEW.{_COLUMN})
          BEGIN SELECT RAISE(ABORT, 'invalid Telegram ownership evidence'); END
        """)
    _replace_sqlite_epoch(track_ownership=True)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        _upgrade_postgres()
    elif dialect == "sqlite":
        _upgrade_sqlite()
    else:
        raise RuntimeError("Unsupported Telegram ownership dialect")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema, quoted, delimiter = _postgres_target()
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {quoted}.telegram_users IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""DO {delimiter} BEGIN
          IF EXISTS (SELECT 1 FROM {quoted}.telegram_users WHERE patient_owner_generation_snapshot IS NOT NULL) THEN
            RAISE EXCEPTION 'Telegram ownership evidence prevents downgrade';
          END IF;
        END {delimiter}""")
        op.execute(f"DROP TRIGGER trg_guard_telegram_patient_ownership ON {quoted}.telegram_users")
        op.execute(f"DROP FUNCTION {quoted}.guard_telegram_patient_ownership()")
        _replace_postgres_epoch(quoted, delimiter, track_ownership=False)
        op.drop_constraint(_CHECK, "telegram_users", type_="check", schema=schema)
        op.drop_column("telegram_users", _COLUMN, schema=schema)
    elif dialect == "sqlite":
        op.execute("UPDATE telegram_users SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE telegram_owner_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute("""INSERT INTO telegram_owner_downgrade_guard SELECT CASE WHEN EXISTS (
          SELECT 1 FROM telegram_users WHERE patient_owner_generation_snapshot IS NOT NULL) THEN 0 ELSE 1 END""")
        op.execute("DROP TABLE telegram_owner_downgrade_guard")
        for trigger in ("trg_guard_telegram_owner_insert", "trg_guard_telegram_owner_update"):
            op.execute(f"DROP TRIGGER {trigger}")
        _replace_sqlite_epoch(track_ownership=False)
        op.drop_column("telegram_users", _COLUMN)
    else:
        raise RuntimeError("Unsupported Telegram ownership dialect")
