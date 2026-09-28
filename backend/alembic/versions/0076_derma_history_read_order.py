"""Issue #3506 (шаг 2): полный порядок в индексах read model дермы.

Бенчмарк (scripts/bench_derma_history_read_model.py) выявил: индексы 0075
покрывали только префикс ORDER BY (kind, entry_date, created_at) — хвост
порядка (source, record_id, position) SQLite/PG досортировывали через
temp b-tree, ЧИТАЯ ВСЁ множество строк на каждый запрос страницы:
stmts/req был константен (2), но объём чтения и CPU росли O(N log N) —
критерий приёмки #3506 «объём чтения не растёт с глубиной истории» не
выполнялся. EXPLAIN подтверждал: USE TEMP B-TREE FOR LAST 3 TERMS OF
ORDER BY.

Фикс: оба read-индекса расширяются до всех колонок канонического порядка
#3494 — страницы обслуживаются индексом (seek + walk offset/limit), без
сортировки. Повторный бенчмарк: плоская латентность, stmts/req = 2.

SAFETY: только пересоздание двух индексов производной таблицы (drop +
create, те же имена); ни одна строка/таблица не меняется; downgrade
возвращает определение 0075. Применение на staging/production —
прецедент 0070: merge не авторизует прогон на живой БД.

Revision ID: 0076_derma_history_read_order
Revises: 0075_derma_history_read_model
Create Date: 2026-09-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0076_derma_history_read_order"
down_revision = "0075_derma_history_read_model"
branch_labels = None
depends_on = None

_TABLE = "derma_history_entries"

# Направления колонок зеркалят ORDER BY канонического мержа #3494
# (entry_date DESC, created_at DESC, source ASC, record_id DESC,
# position ASC): вс-ASC индекс не обслуживает смешанный порядок — хвост
# уходит в temp-btree сортировку всего множества.
_ADMIN_INDEX = [
    sa.text("kind ASC"),
    sa.text("entry_date DESC"),
    sa.text("created_at DESC"),
    sa.text("source ASC"),
    sa.text("record_id DESC"),
    sa.text("position ASC"),
]
_DOCTOR_INDEX = [
    sa.text("kind ASC"),
    sa.text("patient_id ASC"),
    *_ADMIN_INDEX[1:],
]


def upgrade() -> None:
    op.drop_index("ix_derma_history_kind_date", table_name=_TABLE)
    op.create_index(
        "ix_derma_history_kind_date", _TABLE, _ADMIN_INDEX, unique=False
    )
    op.drop_index("ix_derma_history_kind_patient_date", table_name=_TABLE)
    op.create_index(
        "ix_derma_history_kind_patient_date", _TABLE, _DOCTOR_INDEX, unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_derma_history_kind_patient_date", table_name=_TABLE)
    op.create_index(
        "ix_derma_history_kind_patient_date",
        _TABLE,
        ["kind", "patient_id", "entry_date", "created_at"],
        unique=False,
    )
    op.drop_index("ix_derma_history_kind_date", table_name=_TABLE)
    op.create_index(
        "ix_derma_history_kind_date",
        _TABLE,
        ["kind", "entry_date", "created_at"],
        unique=False,
    )
