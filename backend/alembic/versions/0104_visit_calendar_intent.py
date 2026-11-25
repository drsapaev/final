"""Record deliberate staff moves independently of visit or reminder timing."""

import sqlalchemy as sa

from alembic import op

revision = "0104_visit_calendar_intent"
down_revision = "0103_public_site_daily_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column(
            "calendar_rescheduled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("visits", "calendar_rescheduled")
