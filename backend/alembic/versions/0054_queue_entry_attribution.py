"""QF-1: queue entry operator attribution columns.

OnlineQueueEntry gains a LIVE-OPERATOR axis, orthogonal to the routing
owner (DailyQueue.specialist_id — a real doctor or a synthetic resource
doctor like lab_resource/ecg_resource for doctorless queues):

- called_by_user_id: who called the patient next. Until QF-1 this was a
  TRANSIENT attribute set by QRQueueService.call_next_patient — only the
  GraphQL critical-audit path persisted it (Codex round-7 P1); the REST
  and Telegram staff_call paths dropped it between requests. As a real
  column every surface keeps the caller identity.
- served_by_user_id / served_at: who completed the entry and when
  (complete_patient_visit; timestamp precedent: diagnostics_started_at).

Contract decisions (QF-1 blueprint, 2026-09-05):
- Nullable FK ON DELETE SET NULL: deleting the operator user preserves the
  queue history row with NULL attribution — the same audit-preservation
  contract as the patient_id/visit_id FKs on queue_entries.
- NO backfill: pre-QF-1 caller identity was transient (lost between
  requests) — historical rows stay NULL rather than being guessed.
- Indexes follow the 0035_fk_indexes convention (ix_{table}_{column}).
- RBAC/role vocabulary is intentionally NOT touched by this change; the
  serving-role question (e.g. a future Technician role) is a separate
  product decision.

Revision ID: 0054_queue_entry_attribution
Revises: 0053_users_email_unique
Create Date: 2026-09-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0054_queue_entry_attribution"
down_revision = "0053_users_email_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "queue_entries",
        sa.Column("called_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "queue_entries",
        sa.Column("served_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "queue_entries",
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=True),
    )
    # FK constraints follow the 0008_lab_catalog_normalization precedent
    # (op.create_foreign_key) — the repo's idiomatic PG form; add_column with
    # an inline FK was never used in this chain.
    op.create_foreign_key(
        "fk_queue_entries_called_by_user_id",
        "queue_entries",
        "users",
        ["called_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_queue_entries_served_by_user_id",
        "queue_entries",
        "users",
        ["served_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_queue_entries_called_by_user_id",
        "queue_entries",
        ["called_by_user_id"],
    )
    op.create_index(
        "ix_queue_entries_served_by_user_id",
        "queue_entries",
        ["served_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_queue_entries_served_by_user_id", table_name="queue_entries")
    op.drop_index("ix_queue_entries_called_by_user_id", table_name="queue_entries")
    op.drop_constraint(
        "fk_queue_entries_served_by_user_id",
        "queue_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_queue_entries_called_by_user_id",
        "queue_entries",
        type_="foreignkey",
    )
    op.drop_column("queue_entries", "served_at")
    op.drop_column("queue_entries", "served_by_user_id")
    op.drop_column("queue_entries", "called_by_user_id")
