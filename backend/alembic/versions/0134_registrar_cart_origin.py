"""Bind new registrar cart invoices to their original encounter."""

import sqlalchemy as sa

from alembic import op

revision = "0134_registrar_cart_origin"
down_revision = "0133_benefit_ledger_immutability"
branch_labels = None
depends_on = None

_ORIGIN = "registrar_encounter_id_snapshot"
_GENERATION = "registrar_encounter_generation_snapshot"
_TABLE = "payment_invoices"
_INDEX = "uq_payment_invoice_registrar_encounter"
_FUNCTION = "protect_registrar_cart_origin"
_UPDATE = "trg_registrar_cart_origin_immutable"
_VERIFY = "trg_registrar_cart_origin_verify"


def _postgres_target() -> tuple[str, str]:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    quoted = context.dialect.identifier_preparer.quote_schema(schema)
    delimiter = "$registrar_cart_origin$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"
    return quoted, delimiter


def _upgrade_postgres() -> None:
    schema, delimiter = _postgres_target()
    op.execute(f"""
      CREATE FUNCTION {schema}.{_FUNCTION}() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=off AS {delimiter}
      DECLARE members integer[];
      BEGIN
        IF TG_OP='UPDATE' THEN
          IF ROW(OLD.{_ORIGIN},OLD.{_GENERATION}) IS DISTINCT FROM ROW(NEW.{_ORIGIN},NEW.{_GENERATION})
            OR (OLD.{_ORIGIN} IS NOT NULL AND ROW(OLD.id,OLD.patient_id) IS DISTINCT FROM ROW(NEW.id,NEW.patient_id)) THEN
            RAISE EXCEPTION 'registrar cart origin is immutable';
          END IF;
          RETURN NEW;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM {schema}.{_TABLE} WHERE id=NEW.id) THEN RETURN NULL; END IF;
        members := ARRAY(SELECT v.id FROM {schema}.visits v WHERE v.encounter_id=NEW.{_ORIGIN} ORDER BY v.id);
        IF NOT EXISTS (SELECT 1 FROM {schema}.encounters e WHERE e.id=NEW.{_ORIGIN}
                       AND e.patient_id=NEW.patient_id AND e.generation=NEW.{_GENERATION} AND e.provenance='new')
          OR pg_catalog.cardinality(members)=0
          OR EXISTS (SELECT 1 FROM {schema}.visits v WHERE v.id=ANY(members) AND v.patient_id IS DISTINCT FROM NEW.patient_id)
          OR members IS DISTINCT FROM ARRAY (
            SELECT l.visit_id FROM {schema}.payment_invoice_visits l WHERE l.invoice_id=NEW.id ORDER BY l.visit_id
          ) THEN
          RAISE EXCEPTION 'registrar cart invoice membership does not match its origin';
        END IF;
        RETURN NULL;
      END {delimiter}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.{_FUNCTION}() FROM PUBLIC")
    op.execute(f"""
      CREATE TRIGGER {_UPDATE} BEFORE UPDATE OF id,patient_id,{_ORIGIN},{_GENERATION} ON {schema}.{_TABLE}
      FOR EACH ROW EXECUTE FUNCTION {schema}.{_FUNCTION}()
    """)
    op.execute(f"""
      CREATE CONSTRAINT TRIGGER {_VERIFY} AFTER INSERT ON {schema}.{_TABLE}
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.{_ORIGIN} IS NOT NULL)
      EXECUTE FUNCTION {schema}.{_FUNCTION}()
    """)
    table_name = f"{schema}.{_TABLE}".replace("'", "''")
    function_name = f"{schema}.{_FUNCTION}()".replace("'", "''")
    op.execute(f"""DO {delimiter} DECLARE table_owner name; BEGIN
      SELECT r.rolname INTO STRICT table_owner FROM pg_catalog.pg_class t
      JOIN pg_catalog.pg_roles r ON r.oid=t.relowner WHERE t.oid='{table_name}'::pg_catalog.regclass;
      EXECUTE pg_catalog.format('ALTER FUNCTION %s OWNER TO %I','{function_name}',table_owner);
    END {delimiter}""")


def _upgrade_sqlite() -> None:
    op.execute(f"""
      CREATE TRIGGER {_UPDATE} BEFORE UPDATE OF id,patient_id,{_ORIGIN},{_GENERATION} ON {_TABLE}
      WHEN OLD.{_ORIGIN} IS NOT NEW.{_ORIGIN} OR OLD.{_GENERATION} IS NOT NEW.{_GENERATION}
        OR (OLD.{_ORIGIN} IS NOT NULL AND (OLD.id IS NOT NEW.id OR OLD.patient_id IS NOT NEW.patient_id))
      BEGIN SELECT RAISE(ABORT,'registrar cart origin is immutable'); END
    """)
    # SQLite cannot defer a trigger until invoice links are inserted. The cart
    # supplies every link in its transaction and checks the encounter at commit.
    op.execute(f"""
      CREATE TRIGGER {_VERIFY} BEFORE INSERT ON {_TABLE}
      BEGIN
        SELECT RAISE(ABORT,'registrar cart origin is immutable') WHERE EXISTS (
          SELECT 1 FROM {_TABLE} i WHERE i.{_ORIGIN} IS NOT NULL AND (i.id=NEW.id OR i.{_ORIGIN}=NEW.{_ORIGIN})
        );
        SELECT RAISE(ABORT,'registrar cart invoice membership does not match its origin')
        WHERE NEW.{_ORIGIN} IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM encounters e WHERE e.id=NEW.{_ORIGIN} AND e.patient_id=NEW.patient_id
            AND e.generation=NEW.{_GENERATION} AND e.provenance='new'
        );
      END
    """)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported registrar cart origin dialect")
    op.add_column(_TABLE, sa.Column(_ORIGIN, sa.Integer(), nullable=True))
    op.add_column(_TABLE, sa.Column(
        _GENERATION, sa.BigInteger(),
        sa.CheckConstraint(
            f"({_ORIGIN} IS NULL AND {_GENERATION} IS NULL) OR "
            f"({_ORIGIN} IS NOT NULL AND {_GENERATION} IS NOT NULL AND {_ORIGIN}>0 AND {_GENERATION}>0)",
            name="ck_payment_invoice_registrar_origin",
        ),
        nullable=True,
    ))
    marked = sa.text(f"{_ORIGIN} IS NOT NULL")
    op.create_index(_INDEX, _TABLE, [_ORIGIN], unique=True, postgresql_where=marked, sqlite_where=marked)
    if dialect == "postgresql":
        _upgrade_postgres()
    else:
        _upgrade_sqlite()


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema, delimiter = _postgres_target()
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {schema}.{_TABLE} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""DO {delimiter} BEGIN
          IF EXISTS (SELECT 1 FROM {schema}.{_TABLE} WHERE {_ORIGIN} IS NOT NULL) THEN
            RAISE EXCEPTION 'registrar cart origin prevents downgrade';
          END IF;
        END {delimiter}""")
        for trigger in (_VERIFY, _UPDATE):
            op.execute(f"DROP TRIGGER {trigger} ON {schema}.{_TABLE}")
        op.execute(f"DROP FUNCTION {schema}.{_FUNCTION}()")
    elif dialect == "sqlite":
        op.execute(f"UPDATE {_TABLE} SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE registrar_origin_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        op.execute(f"""INSERT INTO registrar_origin_downgrade_guard
          SELECT CASE WHEN EXISTS (SELECT 1 FROM {_TABLE} WHERE {_ORIGIN} IS NOT NULL) THEN 0 ELSE 1 END""")
        op.execute("DROP TABLE registrar_origin_downgrade_guard")
        for trigger in (_VERIFY, _UPDATE):
            op.execute(f"DROP TRIGGER {trigger}")
    else:
        raise RuntimeError("Unsupported registrar cart origin dialect")
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_column(_TABLE, _GENERATION)
    op.drop_column(_TABLE, _ORIGIN)
