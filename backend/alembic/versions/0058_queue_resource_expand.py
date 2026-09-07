"""QD-2A: queue_resources entity + daily_queues dual-owner EXPAND.

Stage A of the QD-2 staged rollout (QueueResource architecture FINAL,
2026-09-07): doctorless queues move off the synthetic User+Doctor pairs
(``lab_resource`` / ``ecg_resource`` / ``general_resource``, provisioned
by 0055 and sandboxed by QD-1.1/QD-1.2) onto a dedicated reference
entity. This revision is the EXPAND step — strictly additive DDL, no
data, no runtime switch; every existing row and every old code path
stays byte-compatible:

- new table ``queue_resources`` — the physical registry for doctorless
  queue routing: ``code`` / ``queue_tag`` UNIQUE (they are semantically
  distinct: code identifies the registry row, queue_tag is the exact
  ``DailyQueue.queue_tag`` value it owns), ``display_name``, ``active``,
  the queue-numbering config resource Doctors carry today
  (``start_number_online`` / ``max_online_per_day`` — read from the
  Doctor row by queue_svc/_operations.py and the GraphQL mutations),
  ``default_cabinet`` nullable, timestamps. Mirrors the
  medical_specialties catalog conventions (op.f() constraint names,
  redundant ix_* indexes, inline ENABLE ROW LEVEL SECURITY — the
  0050/0051 public-RLS invariant must hold at every chain position).
- ``daily_queues.queue_resource_id`` — nullable Integer FK to
  queue_resources (NO ACTION, same policy as the specialist_id FK in
  0001_baseline: history rows are never silently detached) + the
  ix_daily_queues_queue_resource_id index (0035/0054 convention).
- ``daily_queues.specialist_id`` — NULLABLE (was NOT NULL). This is the
  schema half of the dual-owner design; the app contract is untouched
  this stage.

Deliberately NOT in this revision (staged plan, one PR per stage):

- no seed rows — lab/ecg provisioning is QD-2B (explicit registry,
  exact-tag-wins duplicate policy, inventory-before-mutation);
- no XOR CHECK and no partial active uniqueness — the (day, tag)
  duplicate landscape and the uniqueness contract are QD-2B/QD-2D;
- no runtime changes — resolvers, morning pre-create, API identity and
  output contract are QD-2C; synthetic identities retire in QD-2E.

Downgrade is strict: re-tightening specialist_id to NOT NULL fails
loudly on any row written with a NULL specialist meanwhile (history
preservation first — the operator decides, not the migration), then
drops the column/FK/index and the queue_resources table.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0057_lab_resource_internal_role.
revision = "0058_queue_resource_expand"
down_revision = "0057_lab_resource_internal_role"
branch_labels = None
depends_on = None


def _create_queue_resources_table() -> None:
    op.create_table(
        "queue_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("queue_tag", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("start_number_online", sa.Integer(), nullable=False),
        sa.Column("max_online_per_day", sa.Integer(), nullable=False),
        sa.Column("default_cabinet", sa.String(length=20), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_resources")),
        sa.UniqueConstraint("code", name=op.f("uq_queue_resources_code")),
        sa.UniqueConstraint("queue_tag", name=op.f("uq_queue_resources_queue_tag")),
    )
    op.create_index(
        op.f("ix_queue_resources_id"), "queue_resources", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_queue_resources_code"), "queue_resources", ["code"], unique=False
    )
    op.create_index(
        op.f("ix_queue_resources_queue_tag"),
        "queue_resources",
        ["queue_tag"],
        unique=False,
    )


def upgrade() -> None:
    _create_queue_resources_table()
    # RLS for the new public table — 0051 convention (0050 sweeps only
    # what exists when it runs; this table is created after it).
    op.execute("ALTER TABLE public.queue_resources ENABLE ROW LEVEL SECURITY")

    # daily_queues dual-owner axis — additive columns only, no XOR and
    # no uniqueness contract in the expand stage.
    op.add_column(
        "daily_queues", sa.Column("queue_resource_id", sa.Integer(), nullable=True)
    )
    # FK follows the 0008/0054 convention (op.create_foreign_key — the
    # repo's idiomatic PG form; add_column with an inline FK was never
    # used in this chain). NO ACTION matches the 0001 specialist_id FK
    # policy: deleting a referenced owner with live history must fail.
    op.create_foreign_key(
        "fk_daily_queues_queue_resource_id",
        "daily_queues",
        "queue_resources",
        ["queue_resource_id"],
        ["id"],
    )
    op.create_index(
        "ix_daily_queues_queue_resource_id",
        "daily_queues",
        ["queue_resource_id"],
    )
    # Relax the doctor axis: NULL is now a legal stored state (the
    # resource owner is on the new column). The XOR contract itself is
    # QD-2D — both/neither is allowed at the DB level in this stage.
    op.alter_column(
        "daily_queues", "specialist_id", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    # Strict by design: SET NOT NULL fails loudly if any resource-owned
    # row (specialist_id IS NULL) exists — history preservation wins,
    # the operator decides how to proceed, not the migration.
    op.alter_column(
        "daily_queues", "specialist_id", existing_type=sa.Integer(), nullable=False
    )
    op.drop_index("ix_daily_queues_queue_resource_id", table_name="daily_queues")
    op.drop_constraint(
        "fk_daily_queues_queue_resource_id",
        "daily_queues",
        type_="foreignkey",
    )
    op.drop_column("daily_queues", "queue_resource_id")
    op.drop_index("ix_queue_resources_queue_tag", table_name="queue_resources")
    op.drop_index("ix_queue_resources_code", table_name="queue_resources")
    op.drop_index("ix_queue_resources_id", table_name="queue_resources")
    op.drop_table("queue_resources")
