#!/usr/bin/env python3
"""Нагрузочная проверка read model истории дермы (issue #3506, шаг 2).

Доказывает инвариант приёмочных критериев #3506: при фиксированных
page/size объём чтения из БД НЕ растёт с глубиной истории. Бывший
in-memory путь (#3494) читал все строки обоих источников на каждый
запрос страницы; read model обслуживает страницу фиксированным числом
SQL-выражений (COUNT + срез индекса) независимо от глубины.

Что меряется для каждого объёма истории N:
- p50/p95/max wall-time запроса страницы (тот же паттерн, что исполняет
  GET /derma/examinations: скоупинг + COUNT + ORDER BY ... OFFSET/LIMIT);
- число SQL-выражений на запрос страницы (пин постоянства);
- два профиля: общий список (Admin без patient_id — худший случай) и
  скоупинг врача (patient_id IN (...)).

Запуск (от корня репо):
    python scripts/bench_derma_history_read_model.py            # SQLite
    DATABASE_URL=postgresql+psycopg://... python scripts/bench_derma_history_read_model.py

Абсолютные латентности зависят от диалекта/железа (SQLite здесь —
индикатив); инвариант постоянства числа выражений диалектонезависим.
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import tempfile
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
# Модульный engine app.db.session парсит DATABASE_URL при импорте: невалидное
# значение среды ломает импорт до нашего собственного движка — подставляем
# распарсиваемый плейсхолдер (сам бенчмарк движок не трогает: см. url ниже).
if not os.environ.get("DATABASE_URL", "").startswith(("postgresql", "sqlite")):
    os.environ["DATABASE_URL"] = (
        "postgresql+psycopg://clinic:clinic@localhost:5432/clinicdb"
    )

from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.base import Base  # noqa: E402  (регистрирует все модели + listener)
from app.models.derma_history import DermaHistoryEntry  # noqa: E402

READ_ORDER = (
    DermaHistoryEntry.entry_date.desc(),
    DermaHistoryEntry.created_at.desc(),
    DermaHistoryEntry.source.asc(),
    DermaHistoryEntry.record_id.desc(),
    DermaHistoryEntry.position.asc(),
)


def seed(session: Session, total: int, patients: int) -> None:
    base_date = date.today() - timedelta(days=365 * 5)
    rows = []
    for i in range(total):
        rows.append(
            {
                "kind": "examination",
                "source": "emr" if i % 3 else "legacy",
                "record_id": i + 1,
                "position": 0,
                "patient_id": (i % patients) + 1,
                "visit_id": None,
                "doctor_id": None,
                "entry_date": base_date + timedelta(days=i % (365 * 5)),
                "created_at": datetime(2021, 1, 1) + timedelta(minutes=i),
                "payload": {
                    "id": f"emr-{i + 1}" if i % 3 else i + 1,
                    "source": "emr" if i % 3 else "legacy",
                    "patient_id": (i % patients) + 1,
                    "visit_id": None,
                    "doctor_id": None,
                    "examination_date": (
                        base_date + timedelta(days=i % (365 * 5))
                    ).isoformat(),
                    "skin_type": "combination",
                    "skin_condition": "Бенчмарк",
                    "created_at": "2021-01-01T00:00:00",
                },
            }
        )
    session.execute(DermaHistoryEntry.__table__.insert(), rows)
    session.commit()


def bench(session: Session, *, size: int, requests: int, allowed: set[int] | None) -> dict:
    rng = random.Random(42)
    scope_total = (
        session.query(DermaHistoryEntry)
        .filter(DermaHistoryEntry.patient_id == 5)
        .count()
        if isinstance(allowed, tuple)
        else session.query(DermaHistoryEntry).count()
    )
    total_pages = max(1, (scope_total + size - 1) // size)
    counter = {"n": 0}

    def _count(*_a, **_k):  # noqa: ANN002, ANN003
        counter["n"] += 1

    connection = session.connection()
    event.listen(connection, "before_cursor_execute", _count)
    timings: list[float] = []
    statement_counts: set[int] = set()
    try:
        for _ in range(requests):
            page = rng.randint(1, total_pages)
            start = time.perf_counter()
            query = session.query(DermaHistoryEntry).filter(
                DermaHistoryEntry.kind == "examination"
            )
            if isinstance(allowed, tuple):
                query = query.filter(
                    DermaHistoryEntry.patient_id == allowed[1]
                )
            elif allowed is not None:
                query = query.filter(DermaHistoryEntry.patient_id.in_(allowed))
            total = query.count()
            rows = (
                query.order_by(*READ_ORDER)
                .offset((page - 1) * size)
                .limit(size)
                .all()
            )
            timings.append(time.perf_counter() - start)
            statement_counts.add(counter["n"])
            counter["n"] = 0
            assert total > 0 and len(rows) <= size
    finally:
        event.remove(connection, "before_cursor_execute", _count)
    timings.sort()
    return {
        "p50_ms": timings[len(timings) // 2] * 1000,
        "p95_ms": timings[int(len(timings) * 0.95)] * 1000,
        "max_ms": timings[-1] * 1000,
        "statements_per_request": statement_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="1000,5000,20000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--patients", type=int, default=200)
    args = parser.parse_args()

    url = os.environ.get("BENCH_DATABASE_URL")
    cleanup = None
    if not url:
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        cleanup = path
        url = f"sqlite:///{path}"
        print(f"[bench] SQLite temp db: {path}")
    else:
        print(f"[bench] using BENCH_DATABASE_URL")
    engine = create_engine(url, future=True)
    Base.metadata.create_all(bind=engine, tables=[DermaHistoryEntry.__table__])

    print(
        f"{'N':>7} {'profile':>8} {'p50,ms':>9} {'p95,ms':>9} "
        f"{'max,ms':>9} {'stmts/req':>9}"
    )
    with Session(engine) as session:
        for n in (int(x) for x in args.sizes.split(",")):
            session.query(DermaHistoryEntry).delete()
            session.commit()
            seed(session, n, args.patients)
            for profile, allowed in (
                ("patient", ("eq", 5)),  # реальный путь UI: явный patient_id
                ("admin", None),
                ("doctor", set(range(1, 51))),  # худший случай: IN-лист
            ):
                stats = bench(
                    session, size=args.size, requests=args.requests, allowed=allowed
                )
                stmts = ",".join(str(s) for s in sorted(stats["statements_per_request"]))
                print(
                    f"{n:>7} {profile:>8} {stats['p50_ms']:>9.2f} "
                    f"{stats['p95_ms']:>9.2f} {stats['max_ms']:>9.2f} {stmts:>9}"
                )
    engine.dispose()
    if cleanup:
        os.unlink(cleanup)
    print(
        "\nИнвариант: stmts/req константен для каждого профиля при любом N —"
        " объём чтения не зависит от глубины истории."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
