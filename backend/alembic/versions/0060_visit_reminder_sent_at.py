"""Reminder pipeline PR-1: visits.reminder_sent_at as real schema.

The arq worker job ``send_visit_reminder`` (app/tasks/worker.py) has always
assumed a ``visits.reminder_sent_at`` column — both its idempotency guard
(SELECT reminder_sent_at) and its success stamp (UPDATE visits SET
reminder_sent_at = NOW()) used raw SQL against a column that existed in
neither the ORM model nor any migration, so every real job run died with
UndefinedColumn before it could even reach the notification service.

This revision makes the column real: a plain nullable TIMESTAMPTZ on
``visits``, mirroring the neighboring ``confirmed_at`` typing convention.
Strictly additive DDL — no data migration, no backfill (every existing
visit is correctly "never reminded"), no runtime switch. The ORM gains the
same column in the same PR and the worker switches from raw SQL to the ORM
attribute, so the idempotency contract ("second run must not send a second
notification") is enforced at the DB level by the schema itself.

No index: the worker reads/writes the column by primary key (visits.id),
never scans by reminder_sent_at.

Downgrade drops the column; a rollback loses only the "already reminded"
bookkeeping — visits themselves are untouched.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0058_queue_resource_expand.
revision = "0060_visit_reminder_sent_at"
down_revision = "0059_resource_seed_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("visits", "reminder_sent_at")
