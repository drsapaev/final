"""NURSE-V2 N2-2 — nurse_workplace_assignments (owner design-GO 2026-09-19).

D2 FINAL (owner): a Nurse may hold several active assignments (one per
QueueResource), a QueueResource may be served by several Nurses; at most
ONE ACTIVE assignment per (user_id, queue_resource_id) pair — partial
unique index ``WHERE is_active``. ``cabinet_override`` is the
station/cabinet for this assignment; NULL falls back to
``QueueResource.default_cabinet``. Inactive assignments are historical
records: deactivation keeps the row and a new active row for the same
pair may be created afterwards.

FK policies (0008/0054 owner-FK convention — NO ACTION): deleting a
referenced user or queue_resource with live assignment history must
fail; history preservation wins, the operator decides how to proceed.

SAFETY: additive-only DDL (one new table, three indexes, one partial
unique index, two FKs); no existing row is modified, nothing is
backfilled. Production/staging application is NOT part of this change:
merging the PR does not authorize running this migration against a live
database (separate release GO per the NURSE-V2 migration discipline).

RLS: new public table — 0051 convention (inline ENABLE ROW LEVEL
SECURITY, as 0058 did for queue_resources). No policies are created
here: the app connects as the table owner (RLS bypass for owners), and
policy work is deliberately out of the N2-2 scope.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0071_nurse_workplace_assignments"
down_revision = "0070_lab_results_lineage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nurse_workplace_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("queue_resource_id", sa.Integer(), nullable=False),
        sa.Column("cabinet_override", sa.String(length=20), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nurse_workplace_assignments")),
    )
    op.create_foreign_key(
        "fk_nurse_workplace_assignments_user_id",
        "nurse_workplace_assignments",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_nurse_workplace_assignments_queue_resource_id",
        "nurse_workplace_assignments",
        "queue_resources",
        ["queue_resource_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_nurse_workplace_assignments_id"),
        "nurse_workplace_assignments",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nurse_workplace_assignments_user_id"),
        "nurse_workplace_assignments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nurse_workplace_assignments_queue_resource_id"),
        "nurse_workplace_assignments",
        ["queue_resource_id"],
        unique=False,
    )
    # D2 FINAL invariant: at most one ACTIVE assignment per
    # (user_id, queue_resource_id) pair. Partial (PG-only) — the same
    # deliberate shape as the queue_entries 0065 deferred unique: NOT
    # in the ORM __table_args__ so SQLite create_all paths stay plain.
    op.create_index(
        "uq_nurse_workplace_assignments_active_pair",
        "nurse_workplace_assignments",
        ["user_id", "queue_resource_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    # RLS for the new public table — 0051 convention (0058 precedent).
    op.execute(
        "ALTER TABLE public.nurse_workplace_assignments ENABLE ROW LEVEL SECURITY"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.nurse_workplace_assignments DISABLE ROW LEVEL SECURITY"
    )
    op.drop_index(
        "uq_nurse_workplace_assignments_active_pair",
        table_name="nurse_workplace_assignments",
    )
    op.drop_index(
        op.f("ix_nurse_workplace_assignments_queue_resource_id"),
        table_name="nurse_workplace_assignments",
    )
    op.drop_index(
        op.f("ix_nurse_workplace_assignments_user_id"),
        table_name="nurse_workplace_assignments",
    )
    op.drop_index(
        op.f("ix_nurse_workplace_assignments_id"),
        table_name="nurse_workplace_assignments",
    )
    op.drop_constraint(
        "fk_nurse_workplace_assignments_queue_resource_id",
        "nurse_workplace_assignments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_nurse_workplace_assignments_user_id",
        "nurse_workplace_assignments",
        type_="foreignkey",
    )
    op.drop_table("nurse_workplace_assignments")
