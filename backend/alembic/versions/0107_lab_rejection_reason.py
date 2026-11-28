"""Retain structured specimen rejection categories separately from event notes."""

import sqlalchemy as sa

from alembic import op

revision = "0107_lab_rejection_reason"
down_revision = "0106_lab_result_contracts"
branch_labels = None
depends_on = None

TABLE = "lab_specimen_events"
CONSTRAINT = "ck_lab_specimen_event_rejection_reason"
CODE_CHECK = (
    "reason_code IS NULL OR (action = 'reject' AND reason_code IN ("
    "'label_mismatch', 'container_mismatch', 'insufficient_quantity', "
    "'specimen_quality', 'transport_issue', 'other'))"
)


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "reason_code",
            sa.String(32),
            sa.CheckConstraint(CODE_CHECK, name=CONSTRAINT),
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"LOCK TABLE public.{TABLE} IN ACCESS EXCLUSIVE MODE")
    has_categories = bind.execute(
        sa.text(f"SELECT EXISTS (SELECT 1 FROM {TABLE} WHERE reason_code IS NOT NULL)")
    ).scalar_one()
    if has_categories:
        raise RuntimeError(
            "Refusing to remove recorded specimen rejection reason codes."
        )
    op.drop_column(TABLE, "reason_code")
