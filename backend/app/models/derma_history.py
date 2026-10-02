from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class DermaHistoryEntry(Base):
    """Derived read-model row for the unified derma history (issue #3506).

    Одна строка = один элемент истории дерматологии: проекция активной
    дерма-ЭМК (source="emr") или строки закрытой legacy-таблицы
    (source="legacy"). Таблица обслуживается ТОЛЬКО автоматически —
    after_flush listener'ом (app.services.derma_history_projection) и
    backfill'ом миграции 0075; клиенты и сервисы никогда не пишут в неё
    напрямую. Это производный индекс, а не второй источник истины:
    SSOT остаются emr_records и legacy-таблицы.

    payload хранит полный HistoryOut-словарь — ровно ту проекцию, которую
    возвращают GET /derma/examinations и GET /derma/procedures. Скалярные
    колонки воспроизводят канонический порядок мержа in-memory реализации
    (#3494): ORDER BY entry_date DESC, created_at DESC, source ASC,
    record_id DESC, position ASC эквивалентен стабильному Python-мержу
    (тай-брейки: EMR раньше legacy, внутри источника — порядок выборки,
    позиции числовые).

    FK намеренно отсутствуют: строки удаляются listener'ом синхронно с
    источником (та же транзакция), каскады не нужны; RESTRICT из
    emr_records/legacy уже защищает источники от удаления.
    """

    __tablename__ = "derma_history_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # examination | procedure — какой из двух GET-эндпоинтов обслуживает строку
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # emr | legacy
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    # id EMR-записи или id строки legacy-таблицы (уникален внутри (kind, source))
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # позиция внутри записи: для процедур — индекс в ИСХОДНОМ массиве
    # источника (canonical: index; alias: len(canonical)+index), не плотный
    # display-индекс — разрывы при пропуске invalid-записей допустимы;
    # 0 для остальных kind
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    visit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doctor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # дата осмотра/процедуры из сортировочного ключа канонического мержа
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    # created_at из сортировочного ключа (naive; datetime.min при None —
    # зеркалит _history_sort_key из #3494)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # полный HistoryOut-словарь (model_dump(mode="json"))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "kind",
            "source",
            "record_id",
            "position",
            name="uq_derma_history_entry_identity",
        ),
        # doctor-scoped список: kind + IN(patient_id) + полный порядок.
        # Направления колонок зеркалят ORDER BY запроса (смешанный
        # DESC/ASC не обслуживается вс-ASC индексом — хвост уходит в
        # temp-btree сортировку всего множества), иначе объём чтения
        # растёт с глубиной истории.
        Index(
            "ix_derma_history_kind_patient_date",
            "kind",
            "patient_id",
            text("entry_date DESC"),
            text("created_at DESC"),
            "source",
            text("record_id DESC"),
            "position",
        ),
        # общий список (Admin без patient_id): полный порядок запроса
        Index(
            "ix_derma_history_kind_date",
            "kind",
            text("entry_date DESC"),
            text("created_at DESC"),
            "source",
            text("record_id DESC"),
            "position",
        ),
    )
