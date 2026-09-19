"""NURSE-V2 N2-2 — service_executions (owner design-GO 2026-09-19).

D1 FINAL (owner): a SEPARATE entity — execution status is NOT added to
visit_services. One row = one ATTEMPT to actually perform a concrete
VisitService; a retry after 'incomplete' creates a NEW attempt
(attempt_no + 1), the previous row is never overwritten; execution rows
are NOT auto-created from VisitService.qty (qty is the billed quantity,
not a proven count of clinical sessions). 'no_show' stays a queue-level
state — an execution exists only once the service actually starts.

Statuses (first stage): in_progress | completed | incomplete | cancelled.

Invariants (this migration):
- UNIQUE(visit_service_id, attempt_no) — one ordinal per attempt
  (mirrored in the ORM __table_args__; works on SQLite too);
- partial unique index uq_service_executions_one_active on
  (visit_service_id) WHERE status = 'in_progress' — at most ONE
  simultaneously active execution per VisitService (PG-only DDL,
  queue_entries 0065 precedent: deliberately NOT in the ORM).

FK policies:
- visit_service_id NO ACTION — deleting a VisitService with execution
  history must fail (the audit of what was actually performed outranks
  the billing line);
- queue_entry_id SET NULL — an entry purge must not delete execution
  history (mirrors online_queue_entries.visit_id);
- started_by/performed_by NO ACTION — audit attribution to real users
  must not be silently dropped.

SAFETY: additive-only DDL (one new table, no existing row touched, no
backfill). Production/staging application is NOT part of this change;
merging the PR does not authorize running it against a live database
(separate release GO per the NURSE-V2 migration discipline).

RLS: new public table — 0051 convention (inline ENABLE ROW LEVEL
SECURITY, as 0058 did for queue_resources). No policies created here
(the app connects as the table owner; policy work is out of N2-2 scope).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0072_service_executions"
down_revision = "0071_nurse_workplace_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("visit_service_id", sa.Integer(), nullable=False),
        sa.Column("queue_entry_id", sa.Integer(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("started_by_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("incomplete_reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_executions")),
        sa.UniqueConstraint(
            "visit_service_id",
            "attempt_no",
            name="uq_service_executions_visit_service_attempt",
        ),
    )
    op.create_foreign_key(
        "fk_service_executions_visit_service_id",
        "service_executions",
        "visit_services",
        ["visit_service_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_service_executions_queue_entry_id",
        "service_executions",
        "queue_entries",
        ["queue_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_service_executions_started_by_user_id",
        "service_executions",
        "users",
        ["started_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_service_executions_performed_by_user_id",
        "service_executions",
        "users",
        ["performed_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_service_executions_id"),
        "service_executions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_executions_visit_service_id"),
        "service_executions",
        ["visit_service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_executions_queue_entry_id"),
        "service_executions",
        ["queue_entry_id"],
        unique=False,
    )
    # D1 FINAL invariant: at most ONE simultaneously active (in_progress)
    # execution per VisitService. Partial (PG-only) — the queue_entries
    # 0065 precedent: deliberately NOT in the ORM __table_args__.
    op.create_index(
        "uq_service_executions_one_active",
        "service_executions",
        ["visit_service_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )
    # RLS for the new public table — 0051 convention (0058 precedent).
    op.execute("ALTER TABLE public.service_executions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.service_executions DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "uq_service_executions_one_active",
        table_name="service_executions",
    )
    op.drop_index(
        op.f("ix_service_executions_queue_entry_id"),
        table_name="service_executions",
    )
    op.drop_index(
        op.f("ix_service_executions_visit_service_id"),
        table_name="service_executions",
    )
    op.drop_index(
        op.f("ix_service_executions_id"),
        table_name="service_executions",
    )
    op.drop_constraint(
        "fk_service_executions_performed_by_user_id",
        "service_executions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_service_executions_started_by_user_id",
        "service_executions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_service_executions_queue_entry_id",
        "service_executions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_service_executions_visit_service_id",
        "service_executions",
        type_="foreignkey",
    )
    op.drop_table("service_executions")
