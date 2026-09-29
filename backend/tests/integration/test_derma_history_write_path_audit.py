from __future__ import annotations

"""Аудит путей записи источников read model (a6cbef → 5625c8f1b → 9e6c0f6c1).

Owner fact-check потребовал перечислить реальные способы изменения
источников (EMRRecord, DermaExamination, DermaProcedure, Visit) и
проверить каждый: after_flush listener видит ТОЛЬКО ORM-записи; bulk/Core
SQL и raw SQL его обходят. Раунд 2 закрыл СЛЕПУЮ ЗОНУ первого аудита:
сканер не видел Core-DML по РЕФЛЕКТИРОВАННЫМ таблицам (многострочная
конструкция Table(\\n "visits", _REFLECTED_META, ...)) — а именно так
reschedule-пути писали visit_date, ПРОЕКЦИОННУЮ колонку, и read model
молча расходился с ответами GET /derma/* (P1, репро владельца на SQLite).

Раунд 3 (owner review 9e6c0f6c1) закрыл вторую слепую зону того же
класса: bulk-UPDATE через ORM-Query API —
query(Visit).filter(...).update(..., synchronize_session=False) — не
ловился НИ ОДНИМ из трёх семейств (модельного update(Visit) в цепочке
нет: аргумент update — словарь). Именно так Telegram staff_move_visit
писал visit_date (P1, репро владельца: visits.visit_date=2026-11-05,
derma_history_entries остаётся на 2026-10-20). Четвёртое семейство
query_dml вскрыло ещё ДВА ранее невидимых сайта (visit_confirmation_service
— оба аудированы: не-проекционные колонки).

Полная карта записи (перечислена вручную, зафиксирована пинами):

- ORM-пути (сервисы ЭМК, cutover через save_canonical_emr, dev_seed,
  тесты) — listener покрывает;
- Core update(Visit) в worker.py (reminder-лизы) и visits.py
  (статус-переходы) — только не-проекционные колонки;
- Core-UPDATE visit_date в reschedule-путях (сервис + 2 роута) —
  проекционная колонка: каждый сайт сопровождается
  resync_derma_history_for_visits в ТОЙ ЖЕ транзакции (P1 fix);
- bulk query(Visit).update() в Telegram staff_move_visit —
  проекционная колонка visit_date: сопровождается
  resync_derma_history_for_visits в ТОЙ ЖЕ транзакции (P1 fix,
  owner review 9e6c0f6c1);
- bulk query(Visit).update() в visit_confirmation_service (сброс
  confirmation-токена; статус pending_confirmation→processing) —
  только не-проекционные колонки (вскрыты семейством query_dml
  в раунде 3, аудированы задним числом);
- visit_payment_integration_repository — Core-UPDATE только
  payment_*/lifecycle-колонок, не-проекционных;
- synthetic_seed — raw INSERT INTO/DELETE FROM visits без ЭМК-записей;
- миграции до 0075 — их записи догоняет backfill 0075;
- app/main.py — Table(name, ...) по переменной: рефлексия-warmup, ЧТЕНИЕ;
- app/scripts/migrate_sqlite_to_postgres.py — полная копия БД (SQL
  собирается динамически, статические паттерны не видны; согласована как
  срез, включая derma_history_entries).

Новый Core/raw DML по источникам (вне пинов) ломает скан-контракт: автор
обязан либо писать через ORM, либо звать resync_derma_history_for_visits
(затронутые визиты) или rebuild (backend/scripts/resync_derma_history.py,
полный режим — только в окне обслуживания с остановленной записью) —
иначе read model молча разойдётся с ответами GET /derma/*.

Зона скана: backend/app + alembic/versions + backend/scripts + корневой
scripts (бенчи и legacy-утилиты тоже ходят в БД).
"""

import re
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import update

from app.models.visit import Visit

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent

# Источники проекции (имя модели, SQL-таблица)
SOURCE_MODELS = ("Visit", "EMRRecord", "DermaExamination", "DermaProcedure")
SOURCE_TABLES = (
    "visits",
    "emr_records",
    "derma_examinations",
    "derma_procedures",
)

