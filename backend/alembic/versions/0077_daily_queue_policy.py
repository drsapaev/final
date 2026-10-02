"""Persist the policy identity and online issuance counter for daily queues.

T06.1 is an additive schema expansion. Existing daily queues are classified as
legacy and receive a technical zero counter; this is not a historical count
derived from queue entry source data. Database defaults keep pre-T06.2 writers
compatible while the application rollout remains on the legacy policy.

The downgrade is allowed only before any queue has recorded v1 policy state or
a non-zero issuance count. Once those values carry runtime meaning, removing
them would make a rollback unsafe.

Revision ID: 0077_daily_queue_policy
Revises: 0076_derma_history_read_order
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0077_daily_queue_policy"
down_revision = "0076_derma_history_read_order"
branch_labels = None
depends_on = None

_TABLE = "daily_queues"
_POLICY_VERSION_CHECK = "ck_daily_queues_policy_version"
_ONLINE_ISSUED_COUNT_CHECK = "ck_daily_queues_online_issued_count_nonnegative"
_POLICY_VERSION_CHECK_EXPRESSION = (
    "policy_version IN ('legacy', 'daily_online_issuances_v1')"
)
_ONLINE_ISSUED_COUNT_CHECK_EXPRESSION = "online_issued_count >= 0"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "policy_version",
            sa.String(length=32),
            server_default=sa.text("'legacy'"),
            nullable=False,
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "online_issued_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        _POLICY_VERSION_CHECK,
        _TABLE,
        _POLICY_VERSION_CHECK_EXPRESSION,
    )
    op.create_check_constraint(
        _ONLINE_ISSUED_COUNT_CHECK,
        _TABLE,
        _ONLINE_ISSUED_COUNT_CHECK_EXPRESSION,
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_runtime_policy_state = bind.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM daily_queues "
            "WHERE policy_version <> 'legacy' OR online_issued_count <> 0"
            ")"
        )
    ).scalar_one()
    if has_runtime_policy_state:
        raise RuntimeError(
            "Refusing to remove daily queue policy state after v1 creation or "
            "online issuance counters have become meaningful."
        )

    op.drop_constraint(_ONLINE_ISSUED_COUNT_CHECK, _TABLE, type_="check")
    op.drop_constraint(_POLICY_VERSION_CHECK, _TABLE, type_="check")
    op.drop_column(_TABLE, "online_issued_count")
    op.drop_column(_TABLE, "policy_version")
