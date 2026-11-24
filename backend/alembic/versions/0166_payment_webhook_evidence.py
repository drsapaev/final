"""Keep the originally recorded payment webhook evidence stable."""

import sqlalchemy as sa
from alembic import op

revision = "0166_payment_webhook_evidence"
down_revision = "0165_payment_evidence_identity"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_FUNCTION = "reject_payment_webhook_evidence_change"
_TRIGGER = "trg_payment_webhooks_evidence_content"


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError("Payment webhook evidence requires an online PostgreSQL catalog")
    name = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not name:
        raise RuntimeError("Trusted payment webhook schema required")
    return context.dialect.identifier_preparer.quote_schema(name)


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    op.execute(f"""
        CREATE FUNCTION {schema}.{_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $webhook_evidence$
        BEGIN
            RAISE EXCEPTION 'Stored payment webhook evidence is immutable'
                USING ERRCODE = '23514';
        END;
        $webhook_evidence$
    """)
    connection = op.get_bind()
    roles = connection.scalars(
        sa.text("""
            SELECT rolname FROM pg_catalog.pg_roles
            WHERE rolname IN :roles ORDER BY rolname
        """).bindparams(sa.bindparam("roles", expanding=True)),
        {"roles": _GATEWAY_ROLES},
    )
    quote = connection.dialect.identifier_preparer.quote_identifier
    grantees = ", ".join(("PUBLIC", *map(quote, roles)))
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.{_FUNCTION}() FROM {grantees} RESTRICT")

    op.execute(f"""
        CREATE TRIGGER {_TRIGGER}
        AFTER UPDATE ON {schema}.payment_webhooks FOR EACH ROW
        WHEN (
            ROW(OLD.raw_data::text COLLATE pg_catalog."C",
                OLD.signature COLLATE pg_catalog."C", OLD.created_at)
            IS DISTINCT FROM
            ROW(NEW.raw_data::text COLLATE pg_catalog."C",
                NEW.signature COLLATE pg_catalog."C", NEW.created_at)
        )
        EXECUTE FUNCTION {schema}.{_FUNCTION}()
    """)


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return
    op.execute(f"DROP TRIGGER {_TRIGGER} ON {schema}.payment_webhooks")
    op.execute(f"DROP FUNCTION {schema}.{_FUNCTION}()")
