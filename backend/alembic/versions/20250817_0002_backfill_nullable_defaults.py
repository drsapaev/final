"""backfill NULLs with safe defaults for statuses/timestamps/amounts

Revision ID: 20250817_0002
Revises: 20250817_0001
Create Date: 2025-08-17 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20250817_0002"
down_revision = "20250817_0001"
branch_labels = None
depends_on = None


def _table_has(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    return table in insp.get_table_names() and any(
        c["name"] == column for c in insp.get_columns(table)
    )


def _upd_null(conn, table: str, column: str, expr_sql: str):
    if not _table_has(conn, table, column):
        return
    op.execute(
        sa.text(
            f'UPDATE "{table}" SET "{column}" = '
            + expr_sql
            + f' WHERE "{column}" IS NULL'
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    # timestamps
    _upd_null(bind, "visits", "created_at", "CURRENT_TIMESTAMP")
    _upd_null(bind, "visits", "updated_at", "CURRENT_TIMESTAMP")
    _upd_null(bind, "payments", "created_at", "CURRENT_TIMESTAMP")
    _upd_null(bind, "payments", "updated_at", "CURRENT_TIMESTAMP")
    _upd_null(bind, "schedules", "created_at", "CURRENT_TIMESTAMP")
    _upd_null(bind, "schedules", "updated_at", "CURRENT_TIMESTAMP")
    _upd_null(bind, "queues", "created_at", "CURRENT_TIMESTAMP")

    # statuses — мягкие дефолты
    _upd_null(bind, "visits", "status", "'open'")
    _upd_null(bind, "payments", "status", "'pending'")
    _upd_null(bind, "schedules", "status", "'active'")
    _upd_null(bind, "queues", "status", "'waiting'")

    # numeric
    _upd_null(bind, "payments", "amount", "0")

    # licensing
    _upd_null(bind, "activations", "active", "0")


def downgrade() -> None:
    # backfill данных не откатывается
    pass
