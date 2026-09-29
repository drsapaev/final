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

ЗАМЕЧАНИЕ О ЗАЯВЛЕННОМ ИНВАРИАНТЕ (review follow-up, owner fact-check
a6cbef): «объём чтения не растёт с глубиной» — сильнее имеющихся
доказательств. Пагинация page/size с точным total — это COUNT (скан
индексного диапазона скоупинга, O(N_scope)) + OFFSET, который проходит
(page-1)*size+size записей индекса — чтение растёт ЛИНЕЙНО с номером
страницы. Что доказано и запинено: постоянство stmts/req (=2) и отсутствие
полной сортировки множества. Для строгого «без роста с глубиной» нужен
keyset + пересмотр стратегии тотал-каунта — задокументированный follow-up
(смена контракта API, решение владельца). Замеры чтения на глубоких
страницах: PG EXPLAIN (ANALYZE, BUFFERS) — протокол в выводе
scripts/bench_derma_history_read_model.py.

CONCURRENTLY: НЕ используется намеренно. Индексы пересоздаются на таблице,
созданной 0075 в ТОМ ЖЕ прогоне upgrade head: в каноническом порядке
rollout (миграции завершены → деплой/рестарт приложения) читателей
таблицы во время пересоздания нет (код до #3521 таблицу не читает вовсе).
CREATE INDEX CONCURRENTLY нельзя выполнить в транзакции, а alembic
использует транзакционный DDL; окно записи listener'а (код #3520-эры)
во время upgrade закрывается порядком deploy (остановить старое
приложение до миграций — см. runbook деплоя).

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
    op.create_index("ix_derma_history_kind_date", _TABLE, _ADMIN_INDEX, unique=False)
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
