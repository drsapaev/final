"""align NOT NULL targets with actual schema (activations.status, skip schedules)

Revision ID: 20250818_0005
Revises: 20250818_0004
Create Date: 2025-08-18 00:15:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250818_0005"
down_revision = "20250818_0004"
branch_labels = None
depends_on = None


def _table_has(insp, table: str, column: str) -> bool:
    return table in insp.get_table_names() and any(c["name"] == column for c in insp.get_columns(table))


def _col_type(insp, table: str, column: str):
    for c in insp.get_columns(table):
        if c["name"] == column:
            return c.get("type")
    return None


def _is_nullable(insp, table: str, column: str) -> bool:
    for c in insp.get_columns(table):
        if c["name"] == column:
            return bool(c.get("nullable", True))
    return True


def _backfill_if_null(table: str, column: str, sql_expr_default: str) -> None:
    op.execute(sa.text(f'UPDATE "{table}" SET "{column}" = {sql_expr_default} WHERE "{column}" IS NULL'))


def upgrade() -> None:
    """Ensure NOT NULL for activations.status; skip schedules (not present)."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    table = "activations"
    column = "status"
    if not _table_has(insp, table, column):
        return

    if _is_nullable(insp, table, column):
        # безопасный backfill: если есть NULL — ставим 'issued'
        _backfill_if_null(table, column, "'issued'")
        existing_type = _col_type(insp, table, column)
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch:
                if existing_type is not None:
                    batch.alter_column(column, existing_type=existing_type, nullable=False)
                else:
                    batch.alter_column(column, nullable=False)
        else:
            if existing_type is not None:
                op.alter_column(table, column, existing_type=existing_type, nullable=False)
            else:
                op.alter_column(table, column, nullable=False)


def downgrade() -> None:
    """Relax activations.status back to NULLABLE (symmetry)."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    table = "activations"
    column = "status"
    if not _table_has(insp, table, column):
        return

    existing_type = _col_type(insp, table, column)
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch:
            if existing_type is not None:
                batch.alter_column(column, existing_type=existing_type, nullable=True)
            else:
                batch.alter_column(column, nullable=True)
    else:
        if existing_type is not None:
            op.alter_column(table, column, existing_type=existing_type, nullable=True)
        else:
            op.alter_column(table, column, nullable=True)
