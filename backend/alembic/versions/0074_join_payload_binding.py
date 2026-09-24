"""RQ-18 follow-up round-5 (PR #3362 review): bind the join session to its
immutable payload and persist the exact original response snapshot.

Owner findings implemented here:
  - P1-3: one session token = one immutable payload. The joined session
    stores a canonical fingerprint (normalized name, digits-only phone,
    telegram id, typed specialist selection) of the FIRST successful
    complete; a replay with a different payload is refused with the
    machine reason ``join_session_payload_mismatch`` instead of serving
    another patient's ticket.
  - P2-1: the replay serves the EXACT original response (the saved
    ``response_snapshot``), so ``queue_length`` / ``estimated_wait_time``
    are the numbers the patient originally received — not a recomputed
    whole-queue count that silently grows as others join.

Both columns are nullable: rows created by ``start_join_session`` (status
``pending``) carry no payload binding yet; it is written in the same
single transaction that flips the session to ``joined``.

Revision ID: 0074_join_payload_binding
Revises: 0073_execution_routing_snapshot
Create Date: 2026-09-22

MERGE-ORDER RESOLUTION (round-8, review P1): the round-6 protocol above
became unexecutable — #3367 merged into main FIRST (49be23d3) under the
name ``0073_execution_routing_snapshot``, so a textual conflict
resolution cannot remove the graph fork: two revisions sharing
``down_revision = 0072_service_executions`` always yield two heads
(verified with real Alembic 1.20 ScriptDirectory: ``alembic heads``
reported MultipleHeads). Fix applied at merge time: this migration is
RENUMBERED to ``0074_join_payload_binding`` and re-parented onto the
merged main's ``0073_execution_routing_snapshot``, restoring the single
linear head 0072 -> 0073_execution_routing_snapshot -> 0074. The pinned
chain-head asserts in the integration tests were advanced accordingly in
the same merge commit, so every commit on the branch stays green.
"""

import sqlalchemy as sa

from alembic import op

revision = "0074_join_payload_binding"
down_revision = "0073_execution_routing_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "queue_join_sessions",
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "queue_join_sessions",
        sa.Column("response_snapshot", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_queue_join_sessions_payload_fingerprint"),
        "queue_join_sessions",
        ["payload_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_queue_join_sessions_payload_fingerprint"),
        table_name="queue_join_sessions",
    )
    op.drop_column("queue_join_sessions", "response_snapshot")
    op.drop_column("queue_join_sessions", "payload_fingerprint")