# Сайты, прошедшие ручной аудит (ключи — пути от корня репо): файл →
# семейство паттернов → (ТОЧНОЕ ожидаемое число хитов, обоснование).
# Счёт-пин двусторонний: НОВЫЙ сайт в файле (+1 к факту) и ИСЧЕЗНУВШИЙ
# сайт (протухание allowlist) одинаково ломают тест — перепинить можно
# только осознанно, обновив обоснование аудита.
AUDITED_SITES: dict[str, dict[str, tuple[int, str]]] = {
    "backend/app/api/v1/endpoints/visits.py": {
        "model_dml": (
            1,
            "Core update(Visit) статус-переходы: values только "
            "status/started_at/finished_at — не-проекционные колонки",
        ),
        "reflected_table": (
            1,
            "_visits(db) — рефлексия для reschedule-роутов: Core-UPDATE "
            "visit_date (ПРОЕКЦИОННАЯ колонка) в обоих роутах "
            "сопровождается resync_derma_history_for_visits(db, [visit_id]) "
            "в той же транзакции (P1 fix, owner fact-check 5625c8f1b)",
        ),
    },
    "backend/app/repositories/visit_payment_integration_repository.py": {
        "reflected_table": (
            1,
            "Core-UPDATE только payment_*/lifecycle-колонок — "
            "не-проекционных (owner fact-check 5625c8f1b)",
        ),
    },
    "backend/app/services/telegram_staff_action_adapter_service.py": {
        "query_dml": (
            1,
            "staff_move_visit: bulk query(Visit).update пишет visit_date "
            "(ПРОЕКЦИОННАЯ колонка) + reminder-поля; сопровождается "
            "resync_derma_history_for_visits(self.db, [visit_id]) в той же "
            "транзакции после refresh(visit), до _commit_or_flush "
            "(P1 fix, owner review 9e6c0f6c1)",
        ),
    },
    "backend/app/services/visit_confirmation_service.py": {
        "query_dml": (
            2,
            "bulk query(Visit).update: сброс confirmation_token/"
            "confirmation_expires_at (claim токена) и status "
            "pending_confirmation→processing — только не-проекционные "
            "колонки; вскрыты семейством query_dml в раунде 3 "
            "(owner review 9e6c0f6c1), аудированы задним числом",
        ),
    },
    "backend/app/services/visits_api_service.py": {
        "reflected_table": (
            1,
            "_visits() — рефлексия для reschedule_visit: Core-UPDATE "
            "visit_date сопровождается "
            "repository.resync_derma_history_for_visit(visit_id) в той же "
            "транзакции (P1 fix); остальные обращения к таблице — чтения",
        ),
    },
    "backend/app/synthetic_seed.py": {
        "raw_dml": (
            2,
            "raw INSERT INTO/DELETE FROM visits без ЭМК-записей: строк "
            "проекции не создаёт и не трогает",
        ),
    },
    "backend/app/tasks/worker.py": {
        "model_dml": (
            7,
            "Core update(Visit) reminder-лизы: reminder_claimed_at/"
            "reminder_generation/status — не-проекционные колонки",
        ),
    },
    "scripts/legacy_scripts/backend/verify_fk_enforcement.py": {
        "raw_dml": (
            2,
            "legacy dev-инструмент проверки FK на scratch-БД: синтетические "
            "INSERT/DELETE visits без ЭМК-записей — строк проекции не "
            "создаёт",
        ),
    },
}

# Корни скана: весь backend-код + миграции + оба scripts-каталога
# (backend и корень репо — бенчи/legacy-утилиты тоже пишут в БД).
SCAN_ROOTS = (
    REPO_ROOT / "backend" / "app",
    REPO_ROOT / "backend" / "alembic" / "versions",
    REPO_ROOT / "backend" / "scripts",
    REPO_ROOT / "scripts",
)

# Четыре ВХОДА в запись источников мимо after_flush listener'а. Первых
# двух не хватало в раунд 1 (update(Visit) и raw «UPDATE visits» не ловят
# Core-DML по рефлектированной Table("visits", ...) — слепая зона стоила
# P1 reschedule-путей, owner fact-check 5625c8f1b); четвёртого не
# хватало в раунд 2 (query(<Source>)…update( — слепая зона стоила P1
# Telegram-пути, owner review 9e6c0f6c1).
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
# Рефлектированная таблица источника — ТРЕТИЙ вход в невидимый Core DML
# (переменные t/table/update() сами по себе не отслеживаются статически —
# ловится точка входа, конструкция таблицы).
# Многострочные конструкции ловятся по полному тексту файла; хит
# атрибутируется строке с именем таблицы.
_REFLECTED_TABLE = re.compile(
    r"\bTable\(\s*[\"'](" + "|".join(SOURCE_TABLES) + r")[\"']"
)

