"""Enforce one active notification template per type and channel.

Pre-existing duplicate active rows require an explicit operator decision.
The migration never chooses or mutates existing templates.
"""

import sqlalchemy as sa

from alembic import op

revision = "0098_notify_template_unique"
down_revision = "0097_two_factor_sensitive_totp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Offline SQL cannot query data. The unique index still rejects duplicates
    # atomically when that SQL is applied, without modifying existing rows.
    if not op.get_context().as_sql:
        duplicate_groups = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT COUNT(*) FROM (SELECT 1 FROM notification_templates "
                    "WHERE is_active IS TRUE GROUP BY type, channel HAVING COUNT(*) > 1) AS duplicates"
                )
            )
            .scalar_one()
        )
        if duplicate_groups:
            raise RuntimeError(
                f"{duplicate_groups} duplicate active template groups exist; resolve explicitly before upgrade"
            )
    op.create_index(
        "uq_notification_templates_active_type_channel",
        "notification_templates",
        ["type", "channel"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
        sqlite_where=sa.text("is_active IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notification_templates_active_type_channel",
        table_name="notification_templates",
    )
