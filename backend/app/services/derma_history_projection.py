"""SSOT-проекция унифицированной истории дерматологии (issue #3506).

Каноническая серверная агрегация #3494 объединяет два read-only источника:
дерма-ЭМК (emr/v2, specialty_data) и закрытые legacy-таблицы. Этот модуль —
единственное место, где определена проекция обоих источников в строки
истории (HistoryOut). До появления read model эндпоинты derma.py считали
эту проекцию на каждый запрос в памяти (P2 ретро-ревью #3494); теперь те же
функции питают производную таблицу derma_history_entries:

- функции emr_*_items / legacy_*_items возвращают (row, record_id, position)
  — ровно та же проекция, что и в эндпоинтах, плюс связь с записью-источником;
- after_flush listener поддерживает таблицу автоматически при ЛЮБОЙ записи
  источников через ORM (сервисы ЭМК, cutover, тесты, утилиты) — та же
  транзакция, откат источника откатывает и проекцию; внутри события
  только Core SQL (DML и чтение) — ORM-загрузки в after_flush обходят
  предупреждение SQLAlchemy о не приведённом состоянии identity map;
- resync_derma_history_for_visits — досинхронизация для ИЗВЕСТНЫХ классов
  производственной записи мимо ORM: (а) reschedule-пути пишут visit_date
  Core-UPDATE'ом по рефлектированной таблице «visits» (owner fact-check
  5625c8f1b, P1); (б) Telegram /move_visit — bulk query(Visit).update()
  через ORM-Query API (owner review 9e6c0f6c1, P1). Оба обходят
  after_flush listener; вызов в той же транзакции, что и UPDATE, —
  строки read model визита пересчитываются атомарно;
- миграция 0075 выполняет одноразовый backfill тех же строк (батчами
  keyset, без полной материализации в памяти); rebuild_derma_history_entries
  — тот же пересчёт как runbook-команда для любой внешней правки источников.

Контракт порядка (закреплён паритет-тестом): выборка из read model
ORDER BY entry_date DESC, created_at DESC, source ASC, record_id DESC,
position ASC эквивалентна in-memory мержу #3494 (_merge_history_rows:
newest-first, при равенстве дат EMR раньше legacy, внутри источника —
порядок выборки, числовые позиции).
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.derma_examination import DermaExamination
from app.models.derma_history import DermaHistoryEntry
from app.models.derma_procedure import DermaProcedure
from app.models.emr_v2 import EMRRecord
from app.models.visit import Visit
from app.schemas.derma import (
    DermaExaminationHistoryOut,
    DermaProcedureHistoryOut,
)
from app.services.emr_contract import extract_diagnosis_main

_ENTRY_TABLE = DermaHistoryEntry.__table__

# Колонки источников, которые реально читает проекция — ЯВНЫЕ списки, а не
# sa.select всей таблицы живой модели (owner fact-check 5625c8f1b, P2-2):
# backfill миграции 0075 делегирует rebuild'у, и SELECT колонки, которой
# в БД на шаге 0075 ещё нет, сломал бы `alembic upgrade head` с нуля, как
# только будущая миграция добавит колонку в visits/emr_records/legacy.
# Состав заморожен пином в test_derma_history_write_path_audit.
_EMR_SOURCE_COLUMNS = (
    EMRRecord.__table__.c.id,
    EMRRecord.__table__.c.visit_id,
    EMRRecord.__table__.c.patient_id,
    EMRRecord.__table__.c.data,
    EMRRecord.__table__.c.created_at,
    EMRRecord.__table__.c.updated_at,
    EMRRecord.__table__.c.is_active,
)
_VISIT_SOURCE_COLUMNS = (
    Visit.__table__.c.id,
    Visit.__table__.c.visit_date,
    Visit.__table__.c.doctor_id,
)
_LEGACY_EXAMINATION_COLUMNS = tuple(
    DermaExamination.__table__.c[name]
    for name in (
        "id",
        "patient_id",
        "visit_id",
        "doctor_id",
        "examination_date",
        "skin_type",
        "skin_condition",
        "lesions",
        "distribution",
        "symptoms",
        "diagnosis",
        "treatment_plan",
        "created_at",
        "updated_at",
    )
)
_LEGACY_PROCEDURE_COLUMNS = tuple(
    DermaProcedure.__table__.c[name]
    for name in (
        "id",
        "patient_id",
        "visit_id",
        "doctor_id",
        "procedure_date",
        "procedure_type",
        "area_treated",
        "products_used",
        "results",
        "follow_up",
        "total_cost",
        "created_at",
        "updated_at",
    )
)

# Специальность ЭМК, проекция которой попадает в историю дермы (SSOT;
# SQL-фильтр эндпоинта и Python-фильтр listener'а обязаны совпадать)
DERMATOLOGY_SPECIALTY = "dermatology"

EXAM_TEXT_FIELDS = (
    "skin_type",
    "skin_condition",
    "lesions",
    "distribution",
    "symptoms",
    "treatment_plan",
)


# ---------------------------------------------------------------------------
# Проекция ЭМК (перенесено из endpoints/derma.py без изменения логики)
# ---------------------------------------------------------------------------


def is_dermatology_emr(record: Any) -> bool:
    """Python-зеркало SQL-фильтра specialty эндпоинта (#3494)."""
    data = record.data if isinstance(record.data, dict) else {}
    return data.get("specialty") == DERMATOLOGY_SPECIALTY


def str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def parse_iso_date(value: Any) -> date | None:
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def history_exam_date(visit: Visit | None, record: Any) -> date:
    visit_date = getattr(visit, "visit_date", None)
    if visit_date:
        return visit_date
    if record.created_at:
        return record.created_at.date()
    return date.today()


def derma_exam_has_content(
    specialty_data: dict[str, Any], diagnosis_main: str | None
) -> bool:
    """Пустой каркас дерма-ЭМК (fresh skeleton draft) не должен попадать в историю."""
    if diagnosis_main:
        return True
    for field in EXAM_TEXT_FIELDS:
        value = specialty_data.get(field)
        if isinstance(value, str) and value.strip():
            return True
    localization = specialty_data.get("localization")
    if isinstance(localization, dict):
        if any(isinstance(v, str) and v.strip() for v in localization.values()):
            return True
    return False


def _emr_examination_items(
    records: list[Any], visits: dict[int, Any]
) -> list[tuple[DermaExaminationHistoryOut, int, int]]:
    """Проекция осмотров: (row, record_id, position=0), по ≤1 строке на запись."""
    items: list[tuple[DermaExaminationHistoryOut, int, int]] = []
    for record in records:
        data = record.data if isinstance(record.data, dict) else {}
        specialty_data = data.get("specialty_data")
        if not isinstance(specialty_data, dict):
            specialty_data = {}
        diagnosis_main = extract_diagnosis_main(data)
        if not derma_exam_has_content(specialty_data, diagnosis_main):
            continue
        visit = visits.get(record.visit_id)
        items.append(
            (
                DermaExaminationHistoryOut(
                    id=f"emr-{record.id}",
                    source="emr",
                    patient_id=record.patient_id,
                    visit_id=record.visit_id,
                    doctor_id=getattr(visit, "doctor_id", None),
                    examination_date=history_exam_date(visit, record),
                    skin_type=str(specialty_data.get("skin_type") or ""),
                    skin_condition=str_or_none(specialty_data.get("skin_condition")),
                    lesions=str_or_none(specialty_data.get("lesions")),
                    distribution=str_or_none(specialty_data.get("distribution")),
                    symptoms=str_or_none(specialty_data.get("symptoms")),
                    diagnosis=diagnosis_main,
                    treatment_plan=str_or_none(specialty_data.get("treatment_plan")),
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                ),
                record.id,
                0,
            )
        )
    return items


def _emr_procedure_items(
    records: list[Any], visits: dict[int, Any]
) -> list[tuple[DermaProcedureHistoryOut, int, int]]:
    """Проекция процедур: (row, record_id, index) из specialty_data.cosmetic_procedures."""
    items: list[tuple[DermaProcedureHistoryOut, int, int]] = []
    for record in records:
        data = record.data if isinstance(record.data, dict) else {}
        specialty_data = data.get("specialty_data")
        if not isinstance(specialty_data, dict):
            continue
        entries = specialty_data.get("cosmetic_procedures")
        if not isinstance(entries, list):
            continue
        visit = visits.get(record.visit_id)
        fallback_date = history_exam_date(visit, record)
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            procedure_type = entry.get("procedure_type")
            if not isinstance(procedure_type, str) or not procedure_type.strip():
                continue
            items.append(
                (
                    DermaProcedureHistoryOut(
                        id=f"emr-{record.id}-{index}",
                        source="emr",
                        patient_id=record.patient_id,
                        visit_id=record.visit_id,
                        doctor_id=getattr(visit, "doctor_id", None),
                        procedure_date=(
                            parse_iso_date(entry.get("procedure_date")) or fallback_date
                        ),
                        procedure_type=procedure_type,
                        area_treated=str_or_none(entry.get("area_treated")),
                        products_used=str_or_none(entry.get("products_used")),
                        results=str_or_none(entry.get("results")),
                        follow_up=str_or_none(entry.get("follow_up")),
                        total_cost=None,
                        created_at=record.created_at,
                        updated_at=None,
                    ),
                    record.id,
                    index,
                )
            )
    return items


def emr_examination_rows(
    records: list[Any], visits: dict[int, Any]
) -> list[DermaExaminationHistoryOut]:
    """Строки осмотров из ЭМК (контракт эндпоинта, без связи с записью)."""
    return [row for row, _, _ in _emr_examination_items(records, visits)]


def emr_procedure_rows(
    records: list[Any], visits: dict[int, Any]
) -> list[DermaProcedureHistoryOut]:
    """Строки процедур из ЭМК (контракт эндпоинта, без связи с записью)."""
    return [row for row, _, _ in _emr_procedure_items(records, visits)]


# ---------------------------------------------------------------------------
# Проекция legacy-таблиц (таблицы закрыты для записи: POST → 410, #3489;
# строки существуют только до миграции на ЭМК)
# ---------------------------------------------------------------------------


def _legacy_examination_items(
    rows: list[Any],
) -> list[tuple[DermaExaminationHistoryOut, int, int]]:
    return [(DermaExaminationHistoryOut.model_validate(row), row.id, 0) for row in rows]


def _legacy_procedure_items(
    rows: list[Any],
) -> list[tuple[DermaProcedureHistoryOut, int, int]]:
    return [(DermaProcedureHistoryOut.model_validate(row), row.id, 0) for row in rows]


# ---------------------------------------------------------------------------
# Материализация строк read model
# ---------------------------------------------------------------------------


def _sort_created_at(value: datetime | None) -> datetime:
    """Naive-нормализация created_at — зеркалит _history_sort_key (#3494)."""
    created = value or datetime.min
    if created.tzinfo is not None:
        created = created.replace(tzinfo=None)
    return created


def _entry_dicts(kind: str, items: list[tuple[Any, int, int]]) -> list[dict[str, Any]]:
    """(row, record_id, position) → словари для insert в derma_history_entries."""
    return [
        {
            "kind": kind,
            "source": row.source,
            "record_id": record_id,
            "position": position,
            "patient_id": row.patient_id,
            "visit_id": row.visit_id,
            "doctor_id": row.doctor_id,
            "entry_date": (
                row.examination_date
                if hasattr(row, "examination_date")
                else row.procedure_date
            ),
            "created_at": _sort_created_at(row.created_at),
            "payload": row.model_dump(mode="json"),
        }
        for row, record_id, position in items
    ]


def emr_entry_dicts(records: list[Any], visits: dict[int, Any]) -> list[dict[str, Any]]:
    """Все строки read model для списка ЭМК-записей (оба kind)."""
    return [
        *_entry_dicts("examination", _emr_examination_items(records, visits)),
        *_entry_dicts("procedure", _emr_procedure_items(records, visits)),
    ]


def legacy_examination_entry_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return _entry_dicts("examination", _legacy_examination_items(rows))


def legacy_procedure_entry_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return _entry_dicts("procedure", _legacy_procedure_items(rows))


# ---------------------------------------------------------------------------
# Обслуживание таблицы (только Core SQL: DML и чтение — без ORM-загрузок)
# ---------------------------------------------------------------------------


def _visit_map_for_records(session: Session, records: list[Any]) -> dict[int, Any]:
    """Визиты затронутых записей: ОДИН batched Core-SELECT трёх колонок.

    Специально НЕ ORM-загрузка (session.get/query): after_flush
    выполняется до приведения внутреннего состояния сессии, и SQLAlchemy
    предупреждает, что ORM-запросы внутри события могут путать identity
    map. Core-SELECT видит строки этого же flush'а (та же транзакция:
    INSERT/UPDATE уже выполнены) и не трогает identity map вовсе.
    Row даёт attribute access visit_date/doctor_id — то, что нужно
    проекции (history_exam_date / doctor_id).
    """
    visit_ids = {record.visit_id for record in records if record.visit_id is not None}
    if not visit_ids:
        return {}
    visit_tbl = Visit.__table__
    rows = session.execute(
        sa.select(*_VISIT_SOURCE_COLUMNS).where(visit_tbl.c.id.in_(visit_ids))
    ).all()
    return {row.id: row for row in rows}


def replace_emr_entries(session: Session, records: list[Any]) -> None:
    """Атомарно заменить строки read model для данных ЭМК-записей (оба kind)."""
    remove_emr_entries(session, {record.id for record in records})
    insert_emr_entries(session, records)


def insert_emr_entries(session: Session, records: list[Any]) -> int:
    """Вставить проекцию записей (без удаления — для уже очищенных id).

    Возвращает число вставленных строк (счётчик resync-вызовов и CLI).
    """
    if not records:
        return 0
    entries = emr_entry_dicts(records, _visit_map_for_records(session, records))
    if entries:
        session.execute(_ENTRY_TABLE.insert(), entries)
    return len(entries)


def remove_emr_entries(session: Session, record_ids: set[int]) -> None:
    if not record_ids:
        return
    session.execute(
        _ENTRY_TABLE.delete().where(
            _ENTRY_TABLE.c.source == "emr",
            _ENTRY_TABLE.c.record_id.in_(record_ids),
        )
    )


def resync_derma_history_for_visits(
    session: Session, visit_ids: Iterable[int]
) -> dict[str, int]:
    """Пересчитать строки read model для ЭМК-записей данных визитов.

    P1 (owner fact-check 5625c8f1b): reschedule-пути пишут visit_date
    Core-UPDATE'ом по рефлектированной таблице «visits» — after_flush
    listener видит только ORM-изменения, и derma_history_entries молча
    оставалась на старой дате (расходились entry_date,
    payload.examination_date и порядок ответов GET /derma/*).

    P1 (owner review 9e6c0f6c1): тот же класс обхода через ORM-Query API —
    bulk query(Visit).update(..., synchronize_session=False) в
    Telegram staff_move_visit; фиксирован вызовом здесь (после
    refresh(visit), до _commit_or_flush) в той же транзакции.

    Вызывается в ТОЙ ЖЕ транзакции, что и UPDATE источника: удаление+вставка
    строк визита атомарны с изменением источника — откат мутации откатывает
    и проекцию. Пустой для визитов без ЭМК (дёшево, можно звать всегда).

    Только Core SQL — пригоден и как runbook-инструмент: scoped-режим
    CLI resync_derma_history.py работает через эту функцию и не делает
    глобального DELETE (живой трафик не блокируется надолго).
    """
    ids = {int(visit_id) for visit_id in visit_ids if visit_id is not None}
    if not ids:
        return {"visits": 0, "emr_records": 0, "entries": 0}
    emr_tbl = EMRRecord.__table__
    records = session.execute(
        sa.select(*_EMR_SOURCE_COLUMNS).where(emr_tbl.c.visit_id.in_(ids))
    ).all()
    remove_emr_entries(session, {record.id for record in records})
    entries = insert_emr_entries(
        session,
        [
            record
            for record in records
            if record.is_active and is_dermatology_emr(record)
        ],
    )
    return {"visits": len(ids), "emr_records": len(records), "entries": entries}


def _replace_legacy_entries(
    session: Session, kind: str, rows: list[Any], record_ids: set[int]
) -> None:
    if record_ids:
        session.execute(
            _ENTRY_TABLE.delete().where(
                _ENTRY_TABLE.c.source == "legacy",
                _ENTRY_TABLE.c.kind == kind,
                _ENTRY_TABLE.c.record_id.in_(record_ids),
            )
        )
    entries = _entry_dicts(
        kind,
        (
            _legacy_examination_items(rows)
            if kind == "examination"
            else _legacy_procedure_items(rows)
        ),
    )
    if entries:
        session.execute(_ENTRY_TABLE.insert(), entries)


# ---------------------------------------------------------------------------
# Полный пересчёт (backfill/ребилд): keyset-батчи, память O(batch)
# ---------------------------------------------------------------------------

DEFAULT_REBUILD_BATCH_SIZE = 2000


def rebuild_derma_history_entries(
    bind: sa.Connection, *, batch_size: int = DEFAULT_REBUILD_BATCH_SIZE
) -> dict[str, int]:
    """Пакетированный полный пересчёт read model из источников.

    Review follow-up (owner fact-check a6cbef, backfill 0075): прежний
    backfill читал ВСЕ три источника через .all() и копил строки в памяти
    перед одним insert — неограниченный RSS на живой истории. Здесь:
    keyset-пагинация по id каждого источника (WHERE id > курсор ORDER BY
    id LIMIT batch), визиты — batched IN-запрос на батч, вставка пачками;
    память O(batch_size), не O(история).

    Review follow-up (owner fact-check 5625c8f1b, P2-2): источники читаются
    ЯВНЫМИ списками колонок (_EMR_SOURCE_COLUMNS / _VISIT_SOURCE_COLUMNS /
    _LEGACY_*), а не sa.select всей таблицы живой модели — `alembic upgrade
    head` с нуля не сломается на 0075, когда будущая миграция добавит
    колонку в модель источника (в БД на шаге 0075 её ещё нет).

    Детерминированный полный рефреш: DELETE всех строк + повторная
    проекция теми же SSOT-функциями, что обслуживают listener и
    эндпоинты. Выполняется в транзакции вызывающего (миграция 0075 —
    транзакция alembic; CLI — собственная транзакция): атомарно, откат
    возвращает прежнее состояние таблицы.

    ОПЕРАЦИОННОЕ ОГРАНИЧЕНИЕ (owner fact-check 5625c8f1b, P2-3): полный
    режим держит блокировки строк derma_history_entries до конца ЕДИНОЙ
    транзакции. Под живым трафиком параллельный after_flush listener
    (сохранение ЭМК врача) упирается в блокировку и ждёт, а его INSERT
    после коммита пересчёта может нарушить uq_derma_history_entry_identity
    и уронить сохранение ЭМК. Полный пересчёт — только в окне обслуживания
    с остановленной записью; под трафиком — scoped-режим
    (resync_derma_history_for_visits / CLI --visit-ids): без глобального
    DELETE, блокируется только диапазон затронутых визитов.

    Также runbook-команда для ЛЮБОЙ внешней правки источников мимо ORM
    (Core DML, data-миграции, raw SQL) — единственный класс записей,
    который after_flush listener не видит.
    """
    entries_tbl = DermaHistoryEntry.__table__
    emr_tbl = EMRRecord.__table__
    visit_tbl = Visit.__table__

    deleted = bind.execute(entries_tbl.delete()).rowcount or 0
    counts = {
        "deleted": int(deleted),
        "emr_batches": 0,
        "emr_entries": 0,
        "legacy_examination": 0,
        "legacy_procedure": 0,
    }

    # Активные дерма-ЭМК: SQL-фильтр по specialty (портативный:
    # JSON_EXTRACT / ->>, подтверждено в #3494), keyset по id
    cursor: int = 0
    while True:
        records = bind.execute(
            sa.select(*_EMR_SOURCE_COLUMNS)
            .where(
                emr_tbl.c.id > cursor,
                emr_tbl.c.is_active.is_(True),
                emr_tbl.c.data["specialty"].as_string() == DERMATOLOGY_SPECIALTY,
            )
            .order_by(emr_tbl.c.id)
            .limit(batch_size)
        ).all()
        if not records:
            break
        cursor = records[-1].id
        visit_ids = {
            record.visit_id for record in records if record.visit_id is not None
        }
        visits: dict[int, Any] = {}
        if visit_ids:
            for row in bind.execute(
                sa.select(*_VISIT_SOURCE_COLUMNS).where(visit_tbl.c.id.in_(visit_ids))
            ).all():
                visits[row.id] = row
        entries = emr_entry_dicts(records, visits)
        if entries:
            bind.execute(entries_tbl.insert(), entries)
        counts["emr_batches"] += 1
        counts["emr_entries"] += len(entries)

    # Legacy-таблицы заморожены (POST → 410, #3489): проектируем как есть
    for columns, kind, count_key in (
        (_LEGACY_EXAMINATION_COLUMNS, "examination", "legacy_examination"),
        (_LEGACY_PROCEDURE_COLUMNS, "procedure", "legacy_procedure"),
    ):
        id_column = columns[0]
        cursor = 0
        while True:
            rows = bind.execute(
                sa.select(*columns)
                .where(id_column > cursor)
                .order_by(id_column)
                .limit(batch_size)
            ).all()
            if not rows:
                break
            cursor = rows[-1].id
            entries = (
                legacy_examination_entry_dicts(rows)
                if kind == "examination"
                else legacy_procedure_entry_dicts(rows)
            )
            if entries:
                bind.execute(entries_tbl.insert(), entries)
            counts[count_key] += len(entries)

    return counts


# ---------------------------------------------------------------------------
# after_flush listener: производность по построению
# ---------------------------------------------------------------------------

_listener_state = threading.local()
_listener_installed = False


def _sync_derma_history(session: Session) -> None:
    """Пересчитать строки read model для объектов, изменённых текущим flush."""
    affected_emr: dict[int, Any] = {}
    removed_emr_ids: set[int] = set()
    affected_visit_ids: set[int] = set()
    legacy_exams: dict[int, Any] = {}
    removed_exam_ids: set[int] = set()
    legacy_procs: dict[int, Any] = {}
    removed_proc_ids: set[int] = set()

    for obj in session.new:
        if isinstance(obj, EMRRecord):
            affected_emr[obj.id] = obj
        elif isinstance(obj, DermaExamination):
            legacy_exams[obj.id] = obj
        elif isinstance(obj, DermaProcedure):
            legacy_procs[obj.id] = obj

    for obj in session.dirty:
        if not (
            isinstance(obj, (EMRRecord, DermaExamination, DermaProcedure, Visit))
            and session.is_modified(obj)
        ):
            continue
        if isinstance(obj, EMRRecord):
            affected_emr[obj.id] = obj
        elif isinstance(obj, DermaExamination):
            legacy_exams[obj.id] = obj
        elif isinstance(obj, DermaProcedure):
            legacy_procs[obj.id] = obj
        else:
            affected_visit_ids.add(obj.id)

    for obj in session.deleted:
        if isinstance(obj, EMRRecord):
            removed_emr_ids.add(obj.id)
        elif isinstance(obj, DermaExamination):
            removed_exam_ids.add(obj.id)
        elif isinstance(obj, DermaProcedure):
            removed_proc_ids.add(obj.id)
        elif isinstance(obj, Visit):
            affected_visit_ids.add(obj.id)

    # Изменение визита (дата/врач) меняет проекцию его дерма-ЭМК.
    # Тоже Core-SELECT (не session.query): строки, вставленные этим же
    # flush'ом, видны в транзакции, а identity map не затрагивается.
    if affected_visit_ids:
        emr_tbl = EMRRecord.__table__
        for record in session.execute(
            sa.select(*_EMR_SOURCE_COLUMNS).where(
                emr_tbl.c.visit_id.in_(affected_visit_ids),
                emr_tbl.c.is_active.is_(True),
            )
        ).all():
            affected_emr[record.id] = record

    if not (
        affected_emr
        or removed_emr_ids
        or legacy_exams
        or removed_exam_ids
        or legacy_procs
        or removed_proc_ids
    ):
        return

    if affected_emr or removed_emr_ids:
        # чистим ВСЕ затронутые записи (смена специальности дерма→другая
        # обязана удалять строки), вставляем только активные дерма-ЭМК
        remove_emr_entries(session, removed_emr_ids | set(affected_emr))
        insert_emr_entries(
            session,
            [
                record
                for record in affected_emr.values()
                if record.is_active and is_dermatology_emr(record)
            ],
        )
    if legacy_exams or removed_exam_ids:
        _replace_legacy_entries(
            session, "examination", list(legacy_exams.values()), removed_exam_ids
        )
    if legacy_procs or removed_proc_ids:
        _replace_legacy_entries(
            session, "procedure", list(legacy_procs.values()), removed_proc_ids
        )


def _on_after_flush(session: Session, flush_context: Any) -> None:
    if getattr(_listener_state, "in_flight", False):
        return
    try:
        _listener_state.in_flight = True
        _sync_derma_history(session)
    finally:
        _listener_state.in_flight = False


def install_derma_history_listener() -> None:
    """Идемпотентная установка listener'а на базовый класс Session.

    Класс-уровень: покрывает и app-сессии (SessionLocal), и тестовые
    (conftest sessionmaker) — проекция работает при любой записи через ORM.
    """
    global _listener_installed
    if _listener_installed:
        return
    event.listen(Session, "after_flush", _on_after_flush)
    _listener_installed = True


install_derma_history_listener()
