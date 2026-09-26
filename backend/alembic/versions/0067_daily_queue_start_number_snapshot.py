"""RQ-13.b (D-06): DailyQueue.start_number — snapshot of the day's applied
start number.

Owner decision 2026-09-15 (E-039, DECISION_PROPOSALS.md «Решение владельца
продукта»): «Для действующей дневной очереди сохраняется снимок применённых
параметров, включая стартовый номер, время и лимит. ... Новые настройки не
меняют выданные номера и историю текущего дня.»

Pre-slice behavior (verified on f6d9128): the column did not exist and
numbering fell back to LIVE sources at ticket time
(``QueueResource.start_number_online`` / clinic ``start_numbers``), so a
mid-day settings change shifted the active day's baseline.

Upgrade:
- adds ``daily_queues.start_number`` INTEGER NOT NULL SERVER DEFAULT '1';
- backfills EXISTING rows from their owner's ``start_number_online``
  (resource rows ← queue_resources.start_number_online, doctor rows ←
  doctors.start_number_online), so in-flight days keep their pre-migration
  baseline. Rows whose owner sits at the neutral default (1) stay at 1 —
  the clinic-level per-tag offsets are re-applied at day creation for
  future days only (see effective_day_start_number); days alive across the
  deploy window self-heal at midnight.

Downgrade drops the column (pure additive slice; no data rewrite).

Revision ID: 0067_daily_queue_start_number_snapshot
Revises: 0066_general_retirement_cutover
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0067_daily_queue_start_number"
down_revision = "0066_general_retirement_cutover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_queues",
        sa.Column(
            "start_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    # Backfill from the OWNER axis (both columns are NOT NULL DEFAULT 1).
    # Resource rows: the QD-2C registry SSOT. Doctor rows: the owner value
    # (D-06 chain «клиника → отделение → владелец»). COALESCE keeps the
    # server_default '1' when the owner join misses (defensive).
    op.execute(
        """
        UPDATE daily_queues dq
        SET start_number = COALESCE(qr.start_number_online, dq.start_number)
        FROM queue_resources qr
        WHERE dq.queue_resource_id = qr.id
        """
    )
    op.execute(
        """
        UPDATE daily_queues dq
        SET start_number = COALESCE(d.start_number_online, dq.start_number)
        FROM doctors d
        WHERE dq.specialist_id = d.id
        """
    )


def downgrade() -> None:
    op.drop_column("daily_queues", "start_number")
