"""PR-1 reminder pipeline: visits.reminder_sent_at idempotency marker.

The arq reminder worker (app/tasks/worker.py send_visit_reminder) has been
referencing `visits.reminder_sent_at` since P2.3, but the column never
existed in the model or in any migration — the first reminder job would
have died on an UndefinedColumn error before even reaching the
notification service. This revision adds the column the worker always
assumed:

- ``visits.reminder_sent_at`` — nullable DateTime(timezone=True), set by
  the worker after a reminder is actually sent; duplicate jobs and arq
  retries check it before dispatching.

Strictly additive: no data migration, no NOT NULL backfill (most
historical visits never had a reminder), no index (the worker looks the
row up by primary key only), no RLS change (column on an existing
RLS-enabled table).

Downgrade drops the column; in-flight reminder jobs between downgrade and
worker restart will fail loudly (UndefinedColumn) instead of silently
skipping — operator decides, history preserved.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0059_visit_reminder_sent_at"
down_revision = "0058_queue_resource_expand"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("visits", "reminder_sent_at")
