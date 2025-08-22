"""tighten NOT NULL on backfilled columns (safe/conditional)

Revision ID: 20250818_0004
Revises: 20250817_0003
Create Date: 2025-08-18 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250818_0004"
down_revision = "20250817_0003"
branch_labels = None
depends_on = None

# Колонки для ужесточения NOT NULL
# (для несуществующих таблиц/колонок миграция пропускает шаг)
TARGETS = {
    "visits": ["created_at", "updated_at", "status"],
    "payments": ["created_at", "updated_at", "status", "amount"],
    "schedules": ["created_at", "updated_at", "status"],
    # исторически могло быть "queues", но в проекте есть "queue_tickets";
    # проверка наличия таблицы гарантирует пропуск, если её нет:
    "queues": ["created_at", "status"],
    "activations": ["active"],
}

# SQL-выражения для безопасной дозаписи NULL перед ужесточением
DEFAULT_SQL = {
    ("visits", "created_at"): "CURRENT_TIMESTAMP",
    ("visits", "updated_at"): "CURRENT_TIMESTAMP",
    ("visits", "status"): "'open'",
    ("payments", "created_at"): "CURRENT_TIMESTAMP",
    ("payments", "updated_at"): "CURRENT_TIMESTAMP",
    ("payments", "status"): "'pending'",
    ("payments", "amount"): "0",
    ("schedules", "created_at"): "CURRENT_TIMESTAMP",
    ("schedules", "updated_at"): "CURRENT_TIMESTAMP",
    ("schedules", "status"): "'active'",
    ("queues", "created_at"): "CURRENT_TIMESTAMP",
    ("queues", "status"): "'waiting'",
    ("activations", "active"): "0",
}


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


def _backfill_if_null(table: str, column: str) -> None:
    expr = DEFAULT_SQL.get((table, column))
    if not expr:
        return
    op.execute(sa.text(f'UPDATE "{table}" SET "{column}" = {expr} WHERE "{column}" IS NULL'))


def _set_not_null(table: str, column: str) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _table_has(insp, table, column):
        return
    if not _is_nullable(insp, table, column):
        return

    # подстрахуемся: дозапишем NULL'ы
    _backfill_if_null(table, column)

    existing_type = _col_type(insp, table, column)

    if bind.dialect.name == "sqlite":
        # SQLite: copy-and-move через batch_alter_table
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


def upgrade() -> None:
    for t, cols in TARGETS.items():
        for c in cols:
            _set_not_null(t, c)


def downgrade() -> None:
    # ослабление обратно (NOT NULL -> NULLABLE) — симметрично
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for t, cols in TARGETS.items():
        for c in cols:
            if not _table_has(insp, t, c):
                continue
            existing_type = _col_type(insp, t, c)
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table(t) as batch:
                    if existing_type is not None:
                        batch.alter_column(c, existing_type=existing_type, nullable=True)
                    else:
                        batch.alter_column(c, nullable=True)
            else:
                if existing_type is not None:
                    op.alter_column(t, c, existing_type=existing_type, nullable=True)
                else:
                    op.alter_column(t, c, nullable=True)
