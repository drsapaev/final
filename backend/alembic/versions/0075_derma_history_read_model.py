"""Issue #3506 (P2 ретро-ревью #3494): derma history read model.

Полная материализация истории дермы в памяти на каждый запрос страницы
(legacy .all() + merge/sort в Python) — подтверждённый риск масштабирования.
Целевое решение — производная таблица derma_history_entries: та же проекция
(EMR specialty_data + legacy строки, SSOT —
app.services.derma_history_projection), поддерживаемая after_flush
listener'ом при любой ORM-записи источников, с точным порядком канонического
мержа #3494 в колонках сортировки.

Шаг 1 из 2 (аддитивный): таблица + backfill + listener. На момент коммита
этого шага эндпоинты GET /derma/examinations и GET /derma/procedures не
менялись; переключены на read model следующим шагом — #3521 (0076),
обе части уже в main: эндпоинты сейчас обслуживаются из этой таблицы,
а рассинхронизация источников искажает фактические ответы API.

REVISED (review follow-up, owner fact-check a6cbef): backfill переписан
с полной материализации трёх источников в памяти (.all() + накопление
перед одним insert) на пакетированный keyset-пересчёт
(rebuild_derma_history_entries, память O(batch)). Ревизия in-place
безопасна: alembic не хеширует тела миграций и не перезапускает
применённые ревизии; проекция детерминирована (тот же результат);
production cutover ещё не выполнялся — именно его и защищает правка.

SAFETY:
- additive-only DDL: новая таблица, ни одна существующая строка/таблица не
  меняется и не удаляется; downgrade = drop table;
- без FK (производный индекс: строки обслуживаются listener'ом синхронно с
  источниками в той же транзакции, RESTRICT источников уже защищает данные);
- RLS включён (конвенция 0051, прецеденты 0058/0072) — CI RLS guard требует
  relrowsecurity=true для всех public-таблиц после upgrade head;
- backfill детерминирован: те же функции проекции, что обслуживают
  listener и эндпоинты (никакой эвристики — в отличие от прецедента 0070,
  где backfill был запрещён именно из-за эвристик); пакетирование меняет
  только ресурсный профиль (RSS/время), не результат;
- применение на staging/production НЕ входит в этот PR (прецедент 0070):
  merge не авторизует прогон миграции на живой БД.

Revision ID: 0075_derma_history_read_model
Revises: 0074_join_payload_binding
Create Date: 2026-09-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0075_derma_history_read_model"
down_revision = "0074_join_payload_binding"
branch_labels = None
depends_on = None

_TABLE = "derma_history_entries"


def _backfill(bind: sa.Connection) -> int:
    """Одноразовая проекция существующих источников в read model.

    Делегирует пакетированному rebuild_derma_history_entries (SSOT-функции
    app.services.derma_history_projection — те же, что работают в
    after_flush listener'е и эндпоинтах). Память O(batch_size), не
    O(история): keyset по id каждого источника, вставка пачками.
    """
    from app.services.derma_history_projection import (
        rebuild_derma_history_entries,
    )

    counts = rebuild_derma_history_entries(bind)
    return (
        counts["emr_entries"]
        + counts["legacy_examination"]
        + counts["legacy_procedure"]
    )


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
    # RLS for the new public table — 0051 convention (0058/0072 precedent);
    # the CI RLS guard (2026-09-02 Supabase incident) requires every public
    # table to have relrowsecurity=true right after upgrade head.
    op.execute("ALTER TABLE public.derma_history_entries ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.derma_history_entries DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_derma_history_kind_date", table_name=_TABLE)
    op.drop_index("ix_derma_history_kind_patient_date", table_name=_TABLE)
    op.drop_index("ix_derma_history_entries_patient_id", table_name=_TABLE)
    op.drop_table(_TABLE)
