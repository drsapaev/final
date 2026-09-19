"""RQ-16.c: queue_direction_public_addresses — public-address registry.

Owner decision 2026-09-17 (E-055, DECISION_PROPOSALS.md §«Решение владельца
по открытой точке RQ-16.c», trace 1a0ae53e51ec7769) resolved the OPEN POINT
of DIRECTION_CONTRACT.md §5: the permanent public address of a direction is
``/q/<public_code>`` where ``public_code`` is an OPAQUE RANDOM server-
generated identifier (12 lowercase Crockford/Base32-like chars, crypto-
random) — never the direction title, never ``QueueProfile.key``.

Contract enforced by THIS revision (E-055 §5 «Registry model»):

- ``public_code`` — globally UNIQUE forever across the whole database
  (``uq_qdpa_public_code``): the URL has no clinic/profile namespace, so a
  used code can never be reassigned — not after retire, not after a hard
  delete;
- at most ONE active address per QueueProfile: partial unique index
  ``uq_qdpa_one_active_per_profile`` on ``queue_profile_id`` WHERE
  ``retired_at IS NULL AND queue_profile_id IS NOT NULL`` (tombstones are
  excluded so a burned code never blocks a fresh linkage);
- ``queue_profile_id`` is NULLABLE with ON DELETE SET NULL — the tombstone
  lifecycle the owner explicitly approved: after a permitted hard delete
  the profile may disappear, but the address row (and its burned code)
  stays reserved forever; a recreated similar profile always gets a NEW
  code;
- canonical form CHECKs: ``length(public_code) = 12`` and
  ``public_code = lower(public_code)`` — one canonical lowercase variant
  in the DB; no locale-dependent transliteration anywhere;
- RLS enabled for parity with the 0046/0050/0062/0064 sweeps —
  ops/scripts/check_public_rls.py (CI backend-tests job, right after
  ``alembic upgrade head``) fails the build on any public table with
  relrowsecurity = false.

Deliberately OUT OF SCOPE (E-055 §13 — RQ-16.c is MODEL only): NO backfill
of public addresses for existing profiles (provisioning existing directions
is a later, separately authorized step — QueueProfile creation MUST NOT
automatically create a public address), no ``/q`` route, no resolve/start
endpoint, no session issuance, no ``permanent_address`` flip (RQ-16.d per
E-055 §8). The table is write-maintained only by future provision flows;
nothing in the current runtime reads or writes it yet.

Additive only: new table, no changes to existing tables. Downgrade drops
the table (pure additive slice; no data rewrite). Merged revisions
(0063/0065/0066/0067) are consumed as-is, never touched.

Revision ID: 0068_direction_public_address
Revises: 0067_daily_queue_start_number
Create Date: 2026-09-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0068_direction_public_address"
down_revision = "0067_daily_queue_start_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "queue_direction_public_addresses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("queue_profile_id", sa.Integer(), nullable=True),
        sa.Column("public_code", sa.String(length=12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["queue_profile_id"],
            ["queue_profiles.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(public_code) = 12", name="ck_qdpa_code_length"
        ),
        sa.CheckConstraint(
            "public_code = lower(public_code)", name="ck_qdpa_code_canonical"
        ),
        sa.UniqueConstraint("public_code", name="uq_qdpa_public_code"),
    )
    op.create_index(
        "ix_queue_direction_public_addresses_id",
        "queue_direction_public_addresses",
        ["id"],
    )
    op.create_index(
        "ix_queue_direction_public_addresses_queue_profile_id",
        "queue_direction_public_addresses",
        ["queue_profile_id"],
    )
    # At most ONE active (retired_at IS NULL) address per profile — the
    # invariant holds even under a concurrent provisioning race; the loser
    # of the race retries with a freshly generated code (E-055 §11).
    op.create_index(
        "uq_qdpa_one_active_per_profile",
        "queue_direction_public_addresses",
        ["queue_profile_id"],
        unique=True,
        postgresql_where=sa.text(
            "retired_at IS NULL AND queue_profile_id IS NOT NULL"
        ),
    )
    # RLS parity with the 0046/0050/0062/0064 sweeps (see docstring).
    op.execute(
        "ALTER TABLE public.queue_direction_public_addresses "
        "ENABLE ROW LEVEL SECURITY"
    )


def downgrade() -> None:
    op.drop_index(
        "uq_qdpa_one_active_per_profile",
        table_name="queue_direction_public_addresses",
    )
    op.drop_index(
        "ix_queue_direction_public_addresses_queue_profile_id",
        table_name="queue_direction_public_addresses",
    )
    op.drop_index(
        "ix_queue_direction_public_addresses_id",
        table_name="queue_direction_public_addresses",
    )
    op.drop_table("queue_direction_public_addresses")