# Четвёртый вход (owner review 9e6c0f6c1): bulk-DML через ORM-Query API —
# query(<Source>).filter(...).update({...}, synchronize_session=False) —
# Core-UPDATE/DELETE, который after_flush listener НЕ видит (Query.update
# не проходит через unit-of-work flush). Ни одно из трёх семейств такую
# цепочку не брало: модельного «update(Visit)» в ней нет — аргумент update
# словарь/колонки. Терминатор update( ИЛИ delete( (legacy Query.delete —
# тот же класс обхода). Цепочка должна быть НЕПРЕРЫВНОЙ: окно 600 символов
# и «запретные якоря» в зазоре (другая .query(, материализаторы чтения
# .first/.first_or_404/.all/.count/.scalar/.scalars/.one/.one_or_none/.get/
# .subquery, .statement, «;») — прочитанная и материализованная цепочка
# не может продолжиться DML. Многострочные цепочки ловятся по полному
# тексту; хит атрибутируется строке .query(<Source>). Статические границы
# семейства (окно, якоря) зафиксированы тестом мощности обнаружения ниже.
_QUERY_DML = re.compile(
    r"\.query\(\s*(?:sa\.|sqlalchemy\.)?\b(?:" + "|".join(SOURCE_MODELS) + r")\b\s*\)"
    r"(?:(?!\.query\(|\.first\(|\.first_or_404\(|\.all\(|\.count\(|"
    r"\.scalar\(|\.scalars\(|\.one\(|\.one_or_none\(|\.get\(|"
    r"\.statement\b|\.subquery\(|;)[\s\S]){0,600}?"
    r"\.(?:update|delete)\s*\("
)


def _scan_text(text: str) -> dict[str, list[int]]:
    """Хиты семейств паттернов: семейство → номера строк."""
    hits: dict[str, list[int]] = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _MODEL_DML.search(line):
            hits.setdefault("model_dml", []).append(line_no)
        elif _TABLE_DML.search(line):
            hits.setdefault("raw_dml", []).append(line_no)
    for match in _REFLECTED_TABLE.finditer(text):
        hits.setdefault("reflected_table", []).append(
            text[: match.end()].count("\n") + 1
        )
    for match in _QUERY_DML.finditer(text):
        hits.setdefault("query_dml", []).append(text[: match.start()].count("\n") + 1)
    return hits


def _scan_file(path: Path) -> dict[str, list[int]]:
    return _scan_text(path.read_text(encoding="utf-8", errors="replace"))


def _revision_number(path: Path) -> int | None:
    match = re.match(r"^(\d+)_", path.name)
    return int(match.group(1)) if match else None


