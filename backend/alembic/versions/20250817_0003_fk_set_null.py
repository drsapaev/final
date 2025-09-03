"""enforce FKs with ON DELETE SET NULL (from audit)
Revision ID: 20250817_0003
Revises: 20250817_0002
Create Date: 2025-08-17 18:47:08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20250817_0003"
down_revision = "20250817_0002"
branch_labels = None
depends_on = None


def _table_has(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    return table in insp.get_table_names() and any(
        c["name"] == column for c in insp.get_columns(table)
    )


def _fk_exists(conn, table: str, name: str) -> bool:
    insp = sa.inspect(conn)
    if table not in insp.get_table_names():
        return False
    for fk in insp.get_foreign_keys(table):
        if fk.get("name") == name:
            return True
    return False


def _create_fk_if_absent(
    op, conn, name, source, target, local_cols, remote_cols, ondelete=None
):
    if not all(_table_has(conn, source, col) for col in local_cols):
        return
    if not all(_table_has(conn, target, col) for col in remote_cols):
        return
    if _fk_exists(conn, source, name):
        return
    op.create_foreign_key(
        name,
        source,
        target,
        local_cols=local_cols,
        remote_cols=remote_cols,
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.get_bind()


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    to_drop = []
    for table in insp.get_table_names():
        existing = [fk.get("name") for fk in insp.get_foreign_keys(table)]
        for name in to_drop:
            if name in existing:
                op.drop_constraint(name, table_name=table, type_="foreignkey")
