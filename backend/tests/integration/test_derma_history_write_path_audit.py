from __future__ import annotations

"""Аудит путей записи источников read model (review follow-up, a6cbef).

Owner fact-check потребовал перечислить реальные способы изменения
источников (EMRRecord, DermaExamination, DermaProcedure, Visit) и
проверить каждый: after_flush listener видит ТОЛЬКО ORM-записи;
bulk/Core SQL и raw SQL его обходят. Аудит (фиксирован этим тестом):

- ORM-пути (сервисы ЭМК, cutover через save_canonical_emr = add+flush,
  dev_seed, тесты) — listener покрывает;
- Core UPDATE визитов (visits.py статус-переходы, worker.py reminder-лизы)
  — обходят listener, но меняют ТОЛЬКО не-проекционные колонки
  (status/started_at/finished_at/reminder_*) — пин ниже;
- synthetic_seed — raw INSERT INTO visits без ЭМК-записей (строк проекции
  не создаёт в принципе);
- migrate_sqlite_to_postgres — полная копия БД, включая
  derma_history_entries (согласовано как срез);
- миграции до 0075 (0030/0060: UPDATE visits не-проекционных колонок) —
  догоняются backfill 0075.

Новый Core/raw DML по источникам (вне allowlist) ломает скан-пин: автор
обязан либо писать через ORM, либо вызвать rebuild_derma_history_entries
(backend/scripts/resync_derma_history.py) — иначе read model молча
расходится с ответами GET /derma/*.
"""

import re
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import update

from app.models.visit import Visit

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Источники проекции (имя модели, SQL-таблица)
SOURCE_MODELS = ("Visit", "EMRRecord", "DermaExamination", "DermaProcedure")
SOURCE_TABLES = (
    "visits",
    "emr_records",
    "derma_examinations",
    "derma_procedures",
)

# Сайты, прошедшие ручной аудит (файл → обоснование). Пин существования:
# каждая запись allowlist обязана продолжать давать хотя бы одно
# срабатывание сканера — иначе allowlist гниёт.
# Вне allowlist (сканером не помечаются — DML по источникам не содержат,
# аудит задокументирован здесь): app/scripts/migrate_sqlite_to_postgres.py
# — полная копия БД, включая derma_history_entries (согласована как срез);
# app/services/derma_history_projection.py — только Core SELECT источников
# и DML самой read-model таблицы.
AUDITED_SITES: dict[str, str] = {
    "app/api/v1/endpoints/visits.py": (
        "Core update(Visit) статус-переходы: values только "
        "status/started_at/finished_at — не-проекционные колонки"
    ),
    "app/tasks/worker.py": (
        "Core update(Visit) reminder-лизы: reminder_claimed_at/"
        "reminder_generation/status — не-проекционные колонки"
    ),
    "app/synthetic_seed.py": (
        "raw INSERT INTO visits без ЭМК-записей: строк проекции не "
        "создаёт (заголовок модуля про 'EMR records' устарел)"
    ),
}

# Паттерны Core/raw DML по источникам
_MODEL_DML = re.compile(
    r"\b(?:insert|update|delete)\(\s*(?:sa\.|sqlalchemy\.)?\b("
    + "|".join(SOURCE_MODELS)
    + r")\b"
)
_TABLE_DML = re.compile(
    r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:public\.)?\b("
    + "|".join(SOURCE_TABLES)
    + r")\b",
    re.IGNORECASE,
)


def _revision_number(path: Path) -> int | None:
    match = re.match(r"^(\d+)_", path.name)
    return int(match.group(1)) if match else None


def _scan_file(path: Path) -> list[str]:
    hits: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _MODEL_DML.search(line) or _TABLE_DML.search(line):
            hits.append(f"{path.relative_to(BACKEND_ROOT)}:{line_no}")
    return hits


