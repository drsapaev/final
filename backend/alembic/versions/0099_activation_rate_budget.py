"""Add bounded shared admission counters for server activation."""
import sqlalchemy as sa

from alembic import op

revision = "0099_activation_rate_budget"
down_revision = "0098_notify_template_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activation_rate_budgets",
        sa.Column("scope", sa.String(72), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts >= 1", name="ck_activation_rate_budget_attempts"),
    )
    op.create_index("ix_activation_rate_budget_expiry", "activation_rate_budgets", ["expires_at"])
    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TABLE activation_rate_budgets ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_activation_rate_budget_expiry", table_name="activation_rate_budgets")
    op.drop_table("activation_rate_budgets")
