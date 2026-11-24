"""Protect the PostgreSQL audit log against whole-table truncation."""

from alembic import op

revision = "0144_audit_log_truncate_guard"
down_revision = "0143_merge_public_analytics"
branch_labels = None
depends_on = None


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported audit log dialect")

    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return context.dialect.identifier_preparer.quote_schema(schema)


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    op.execute(f"""
        CREATE FUNCTION {schema}.prevent_audit_log_truncate() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog
        AS $audit_log_guard$
        BEGIN
            RAISE EXCEPTION 'audit log cannot be truncated' USING ERRCODE='23514';
        END $audit_log_guard$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.prevent_audit_log_truncate() FROM PUBLIC")
    op.execute(f"""
        CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON {schema}.audit_logs
        FOR EACH STATEMENT EXECUTE FUNCTION {schema}.prevent_audit_log_truncate()
    """)
    op.execute(f"ALTER TABLE {schema}.audit_logs ENABLE ALWAYS TRIGGER audit_logs_no_truncate")


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    op.execute(f"DROP TRIGGER audit_logs_no_truncate ON {schema}.audit_logs")
    op.execute(f"DROP FUNCTION {schema}.prevent_audit_log_truncate()")