class TestDermaHistoryWritePathAudit:
    """fs-контракт: вся запись источников — ORM, либо явно задокументированная
    Core/raw запись (досинхронизация или аудит колонок)."""

    def test_no_unaudited_core_or_raw_dml_on_sources(self) -> None:
        problems: list[str] = []
        seen_audited: set[str] = set()

        for root in SCAN_ROOTS:
            for path in sorted(root.rglob("*.py")):
                hits = _scan_file(path)
                if not hits:
                    continue
                rel = path.relative_to(REPO_ROOT).as_posix()
                revision = _revision_number(path)
                if revision is not None and revision < 75:
                    # миграции до 0075: их записи догоняет backfill 0075
                    # (0030/0060 — UPDATE visits не-проекционных колонок)
                    continue
                seen_audited.add(rel)
                allowed = AUDITED_SITES.get(rel, {})
                for family, line_nos in hits.items():
                    pin = allowed.get(family)
                    if pin is None:
                        problems.append(
                            f"{rel}: {family} ×{len(line_nos)} "
                            f"(строки {line_nos}) — {AUDITED_HINT}"
                        )
                    elif len(line_nos) > pin[0]:
                        problems.append(
                            f"{rel}: {family}: новых срабатываний больше "
                            f"пина ({len(line_nos)} > {pin[0]}, строки "
                            f"{line_nos}) — {AUDITED_HINT}"
                        )
                    elif len(line_nos) < pin[0]:
                        problems.append(
                            f"{rel}: {family}: allowlist протух "
                            f"({len(line_nos)} < {pin[0]}) — перепинить "
                            "или убрать"
                        )

        for rel in AUDITED_SITES:
            if rel in seen_audited:
                continue
            path = REPO_ROOT / rel
            if not path.exists():
                problems.append(f"{rel}: файл allowlist'а исчез")
            elif not _scan_file(path):
                problems.append(f"{rel}: allowlist без единого хита — протух")

        assert not problems, (
            "Запись источников read model мимо ORM flush "
            "(after_flush listener её не видит — read model разойдётся "
            "с ответами GET /derma/*):\n  "
            + "\n  ".join(problems)
            + "\nИсправление: ORM-объекты через session.add/commit, либо "
            "явная досинхронизация resync_derma_history_for_visits / "
            "rebuild_derma_history_entries "
            "(backend/scripts/resync_derma_history.py), либо расширить "
            "AUDITED_SITES с обоснованием аудита и перепином счётчика."
        )

    def test_scanner_detects_all_four_dml_gateways(self) -> None:
        """P1 (owner fact-check 5625c8f1b): прежний сканер видел только
        update(Visit) и raw «UPDATE visits» — Core-UPDATE по рефлектированной
        таблице (как писали reschedule-пути) проходил мимо. Пин мощности
        обнаружения первых трёх входов, включая МНОГОСТРОЧНУЮ конструкцию
        Table(...) из visits_api_service (однострочный grep её не брал).

        P1 (owner review 9e6c0f6c1): четвёртый вход — bulk-DML через
        ORM-Query API. Пин мощности его обнаружения, включая
        МНОГОСТРОЧНУЮ цепочку staff_move_visit (query и update на разных
        строках) и негативы: прочитанная цепочка (материализатор) не
        продолжается DML; update словаря без query-цепочки; query
        не-источника (Payment) не считается."""
        sample = "\n".join(
            [
                't = Table("visits", meta, autoload_with=bind)',
                "tbl = Table(",
                '    "emr_records", meta, autoload_with=bind,',
                ")",
                'db.execute(text("UPDATE derma_procedures SET x = 1"))',
                'db.execute(update(Visit).values(status="open"))',
                "claimed = (",
                "    self.db.query(Visit)",
                "    .filter(",
                "        Visit.id == visit_id,",
                "        Visit.reminder_generation == generation,",
                "    )",
                "    .update(",
                "        {\"visit_date\": new_visit_date},",
                "        synchronize_session=False,",
                "    )",
                " stale = db.query(EMRRecord).filter(EMRRecord.id == rid).delete()",
                "queue = db.query(Visit).filter(Visit.id == vid).all()",
            ]
        )
        hits = _scan_text(sample)
        # имя таблицы многострочной конструкции — на строке 3
        assert hits["reflected_table"] == [1, 3]
        assert hits["raw_dml"] == [5]
        assert hits["model_dml"] == [6]
        # многострочная query-цепочка: хит атрибутируется строке .query(Visit)
        # (строка 8); однострочный query-delete — строке 17; строка 18 —
        # материализатор .all(), НЕ DML
        assert hits["query_dml"] == [8, 17]

        # негатив: чтения, dict.update и select не триггерят
        clean = "\n".join(
            [
                "sa.select(Visit.__table__)",
                "values = {}; values.update(other)",
                "rows = session.execute(sa.select(emr_tbl.c.id))",
                "visit = db.query(Visit).filter(Visit.id == vid).first()",
                "payment = db.query(Payment).filter(Payment.id == pid)",
                "payment = db.query(Payment).filter(Payment.id == pid).update({})",
            ]
        )
        assert _scan_text(clean) == {}

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

    def test_service_reschedule_updates_derma_read_model(
        self, db_session, test_patient, test_doctor, admin_user
    ) -> None:
        """P1 fix (owner fact-check 5625c8f1b, репро на SQLite): дерма-ЭМК
        с осмотром на visit_date=X, Core-перенос визита через
        VisitsApiService.reschedule_visit на Y — строки read model обязаны
        дать Y (entry_date и payload.examination_date), без дублей.
        Прежний код молча оставлял старую дату (listener Core-UPDATE не
        видит); процедуры несут собственный procedure_date — не меняются."""
        from app.services.visits_api_service import VisitsApiService
        from tests.integration.test_derma_history_read_model import (
            _add_emr,
            _add_visit,
            _derma_emr_data,
            _entries,
        )

        original_date = date.today() - timedelta(days=10)
        visit = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=original_date,
        )
        _add_emr(
            db_session,
            visit=visit,
            data=_derma_emr_data(procedures=1, with_exam=True),
            created_by=admin_user.id,
        )
        assert (
            _entries(db_session, kind="examination", source="emr")[0].entry_date
            == original_date
        )

        new_date = date.today() + timedelta(days=40)
        service = VisitsApiService(db_session)
        service.reschedule_visit(visit_id=visit.id, new_date=new_date)

        # Core DELETE+INSERT не обновляет identity map сессии — перечитываем
        db_session.expire_all()
        exams = _entries(db_session, kind="examination", source="emr")
        procs = _entries(db_session, kind="procedure", source="emr")
        assert len(exams) == 1
        assert exams[0].entry_date == new_date
        assert exams[0].payload["examination_date"] == new_date.isoformat()
        assert len(procs) == 1
        assert procs[0].entry_date == date.today()

    def test_telegram_staff_move_visit_updates_derma_read_model(
        self, db_session, test_patient, test_doctor, admin_user
    ) -> None:
        """P1 (owner review 9e6c0f6c1, репро на SQLite): Telegram
        /move_visit пишет visit_date bulk query(Visit).update(...,
        synchronize_session=False) — Core-UPDATE мимо after_flush
        listener'а (та же слепая зона, что reschedule-пути 5625c8f1b,
        но через ORM-Query API: аргумент update — словарь, модельного
        update(Visit) в цепочке нет). Прежний код: visits.visit_date
        уходит на новую дату, derma_history_entries молча остаётся на
        старой (репро владельца: 2026-11-05 против 2026-10-20) —
        расходились entry_date, payload.examination_date и порядок
        GET /derma/*. Фикс: resync_derma_history_for_visits в той же
        транзакции (после refresh(visit), до _commit_or_flush)."""
        from app.models.online_queue import DailyQueue, OnlineQueueEntry
        from app.services.telegram_staff_action_adapter_service import (
            TelegramStaffActionAdapterService,
        )
        from tests.integration.test_derma_history_read_model import (
            _add_emr,
            _add_visit,
            _derma_emr_data,
            _entries,
        )

        # второй визит с более СТАРОЙ датой: после переноса первого в
        # будущее порядок истории обязан перевернуться (newest-first)
        visit_a = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=date.today() - timedelta(days=30),
        )
        emr_a = _add_emr(
            db_session,
            visit=visit_a,
            data=_derma_emr_data(procedures=0, with_exam=True),
            created_by=admin_user.id,
        )
        visit_b = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=date.today() - timedelta(days=5),
        )
        emr_b = _add_emr(
            db_session,
            visit=visit_b,
            data=_derma_emr_data(procedures=0, with_exam=True),
            created_by=admin_user.id,
        )
        assert len(_entries(db_session, kind="examination", source="emr")) == 2

        # staff_move_visit требует активной queue-связи визита (иначе
        # QueueNotFoundError → rollback) — как в unit-тестах адаптера
        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="derma_history_audit",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        db_session.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                visit_id=visit_b.id,
                number=7,
                patient_id=test_patient.id,
                patient_name="Derma History Audit",
                phone="+998900000199",
                source="desk",
                status="waiting",
            )
        )
        db_session.flush()

        new_date = date.today() + timedelta(days=20)
        result = TelegramStaffActionAdapterService(db_session).staff_move_visit(
            visit_id=visit_b.id,
            new_visit_date=new_date,
            actor_user_id=admin_user.id,
            telegram_chat_id=7704,
            commit=False,
        )
        assert result["success"] is True

        # Core DELETE+INSERT не обновляет identity map сессии — перечитываем
        db_session.expire_all()
        entries = _entries(db_session, kind="examination", source="emr")
        assert len(entries) == 2  # ровно две строки — без дублей
        moved = [e for e in entries if e.record_id == emr_b.id][0]
        assert moved.entry_date == new_date
        assert moved.payload["examination_date"] == new_date.isoformat()
        # порядок истории: перенесённый визит первым (newest-first)
        assert entries[0].record_id == emr_b.id
        # незатронутый визит не тронут scoped-пересчётом
        other = [e for e in entries if e.record_id == emr_a.id][0]
        assert other.entry_date == date.today() - timedelta(days=30)

    def test_core_visit_date_change_desync_detected_and_repaired(
        self, db_session, test_patient, test_doctor, admin_user
    ) -> None:
        """Документация остаточного риска + пин инструмента: «роуерная»
        Core-правка visit_date ВНЕ известных сайтов (data-миграция, DBA,
        внешний скрипт) по-прежнему рассинхронизирует read model —
        известные reschedule-пути теперь самодосинхронизируются (P1 fix),
        для остального есть rebuild (полный — окно обслуживания)."""

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

    def test_scoped_resync_updates_only_target_visits(
        self, db_session, test_patient, test_doctor, admin_user
    ) -> None:
        """P2-3 (owner fact-check 5625c8f1b): scoped-досинхронизация
        (resync_derma_history_for_visits — то же, что CLI --visit-ids)
        НЕ делает глобального DELETE: строки незатронутых визитов
        сохраняют свои pk, затронутый визит репроектируется на новую
        дату. Под трафиком допустим только этот режим (полный rebuild —
        окно обслуживания, см. докстринг rebuild_derma_history_entries)."""
        from app.services.derma_history_projection import (
            resync_derma_history_for_visits,
        )
        from tests.integration.test_derma_history_read_model import (
            _add_emr,
            _add_visit,
            _derma_emr_data,
            _entries,
        )

        visit_a = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=date.today() - timedelta(days=10),
        )
        visit_b = _add_visit(
            db_session,
            patient=test_patient,
            doctor=test_doctor,
            visit_date=date.today() - timedelta(days=5),
        )
        emr_a = _add_emr(
            db_session,
            visit=visit_a,
            data=_derma_emr_data(procedures=0, with_exam=True),
            created_by=admin_user.id,
        )
        emr_b = _add_emr(
            db_session,
            visit=visit_b,
            data=_derma_emr_data(procedures=0, with_exam=True),
            created_by=admin_user.id,
        )
        before = {
            e.record_id: e.id
            for e in _entries(db_session, kind="examination", source="emr")
        }
        assert set(before) == {emr_a.id, emr_b.id}

        rogue_date = date.today() + timedelta(days=30)
        db_session.execute(
            update(Visit)
            .where(Visit.id == visit_a.id)
            .values(visit_date=rogue_date)
            .execution_options(synchronize_session=False)
        )
        counts = resync_derma_history_for_visits(db_session, [visit_a.id])
        db_session.commit()
        db_session.expire_all()

        assert counts == {"visits": 1, "emr_records": 1, "entries": 1}
        after = {
            e.record_id: e
            for e in _entries(db_session, kind="examination", source="emr")
        }
        assert set(after) == {emr_a.id, emr_b.id}
        assert after[emr_a.id].entry_date == rogue_date
        # строка визита B не тронута — тот же pk: глобального DELETE не было
        assert after[emr_b.id].id == before[emr_b.id]
        assert after[emr_b.id].entry_date == date.today() - timedelta(days=5)

    def test_rebuild_reads_sources_with_frozen_explicit_columns(self) -> None:
        """P2-2 (owner fact-check 5625c8f1b): backfill 0075 делегирует
        rebuild'у; SELECT всей таблицы живой модели сломал бы
        `alembic upgrade head` с нуля после добавления колонки в модель
        (в БД на шаге 0075 её ещё нет). Списки колонок заморожены."""
        from app.services.derma_history_projection import (
            _EMR_SOURCE_COLUMNS,
            _LEGACY_EXAMINATION_COLUMNS,
            _LEGACY_PROCEDURE_COLUMNS,
            _VISIT_SOURCE_COLUMNS,
        )

        assert [column.name for column in _EMR_SOURCE_COLUMNS] == [
            "id",
            "visit_id",
            "patient_id",
            "data",
            "created_at",
            "updated_at",
            "is_active",
        ]
        assert [column.name for column in _VISIT_SOURCE_COLUMNS] == [
            "id",
            "visit_date",
            "doctor_id",
        ]
        assert [column.name for column in _LEGACY_EXAMINATION_COLUMNS] == [
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
        ]
        assert [column.name for column in _LEGACY_PROCEDURE_COLUMNS] == [
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
        ]

    def test_projection_module_selects_sources_by_explicit_columns(
        self,
    ) -> None:
        """P2-2 анти-регресс: в SSOT-модуле не должно вернуться
        sa.select(<таблица целиком>) по источникам — только явные колонки
        (пин составов выше) или select(*_COLUMNS)."""
        import app.services.derma_history_projection as projection

        source = Path(projection.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "select(emr_tbl)",
            "select(visit_tbl)",
            "select(table)",
        ):
            assert forbidden not in source, forbidden


AUDITED_HINT = "Core/raw DML по источнику read model; аудита нет в AUDITED_SITES"