class TestDermaHistoryWritePathAudit:
    """fs-контракт: вся запись источников — ORM или явно аудited Core/raw."""

    def test_no_unaudited_core_or_raw_dml_on_sources(self) -> None:
        unexpected: list[str] = []
        allowlist_hits: dict[str, int] = dict.fromkeys(AUDITED_SITES, 0)

        scan_roots = [
            (BACKEND_ROOT / "app", ".py"),
            (BACKEND_ROOT / "alembic" / "versions", ".py"),
        ]
        for root, suffix in scan_roots:
            for path in sorted(root.rglob(f"*{suffix}")):
                rel = path.relative_to(BACKEND_ROOT).as_posix()
                hits = _scan_file(path)
                if not hits:
                    continue
                if rel in AUDITED_SITES:
                    allowlist_hits[rel] += len(hits)
                    continue
                revision = _revision_number(path)
                if revision is not None and revision < 75:
                    # миграции до 0075: их записи догоняет backfill 0075
                    # (0030/0060 — UPDATE visits не-проекционных колонок)
                    continue
                unexpected.extend(f"{hit}  ({AUDITED_HINT})" for hit in hits)

        assert not unexpected, (
            "Обнаружена запись источников read model мимо ORM flush "
            "(after_flush listener её не видит — read model разойдётся "
            "с ответами GET /derma/*):\n  "
            + "\n  ".join(unexpected)
            + "\nИсправление: ORM-объекты через session.add/commit, либо "
            "явная досинхронизация rebuild_derma_history_entries "
            "(backend/scripts/resync_derma_history.py), либо расширить "
            "AUDITED_SITES с обоснованием аудита."
        )

        stale = [key for key, count in allowlist_hits.items() if count == 0]
        assert not stale, (
            "Allowlist аудита протух: записи больше не дают срабатываний "
            "сканера — убрать их: " + ", ".join(stale)
        )

    def test_audited_status_transition_keeps_projection_intact(
        self, db_session, test_patient, test_doctor, admin_user
    ) -> None:
        """Core update(Visit) по не-проекционным колонкам (status) —
        профиль реальных сайтов visits.py/worker.py — НЕ меняет строки
        read model: рассинхронизации нет."""
        from tests.integration.test_derma_history_read_model import (
            _add_emr,
            _add_visit,
            _derma_emr_data,
            _entries,
        )

        visit = _add_visit(db_session, patient=test_patient, doctor=test_doctor)
        _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(procedures=1, with_exam=True),
            created_by=admin_user.id,
        )
        before = _entries(db_session, kind="examination", source="emr")
        assert len(before) == 1

        db_session.execute(
            update(Visit)
            .where(Visit.id == visit.id)
            .values(status="in_progress")
            .execution_options(synchronize_session=False)
        )
        db_session.commit()

        after = _entries(db_session, kind="examination", source="emr")
        assert [(e.record_id, e.entry_date, e.doctor_id, e.payload) for e in after] == [
            (e.record_id, e.entry_date, e.doctor_id, e.payload) for e in before
        ]

    def test_core_visit_date_change_desync_detected_and_repaired(
        self, db_session, test_patient, test_doctor, admin_user
    ) -> None:
        """Документация риска + пин инструмента: Core UPDATE проекционной
        колонки (visit_date — профиль будущей data-миграции) рассинхронизирует
        read model; rebuild_derma_history_entries восстанавливает parity."""

        from app.services.derma_history_projection import (
            rebuild_derma_history_entries,
        )
        from tests.integration.test_derma_history_read_model import (
            _add_emr,
            _add_visit,
            _derma_emr_data,
            _entries,
        )

        visit = _add_visit(db_session, patient=test_patient, doctor=test_doctor)
        emr = _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(procedures=0, with_exam=True),
            created_by=admin_user.id,
        )
        original_date = _entries(db_session, kind="examination", source="emr")[
            0
        ].entry_date

        # «Роверная» Core-правка даты визита — listener её НЕ видит
        rogue_date = date.today() + timedelta(days=365)
        db_session.execute(
            update(Visit)
            .where(Visit.id == visit.id)
            .values(visit_date=rogue_date)
            .execution_options(synchronize_session=False)
        )
        db_session.commit()
        stale = _entries(db_session, kind="examination", source="emr")
        assert stale[0].entry_date == original_date  # рассинхрон задокументирован

        # Runbook-команда пересчёта восстанавливает parity.
        # expire_all: Core DELETE+INSERT не обновляет identity map сессии —
        # ORM-объекты перечитываются из БД, а не из кеша.
        connection = db_session.connection()
        counts = rebuild_derma_history_entries(connection)
        db_session.expire_all()
        assert counts["emr_entries"] >= 1
        assert counts["deleted"] >= 1
        repaired = _entries(db_session, kind="examination", source="emr")
        assert len(repaired) == 1
        assert repaired[0].entry_date == rogue_date
        assert repaired[0].record_id == emr.id


AUDITED_HINT = "Core/raw DML по источнику read model; аудита нет в AUDITED_SITES"
