#!/usr/bin/env python3
"""Read-only верификация применения миграций 0075/0076 на живой БД (issue #3506).

Контекст. Миграции 0075_derma_history_read_model (таблица
derma_history_entries + пакетированный backfill + RLS) и
0076_derma_history_read_order (индексы полного порядка с направлениями
колонок) применяются на staging/production вручную оператором — merge не
авторизует прогон на живой БД (прецедент 0070). После применения оператору
нужна механическая проверка критериев приёмки — этот скрипт и есть она.

Гарантия read-only — механизм, а не политика:
- PostgreSQL: соединение открывается с default_transaction_read_only=on —
  ЛЮБАЯ попытка записи отвергается сервером;
- SQLite (локальная отладка самого скрипта): PRAGMA query_only=ON.

Проверки:
 1. alembic_version = 0076_derma_history_read_order (ровно одна строка);
 2. RLS включён на public.derma_history_entries (конвенция 0051; CI RLS
    guard проверяет это на upgrade, здесь — на живой БД);
 3. оба read-индекса 0076: состав колонок И направления (indoption) —
    вс-ASC индекс не обслуживает смешанный ORDER BY канонического мержа
    #3494, хвост уходит в temp-btree сортировку всего множества;
 4. UNIQUE uq_derma_history_entry_identity (защита от двойной проекции);
 5. ПАРИТЕТ: полная повторная проекция источников теми же SSOT-функциями
    (app.services.derma_history_projection: emr_entry_dicts /
    legacy_*_entry_dicts — путь listener'а и backfill), пакетированно
    (keyset по id, память O(batch)), против фактических строк
    derma_history_entries: missing (backfill/прослушка пропустили),
    extra (висячие строки), несовпадения полей (payload включительно);
 6. EXPLAIN канонических страничных запросов (PG): без узла Sort,
    обслуживание индексом полного порядка — доказуемая планом часть
    критерия «объём чтения не растёт с глубиной истории»;
 7. информационно: pg_stat_user_indexes.idx_scan — читает ли приложение
    новые индексы после деплоя (не FAIL: статистика копится со временем).

Проверки 2/3/6/7 — PostgreSQL-only; на другом движке помечаются SKIP
(скрипт отлажен на SQLite: паритет и alembic работают везде).

Запуск (хост клиники, backend-venv; staging ИЛИ prod задаются явно):
  C:\\final\\backend\\.venv\\Scripts\\python.exe ^
    C:\\final\\scripts\\verify_derma_history_read_model.py ^
    --env-file C:\\final\\backend\\.env

  # явная цель (приоритет над --env-file):
  python scripts/verify_derma_history_read_model.py \
    --database-url "postgresql+psycopg://user@host:5432/db"

Цель (host/port/database, БЕЗ пароля) печатается до проверок — оператор
видит, какую именно БД он верифицирует. Код возврата: 0 = FAIL'ов нет,
1 = есть хотя бы один FAIL (годится для runbook-обвязки).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

EXPECTED_HEAD = "0076_derma_history_read_order"
TABLE = "derma_history_entries"

ADMIN_INDEX = "ix_derma_history_kind_date"
DOCTOR_INDEX = "ix_derma_history_kind_patient_date"
PATIENT_INDEX = "ix_derma_history_entries_patient_id"
UNIQUE_CONSTRAINT = "uq_derma_history_entry_identity"


def _cols(spec: str) -> list[tuple[str, bool]]:
    """'kind,entry_date:DESC,...' → [(колонка, is_desc)]."""
    out: list[tuple[str, bool]] = []
    for part in spec.split(","):
        name, _, direction = part.partition(":")
        out.append((name.strip(), direction.strip().upper() == "DESC"))
    return out


# Полный порядок канонического мержа #3494 → направления индексов 0076.
ADMIN_INDEX_COLUMNS = _cols(
    "kind, entry_date:DESC, created_at:DESC, source, record_id:DESC, position"
)
DOCTOR_INDEX_COLUMNS = _cols(
    "kind, patient_id, entry_date:DESC, created_at:DESC, source,"
    " record_id:DESC, position"
)

IDENTITY_FIELDS = ("kind", "source", "record_id", "position")
COMPARE_FIELDS = (
    "patient_id",
    "visit_id",
    "doctor_id",
    "entry_date",
    "created_at",
    "payload",
)

# Ниже какого числа строк вердикт EXPLAIN не строгий: на маленькой таблице
# планировщик PG вправе выбрать seq scan + сортировку — это не дефект 0076.
EXPLAIN_STRICT_MIN_ROWS = 1000


class Check:
    def __init__(self, idx: int, total: int, name: str) -> None:
        self.idx = idx
        self.total = total
        self.name = name
        self.status = "SKIP"
        self.details: list[str] = []

    def done(self, status: str, notes: list[str] | None = None) -> None:
        self.status = status
        self.details.extend(notes or [])

    def __str__(self) -> str:
        head = " [%d/%d] %s" % (self.idx, self.total, self.name)
        pad = max(1, 64 - len(head))
        return "%s %s %s" % (head, "." * pad, self.status)


def mask_url(url: str) -> str:
    """host/port/db для баннера; пароль не печатается никогда."""
    if url.startswith("sqlite"):
        # sqlite:///относительный или sqlite:////абсолютный путь
        return "db=%s" % url.split("sqlite:///", 1)[-1]
    m = re.match(r"^[^:/]+://(?:[^@/]+@)?([^/]+)(?:/([^?]+))?", url)
    if not m:
        return "<не разобрано>"
    host = m.group(1)
    database = (m.group(2) or "").split("?")[0]
    return "host=%s db=%s" % (host, database or "<default>")


def resolve_url(args: argparse.Namespace) -> str:
    if args.database_url:
        return args.database_url
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if args.env_file and args.env_file.is_file():
        try:
            from dotenv import dotenv_values

            env = dotenv_values(args.env_file)
            if env.get("DATABASE_URL"):
                return str(env["DATABASE_URL"])
        except ImportError:
            pass
    sys.exit(
        "Цель не задана: передайте --database-url или --env-file с "
        "DATABASE_URL (backend/.env)."
    )


def make_readonly_engine(url: str) -> sa.Engine:
    if url.startswith("sqlite"):
        engine = sa.create_engine(url, future=True)

        @sa.event.listens_for(engine, "connect")
        def _sqlite_readonly(dbapi_conn, _record):  # noqa: ANN001
            dbapi_conn.execute("PRAGMA query_only=ON")

        return engine
    # PostgreSQL: серверная гарантия read-only на уровне соединения.
    return sa.create_engine(
        url,
        future=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


def _norm_dt(value: Any) -> Any:
    if hasattr(value, "tzinfo") and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _values_equal(expected: Any, stored: Any) -> bool:
    if isinstance(expected, dict) and isinstance(stored, dict):
        if set(expected) != set(stored):
            return False
        return all(_values_equal(expected[k], stored[k]) for k in expected)
    if isinstance(expected, (list, tuple)) and isinstance(
        stored, (list, tuple)
    ):
        return len(expected) == len(stored) and all(
            _values_equal(a, b) for a, b in zip(expected, stored)
        )
    return _norm_dt(expected) == _norm_dt(stored)


def _first_payload_diff(expected: dict, stored: dict) -> str:
    for key in sorted(set(expected) | set(stored)):
        if key not in expected:
            return "payload: ключ %r только в БД" % (key,)
        if key not in stored:
            return "payload: ключ %r только в проекции" % (key,)
        if not _values_equal(expected[key], stored[key]):
            return "payload[%r]: проекция=%r БД=%r" % (
                key,
                expected[key],
                stored[key],
            )
    return "payload: расхождение не локализовано"


def check_alembic(conn, check: Check) -> None:
    try:
        rows = conn.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalars().all()
    except Exception as exc:  # noqa: BLE001
        check.done("FAIL", ["alembic_version не читается: %s" % exc])
        return
    if rows == [EXPECTED_HEAD]:
        check.done("PASS", ["head = %s" % EXPECTED_HEAD])
        return
    if rows == ["0075_derma_history_read_model"]:
        check.done(
            "FAIL",
            [
                "применена только 0075 — 0076 (индексы полного порядка) "
                "отсутствует"
            ],
        )
        return
    check.done(
        "FAIL",
        ["ожидалась ровно одна строка %r, получено: %r" % (EXPECTED_HEAD, rows)],
    )


def check_rls(conn, is_pg: bool, check: Check) -> None:
    if not is_pg:
        check.done("SKIP", ["не-PostgreSQL движок — RLS неприменим"])
        return
    row = conn.execute(
        sa.text(
            "SELECT c.relrowsecurity FROM pg_class c "
            "WHERE c.oid = to_regclass('public.derma_history_entries')"
        )
    ).first()
    if row is None:
        check.done("FAIL", ["таблица public.derma_history_entries не найдена"])
        return
    if row[0]:
        check.done("PASS", ["relrowsecurity = true (конвенция 0051)"])
    else:
        check.done("FAIL", ["RLS ВЫКЛЮЧЕН — включается миграцией 0075"])


def _index_columns(conn, index_name: str) -> list[tuple[str, bool]]:
    sql = sa.text(
        "SELECT a.attname AS col, ((o.x & 1) = 1) AS is_desc, o.n AS ord "
        "FROM pg_index i "
        "JOIN pg_class t ON t.oid = i.indrelid "
        "JOIN pg_class ix ON ix.oid = i.indexrelid "
        "JOIN pg_namespace ns ON ns.oid = t.relnamespace "
        "CROSS JOIN LATERAL unnest(i.indkey::smallint[])"
        " WITH ORDINALITY AS k(attnum, n) "
        "CROSS JOIN LATERAL unnest(i.indoption::smallint[])"
        " WITH ORDINALITY AS o(x, n) "
        "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum "
        "WHERE ns.nspname = 'public' AND t.relname = :tbl "
        "  AND ix.relname = :idx AND k.n = o.n "
        "ORDER BY o.n"
    )
    rows = conn.execute(sql, {"tbl": TABLE, "idx": index_name}).all()
    return [(r[0], bool(r[1])) for r in rows]


def _fmt_cols(columns: list[tuple[str, bool]]) -> str:
    return ", ".join("%s %s" % (name, "DESC" if desc else "ASC") for name, desc in columns)


def check_indexes(conn, is_pg: bool, check: Check) -> None:
    if not is_pg:
        check.done("SKIP", ["не-PostgreSQL движок — pg_index неприменим"])
        return
    notes: list[str] = []
    ok = True
    for name, expected_cols in (
        (ADMIN_INDEX, ADMIN_INDEX_COLUMNS),
        (DOCTOR_INDEX, DOCTOR_INDEX_COLUMNS),
    ):
        actual = _index_columns(conn, name)
        if not actual:
            notes.append("%s: НЕ НАЙДЕН" % name)
            ok = False
            continue
        if actual == expected_cols:
            notes.append("%s: (%s)" % (name, _fmt_cols(actual)))
        else:
            ok = False
            notes.append("%s: СОСТАВ/НАПРАВЛЕНИЯ ОТЛИЧАЮТСЯ от 0076" % name)
            notes.append("  ожидалось: %s" % _fmt_cols(expected_cols))
            notes.append("  фактически: %s" % _fmt_cols(actual))
    extra = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relname = :idx AND n.nspname = 'public'"
        ),
        {"idx": PATIENT_INDEX},
    ).first()
    if extra is None:
        ok = False
        notes.append("%s: НЕ НАЙДЕН (создан 0075)" % PATIENT_INDEX)
    check.done("PASS" if ok else "FAIL", notes)


def check_unique(conn, is_pg: bool, check: Check) -> None:
    if not is_pg:
        check.done("SKIP", ["не-PostgreSQL движок — pg_constraint неприменим"])
        return
    rows = conn.execute(
        sa.text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = to_regclass('public.derma_history_entries') "
            "  AND contype = 'u'"
        )
    ).scalars().all()
    if UNIQUE_CONSTRAINT in rows:
        check.done(
            "PASS",
            ["UNIQUE %s (kind, source, record_id, position)" % UNIQUE_CONSTRAINT],
        )
    else:
        check.done(
            "FAIL",
            ["UNIQUE %s не найден; фактически: %r" % (UNIQUE_CONSTRAINT, rows)],
        )


def check_parity(session: Session, batch_size: int, check: Check) -> None:
    from app.models.derma_examination import DermaExamination
    from app.models.derma_history import DermaHistoryEntry
    from app.models.derma_procedure import DermaProcedure
    from app.models.emr_v2 import EMRRecord
    from app.services.derma_history_projection import (
        _visit_map_for_records,
        emr_entry_dicts,
        is_dermatology_emr,
        legacy_examination_entry_dicts,
        legacy_procedure_entry_dicts,
    )

    expected: dict[tuple, dict] = {}
    duplicates: list[tuple] = []
    emr_total = derma_total = 0

    cursor = 0
    while True:
        rows = session.execute(
            sa.select(EMRRecord.__table__)
            .where(EMRRecord.__table__.c.id > cursor)
            .order_by(EMRRecord.__table__.c.id)
            .limit(batch_size)
        ).all()
        if not rows:
            break
        cursor = rows[-1].id
        emr_total += len(rows)
        derma = [r for r in rows if is_dermatology_emr(r)]
        derma_total += len(derma)
        if derma:
            visits = _visit_map_for_records(session, derma)
            for entry in emr_entry_dicts(derma, visits):
                key = tuple(entry[f] for f in IDENTITY_FIELDS)
                if key in expected:
                    duplicates.append(key)
                expected[key] = entry

    legacy_totals: dict[str, int] = {}
    for label, model, project in (
        ("derma_examinations", DermaExamination, legacy_examination_entry_dicts),
        ("derma_procedures", DermaProcedure, legacy_procedure_entry_dicts),
    ):
        legacy_totals[label] = 0
        cursor = 0
        while True:
            rows = session.execute(
                sa.select(model.__table__)
                .where(model.__table__.c.id > cursor)
                .order_by(model.__table__.c.id)
                .limit(batch_size)
            ).all()
            if not rows:
                break
            cursor = rows[-1].id
            legacy_totals[label] += len(rows)
            for entry in project(rows):
                key = tuple(entry[f] for f in IDENTITY_FIELDS)
                expected[key] = entry

    stored: dict[tuple, dict] = {}
    cursor = 0
    while True:
        rows = session.execute(
            sa.select(DermaHistoryEntry.__table__)
            .where(DermaHistoryEntry.__table__.c.id > cursor)
            .order_by(DermaHistoryEntry.__table__.c.id)
            .limit(batch_size * 5)
        ).mappings()
        batch = rows.all()
        if not batch:
            break
        cursor = batch[-1]["id"]
        for row in batch:
            key = tuple(row[f] for f in IDENTITY_FIELDS)
            stored[key] = {f: row[f] for f in COMPARE_FIELDS}

    missing = sorted(expected.keys() - stored.keys())
    extra = sorted(stored.keys() - expected.keys())
    mismatches: list[tuple[tuple, str]] = []
    for key in sorted(expected.keys() & stored.keys()):
        exp, got = expected[key], stored[key]
        for field in COMPARE_FIELDS:
            if field == "payload":
                if not _values_equal(exp[field], got[field]):
                    mismatches.append(
                        (key, _first_payload_diff(exp[field], got[field]))
                    )
            elif not _values_equal(exp[field], got[field]):
                mismatches.append(
                    (key, "%s: проекция=%r БД=%r" % (field, exp[field], got[field]))
                )

    notes = [
        "источники: ЭМК %d (дерма %d), legacy: %d осмотров / %d процедур"
        % (
            emr_total,
            derma_total,
            legacy_totals["derma_examinations"],
            legacy_totals["derma_procedures"],
        ),
        "ожидаемая проекция: %d строк; в таблице: %d строк"
        % (len(expected), len(stored)),
        "missing (нет в БД): %d" % len(missing),
    ]
    notes.extend("  %r" % (k,) for k in missing[:5])
    notes.append("extra (висячие в БД): %d" % len(extra))
    notes.extend("  %r" % (k,) for k in extra[:5])
    notes.append("несовпадения полей: %d" % len(mismatches))
    notes.extend("  %r: %s" % (k, reason) for k, reason in mismatches[:5])
    if duplicates:
        notes.append("ДУБЛИ ключей проекции: %d %r" % (len(duplicates), duplicates[:3]))

    if not missing and not extra and not mismatches and not duplicates:
        notes.append(
            "паритет полный: проекция SSOT-функциями эквивалентна строкам "
            "derma_history_entries"
        )
        check.done("PASS", notes)
    else:
        check.done("FAIL", notes)


def check_explain(conn, is_pg: bool, check: Check) -> None:
    if not is_pg:
        check.done("SKIP", ["не-PostgreSQL движок — EXPLAIN-план неприменим"])
        return
    total = conn.execute(sa.text("SELECT count(*) FROM %s" % TABLE)).scalar()
    if not total:
        check.done("SKIP", ["таблица пуста — планы не показательны"])
        return
    busiest = conn.execute(
        sa.text(
            "SELECT patient_id FROM %s WHERE kind = 'examination' "
            "GROUP BY patient_id ORDER BY count(*) DESC LIMIT 1" % TABLE
        )
    ).scalar()

    order = (
        "ORDER BY entry_date DESC, created_at DESC, source ASC, "
        "record_id DESC, position ASC"
    )
    queries = []
    if busiest is not None:
        queries.append(
            (
                "doctor-профиль (по пациенту)",
                "SELECT * FROM %s WHERE kind = 'examination' AND patient_id = %d"
                " %s LIMIT 20 OFFSET 40" % (TABLE, int(busiest), order),
                DOCTOR_INDEX,
            )
        )
    queries.append(
        (
            "admin-профиль (без patient_id)",
            "SELECT * FROM %s WHERE kind = 'examination' %s LIMIT 20 OFFSET 40"
            % (TABLE, order),
            ADMIN_INDEX,
        )
    )

    strict = total >= EXPLAIN_STRICT_MIN_ROWS
    notes: list[str] = []
    ok = True
    warned = False
    for label, query, index in queries:
        plan = "\n".join(conn.execute(sa.text("EXPLAIN " + query)).scalars().all())
        uses_index = index in plan
        has_sort = re.search(r"^\s*Sort\b", plan, re.M) is not None
        if uses_index and not has_sort:
            verdict = "PASS"
        elif strict:
            verdict = "FAIL"
            ok = False
        else:
            verdict = "WARN"
            warned = True
        first_line = plan.splitlines()[0] if plan else "<пусто>"
        notes.append("%s: %s — %s" % (label, verdict, first_line))

    if not ok:
        status = "FAIL"
    elif warned:
        status = "WARN"
    else:
        status = "PASS"
    if not strict:
        notes.append(
            "таблица < %d строк: seq scan на маленьком множестве — не дефект"
            % EXPLAIN_STRICT_MIN_ROWS
        )
    check.done(status, notes)


def check_stats(conn, is_pg: bool, check: Check) -> None:
    if not is_pg:
        check.done("SKIP", ["не-PostgreSQL движок — pg_stat неприменим"])
        return
    rows = conn.execute(
        sa.text(
            "SELECT indexrelname, idx_scan FROM pg_stat_user_indexes "
            "WHERE relname = :t ORDER BY indexrelname"
        ),
        {"t": TABLE},
    ).all()
    if not rows:
        check.done("SKIP", ["pg_stat_user_indexes пуст (статистика сброшена?)"])
        return
    notes = ["%s: idx_scan=%s" % (name, scans) for name, scans in rows]
    check.done("PASS", notes)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only верификация применения 0075/0076 (issue #3506)"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=BACKEND_DIR / ".env",
        help="backend/.env с DATABASE_URL (по умолчанию: %(default)s)",
    )
    parser.add_argument(
        "--database-url",
        help="явная цель (staging ИЛИ prod); приоритет над --env-file",
    )
    parser.add_argument(
        "--batch-size", type=int, default=200, help="keyset-батч источников"
    )
    parser.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    url = resolve_url(args)

    # app.* читает env при импорте — цель фиксируется ДО импортов.
    os.environ["DATABASE_URL"] = url
    is_pg = url.startswith("postgresql")
    if not is_pg:
        # SQLite допустим ТОЛЬКО для локальной отладки самого скрипта
        # (runtime-guard app.db.session); на staging/production — PostgreSQL.
        os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
    sys.path.insert(0, str(BACKEND_DIR))
    engine = make_readonly_engine(url)

    checks = [
        Check(1, 7, "Версия Alembic (head = 0076)"),
        Check(2, 7, "RLS на derma_history_entries"),
        Check(3, 7, "Индексы полного порядка 0076 (состав + направления)"),
        Check(4, 7, "UNIQUE %s" % UNIQUE_CONSTRAINT),
        Check(5, 7, "Паритет: проекция SSOT = строки read model"),
        Check(6, 7, "EXPLAIN страничных запросов (без Sort)"),
        Check(7, 7, "Статистика использования индексов"),
    ]

    with engine.connect() as conn:
        check_alembic(conn, checks[0])
        check_rls(conn, is_pg, checks[1])
        check_indexes(conn, is_pg, checks[2])
        check_unique(conn, is_pg, checks[3])
    with Session(engine) as session:
        check_parity(session, args.batch_size, checks[4])
    with engine.connect() as conn:
        check_explain(conn, is_pg, checks[5])
        check_stats(conn, is_pg, checks[6])

    failed = sum(1 for c in checks if c.status == "FAIL")
    passed = sum(1 for c in checks if c.status == "PASS")
    skipped = sum(1 for c in checks if c.status == "SKIP")
    warned = sum(1 for c in checks if c.status == "WARN")

    if args.json:
        print(
            json.dumps(
                {
                    "target": mask_url(url),
                    "engine": "postgresql" if is_pg else url.split("://")[0],
                    "ok": failed == 0,
                    "summary": {
                        "pass": passed,
                        "fail": failed,
                        "skip": skipped,
                        "warn": warned,
                    },
                    "checks": [
                        {"name": c.name, "status": c.status, "details": c.details}
                        for c in checks
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        bar = "=" * 66
        print(bar)
        print(" Верификация read model дермы (миграции 0075/0076, issue #3506)")
        print(" Цель: %s" % mask_url(url))
        print(
            " Режим: READ-ONLY"
            + (" (default_transaction_read_only=on)" if is_pg else " (PRAGMA query_only)")
        )
        print(bar)
        for c in checks:
            print(c)
            for line in c.details:
                print("        %s" % line)
        print(bar)
        summary = " ИТОГ: PASS=%d FAIL=%d SKIP=%d WARN=%d" % (
            passed,
            failed,
            skipped,
            warned,
        )
        print(
            summary
            + ("  → ПРИМЕНЕНИЕ ВЕРИФИЦИРОВАНО" if failed == 0 else "  → ЕСТЬ РАСХОЖДЕНИЯ")
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
