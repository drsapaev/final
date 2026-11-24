"""Guard stored invoice amounts without rewriting existing rows."""

from alembic import op

revision = "0147_invoice_amount_checks"
down_revision = "0146_kaspi_issued_reference"
branch_labels = None
depends_on = None

_AMOUNT_CHECKS = (
    ("payment_invoices", "ck_payment_invoices_total_amount_range", "total_amount"),
    ("payment_invoice_visits", "ck_payment_invoice_visits_visit_amount_range", "visit_amount"),
)


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported invoice amount check dialect")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return schema


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    for table, name, column in _AMOUNT_CHECKS:
        # The upper bound also excludes PostgreSQL numeric NaN.
        op.create_check_constraint(
            name,
            table,
            f"{column} BETWEEN 0 AND 9999999999.99",
            schema=schema,
            postgresql_not_valid=True,
        )


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    for table, name, _ in reversed(_AMOUNT_CHECKS):
        op.drop_constraint(name, table, type_="check", schema=schema)
