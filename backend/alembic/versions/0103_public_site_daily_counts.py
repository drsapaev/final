"""Store daily totals for approved public-site interactions."""

import sqlalchemy as sa

from alembic import op

revision = "0103_public_site_daily_counts"
down_revision = "0102_visit_confirm_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_site_daily_counts",
        sa.Column("clinic_day", sa.Date(), nullable=False),
        sa.Column("event_code", sa.String(length=24), nullable=False),
        sa.Column("total", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "clinic_day", "event_code", name="pk_public_site_daily_counts"
        ),
        sa.CheckConstraint(
            "event_code IN ('site_view', 'phone_click', 'booking_form_open')",
            name="ck_public_site_daily_counts_event_code",
        ),
        sa.CheckConstraint("total > 0", name="ck_public_site_daily_counts_total"),
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE public.public_site_daily_counts " "ENABLE ROW LEVEL SECURITY",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "LOCK TABLE public.public_site_daily_counts "
                "IN ACCESS EXCLUSIVE MODE",
            )
        )

    has_totals = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM public_site_daily_counts)")
    ).scalar_one()
    if has_totals:
        raise RuntimeError("Refusing to remove persisted public site daily totals.")

    op.drop_table("public_site_daily_counts")
