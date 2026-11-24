"""Guard stored amounts allocated from payments to visits."""

from alembic import op

revision = "0149_payment_visit_amount"
down_revision = "0148_payment_amount_checks"
branch_labels = None
depends_on = None

_CHECK_NAME = "ck_payment_visits_amount_range"


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported payment allocation amount check dialect")
    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return schema


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is not None:
        op.create_check_constraint(
            _CHECK_NAME,
            "payment_visits",
            "amount BETWEEN 0 AND 9999999999.99",
            schema=schema,
            postgresql_not_valid=True,
        )


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is not None:
        op.drop_constraint(_CHECK_NAME, "payment_visits", type_="check", schema=schema)
