"""Reserve issued Kaspi references without rewriting historical payments."""

from alembic import op

revision = "0146_kaspi_issued_reference"
down_revision = "0145_payme_receipt_integrity"
branch_labels = None
depends_on = None

_REGISTRY = "kaspi_issued_payment_refs"
_FUNCTION = "reserve_kaspi_payment_reference"
_ASSIGNMENT = "trg_reserve_kaspi_payment_reference"
_TRUNCATE = "trg_keep_kaspi_reference_registry"


def _postgres_target() -> tuple[str, str] | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported Kaspi reference dialect")
    name = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not name:
        raise RuntimeError("Trusted application schema required")
    schema = context.dialect.identifier_preparer.quote_schema(name)
    tag = "$kaspi_issued_reference$"
    while tag in schema:
        tag = tag[:-1] + "_x$"
    return schema, tag


def _source_references(schema: str) -> str:
    return f"""
      SELECT provider_payment_id AS reference FROM {schema}.payments
      WHERE provider = 'kaspi' AND provider_payment_id IS NOT NULL
      UNION
      SELECT transaction_id FROM {schema}.payment_transactions
      WHERE provider = 'kaspi'
    """


def _lock_complete_sources(schema: str, tag: str) -> None:
    literal = schema.replace("'", "''")
    op.execute(f"LOCK TABLE {schema}.payments, {schema}.payment_transactions IN SHARE ROW EXCLUSIVE MODE")
    op.execute(f"""
      DO {tag} BEGIN
        IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
          RAISE EXCEPTION 'Kaspi reference migration requires read committed' USING ERRCODE='25000';
        END IF;
        IF pg_catalog.row_security_active('{literal}.payments'::pg_catalog.regclass)
           OR pg_catalog.row_security_active('{literal}.payment_transactions'::pg_catalog.regclass) THEN
          RAISE EXCEPTION 'Kaspi reference history must be visible' USING ERRCODE='42501';
        END IF;
      END {tag}
    """)


def upgrade() -> None:
    target = _postgres_target()
    if target is None:
        return
    schema, tag = target
    literal = schema.replace("'", "''")
    _lock_complete_sources(schema, tag)

    op.execute(f"""
      CREATE TABLE {schema}.{_REGISTRY} (
        reference VARCHAR(128) CONSTRAINT pk_kaspi_issued_payment_refs PRIMARY KEY
      )
    """)
    op.execute(f"INSERT INTO {schema}.{_REGISTRY} (reference) {_source_references(schema)}")
    op.execute(f"REVOKE ALL ON TABLE {schema}.{_REGISTRY} FROM PUBLIC")
    op.execute(f"ALTER TABLE {schema}.{_REGISTRY} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {schema}.{_REGISTRY} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY kaspi_reference_owner_read ON {schema}.{_REGISTRY} FOR SELECT TO CURRENT_USER USING (true)"
    )
    op.execute(
        f"CREATE POLICY kaspi_reference_owner_reserve ON {schema}.{_REGISTRY} "
        "FOR INSERT TO CURRENT_USER WITH CHECK (true)"
    )

    op.execute(f"""
      CREATE FUNCTION {schema}.{_FUNCTION}() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS {tag}
      BEGIN
        IF TG_OP = 'TRUNCATE' THEN
          RAISE EXCEPTION 'Kaspi reference registry cannot be truncated' USING ERRCODE='23514';
        END IF;
        IF TG_RELID <> '{literal}.payments'::pg_catalog.regclass OR TG_NAME <> '{_ASSIGNMENT}' THEN
          RAISE EXCEPTION 'Invalid Kaspi reference trigger' USING ERRCODE='42501';
        END IF;
        IF NEW.provider IS DISTINCT FROM 'kaspi' OR NEW.provider_payment_id IS NULL THEN
          RETURN NEW;
        END IF;
        IF TG_OP = 'UPDATE' THEN
          IF OLD.provider IS NOT DISTINCT FROM NEW.provider
             AND OLD.provider_payment_id IS NOT DISTINCT FROM NEW.provider_payment_id THEN
            RETURN NEW;
          END IF;
        END IF;

        INSERT INTO {schema}.{_REGISTRY} (reference) VALUES (NEW.provider_payment_id)
        ON CONFLICT DO NOTHING;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'Kaspi reference already issued'
            USING ERRCODE='23505', CONSTRAINT='pk_kaspi_issued_payment_refs';
        END IF;
        RETURN NEW;
      END {tag}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.{_FUNCTION}() FROM PUBLIC")
    op.execute(f"""
      CREATE TRIGGER {_ASSIGNMENT} BEFORE INSERT OR UPDATE OF provider, provider_payment_id
      ON {schema}.payments FOR EACH ROW EXECUTE FUNCTION {schema}.{_FUNCTION}()
    """)
    op.execute(f"""
      CREATE TRIGGER {_TRUNCATE} BEFORE TRUNCATE ON {schema}.{_REGISTRY}
      FOR EACH STATEMENT EXECUTE FUNCTION {schema}.{_FUNCTION}()
    """)


def downgrade() -> None:
    target = _postgres_target()
    if target is None:
        return
    schema, tag = target
    _lock_complete_sources(schema, tag)
    op.execute(f"LOCK TABLE {schema}.{_REGISTRY} IN ACCESS EXCLUSIVE MODE")
    op.execute(f"""
      DO {tag} BEGIN
        IF EXISTS (
          SELECT reference FROM {schema}.{_REGISTRY}
          EXCEPT
          SELECT source.reference FROM ({_source_references(schema)}) AS source
        ) THEN
          RAISE EXCEPTION 'Kaspi reference history prevents downgrade' USING ERRCODE='23514';
        END IF;
      END {tag}
    """)
    op.execute(f"DROP TRIGGER {_ASSIGNMENT} ON {schema}.payments")
    op.execute(f"DROP TABLE {schema}.{_REGISTRY}")
    op.execute(f"DROP FUNCTION {schema}.{_FUNCTION}()")
