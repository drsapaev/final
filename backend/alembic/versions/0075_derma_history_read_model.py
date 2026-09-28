"""Issue #3506 (P2 ретро-ревью #3494): derma history read model.

Полная материализация истории дермы в памяти на каждый запрос страницы
(legacy .all() + merge/sort в Python) — подтверждённый риск масштабирования.
Целевое решение — производная таблица derma_history_entries: та же проекция
(EMR specialty_data + legacy строки, SSOT —
app.services.derma_history_projection), поддерживаемая after_flush
listener'ом при любой ORM-записи источников, с точным порядком канонического
мержа #3494 в колонках сортировки.

Этот PR — шаг 1 из 2 (аддитивный): таблица + backfill + listener.
Эндпоинты GET /derma/examinations и GET /derma/procedures НЕ меняются —
переключение на read model в отдельном PR после выдержки паритет-теста.

SAFETY:
- additive-only DDL: новая таблица, ни одна существующая строка/таблица не
  меняется и не удаляется; downgrade = drop table;
- без FK (производный индекс: строки обслуживаются listener'ом синхронно с
  источниками в той же транзакции, RESTRICT источников уже защищает данные);
- backfill детерминирован: те же функции проекции, что обслуживают
  listener и эндпоинты (никакой эвристики — в отличие от прецедента 0070,
  где backfill был запрещён именно из-за эвристик);
- применение на staging/production НЕ входит в этот PR (прецедент 0070):
  merge не авторизует прогон миграции на живой БД.

Revision ID: 0075_derma_history_read_model
Revises: 0074_join_payload_binding
Create Date: 2026-09-28
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "0075_derma_history_read_model"
down_revision = "0074_join_payload_binding"
branch_labels = None
depends_on = None

_TABLE = "derma_history_entries"


def _backfill(bind: sa.Connection) -> int:
    """Одноразовая проекция существующих источников в read model.

    Использует SSOT-функции app.services.derma_history_projection — те же,
    что работают в after_flush listener'е. Row-объекты core-select
    удовлетворяют проекции (attribute access по именам колонок).
    """
    from app.models.derma_examination import DermaExamination
    from app.models.derma_history import DermaHistoryEntry
    from app.models.derma_procedure import DermaProcedure
    from app.models.emr_v2 import EMRRecord
    from app.models.visit import Visit
    from app.services.derma_history_projection import (
        DERMATOLOGY_SPECIALTY,
        emr_entry_dicts,
        legacy_examination_entry_dicts,
        legacy_procedure_entry_dicts,
    )

    entries_tbl = DermaHistoryEntry.__table__
    emr_tbl = EMRRecord.__table__
    visit_tbl = Visit.__table__

    # Активные дерма-ЭМК: SQL-фильтр по specialty (портативный: JSON_EXTRACT /
    # ->>, подтверждено в #3494), без cap'ов
    records = (
        bind.execute(
            sa.select(emr_tbl).where(
                emr_tbl.c.is_active.is_(True),
                emr_tbl.c.data["specialty"].as_string() == DERMATOLOGY_SPECIALTY,
            )
        )
        .mappings()
        .all()
    )

    visit_ids = {row["visit_id"] for row in records if row["visit_id"] is not None}
    visits: dict[int, Any] = {}
    if visit_ids:
        for row in bind.execute(
            sa.select(visit_tbl).where(visit_tbl.c.id.in_(visit_ids))
        ).all():
            visits[row.id] = row

    entries: list[dict[str, Any]] = emr_entry_dicts(records, visits)

    # Legacy-таблицы заморожены (POST → 410, #3489): проектируем как есть
    legacy_exams = bind.execute(sa.select(DermaExamination.__table__)).all()
    entries.extend(legacy_examination_entry_dicts(legacy_exams))
    legacy_procs = bind.execute(sa.select(DermaProcedure.__table__)).all()
    entries.extend(legacy_procedure_entry_dicts(legacy_procs))

    if entries:
        bind.execute(entries_tbl.insert(), entries)
    return len(entries)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kind",
            "source",
            "record_id",
            "position",
            name="uq_derma_history_entry_identity",
        ),
    )
    op.create_index(
        "ix_derma_history_entries_patient_id", _TABLE, ["patient_id"], unique=False
    )
    op.create_index(
        "ix_derma_history_kind_patient_date",
        _TABLE,
        ["kind", "patient_id", "entry_date", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_derma_history_kind_date",
        _TABLE,
        ["kind", "entry_date", "created_at"],
        unique=False,
    )
    _backfill(op.get_bind())


def downgrade() -> None:
    op.drop_index("ix_derma_history_kind_date", table_name=_TABLE)
    op.drop_index("ix_derma_history_kind_patient_date", table_name=_TABLE)
    op.drop_index("ix_derma_history_entries_patient_id", table_name=_TABLE)
    op.drop_table(_TABLE)
