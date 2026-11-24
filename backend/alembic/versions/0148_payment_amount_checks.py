"""Guard stored payment amounts and cumulative refunds."""

from alembic import op

revision = "0148_payment_amount_checks"
down_revision = "0147_invoice_amount_checks"
branch_labels = None
depends_on = None

_AMOUNT_CHECKS = (
    ("ck_payments_amount_range", "amount BETWEEN 0 AND 9999999999.99"),
    (
        "ck_payments_refunded_amount_range",
        "refunded_amount IS NULL OR refunded_amount BETWEEN 0 AND amount",
    ),
)


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported payment amount check dialect")
    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return schema


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    for name, expression in _AMOUNT_CHECKS:
        op.create_check_constraint(
            name,
            "payments",
            expression,
            schema=schema,
            postgresql_not_valid=True,
        )


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    for name, _ in reversed(_AMOUNT_CHECKS):
        op.drop_constraint(name, "payments", type_="check", schema=schema)
