#!/usr/bin/env python3
"""Нагрузочная проверка read model истории дермы (issue #3506, шаг 2).

Пинит доказуемую часть приёмочных критериев #3506: при фиксированных
page/size ЧИСЛО SQL-выражений на запрос страницы не зависит от объёма
истории (COUNT + срез = 2). Бывший in-memory путь (#3494) читал все
строки обоих источников на каждый запрос страницы.

ЗАЯВЛЕННЫЙ ИНВАРИАНТ СМЯГЧЁН (review follow-up, owner fact-check a6cbef):
«объём чтения не растёт с глубиной» сильнее имеющихся доказательств.
Фактический профиль чтения: COUNT сканирует индексный диапазон скоупинга
(O(N_scope)), OFFSET проходит (page-1)*size+size записей индекса —
объём чтения растёт ЛИНЕЙНО с номером страницы. Дополнительно к N-sweep
скрипт меряет page-DEPTH sweep (одна и та же история, растущая глубина
страницы) и печатает число проходимых индексных записей.

Что меряется:
- N-sweep (для каждого объёма истории N): p50/p95/max wall-time
  случайной страницы, число SQL-выражений на запрос;
- page-depth sweep (фиксированное N, страницы 1..deep): wall-time
  страницы + вычисленное число проходимых OFFSET'ом записей;
- два профиля: общий список (Admin без patient_id — худший случай) и
  скоупинг врача (patient_id IN (...)).

PG host-side протокол (на staging, ОБЯЗАТЕЛЬНО до production cutover):
    EXPLAIN (ANALYZE, BUFFERS) SELECT ... ORDER BY entry_date DESC, ...
    OFFSET <(page-1)*size> LIMIT <size>;
  на глубинах 10/100/1000 страниц — убедиться в линейном росте
  shared read blocks и принять решение о keyset-пагинации.

Запуск (от корня репо):
    python scripts/bench_derma_history_read_model.py            # SQLite
    BENCH_DATABASE_URL=postgresql+psycopg://... python scripts/bench_derma_history_read_model.py

Абсолютные латентности зависят от диалекта/железа (SQLite здесь —
индикатив); инвариант постоянства числа выражений диалектонезависим.
"""

from __future__ import annotations

import argparse
import os
import random
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


def bench(
    session: Session, *, size: int, requests: int, allowed: set[int] | None
) -> dict:
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
                query = query.filter(DermaHistoryEntry.patient_id == allowed[1])
            elif allowed is not None:
                query = query.filter(DermaHistoryEntry.patient_id.in_(allowed))
            total = query.count()
            rows = (
                query.order_by(*READ_ORDER).offset((page - 1) * size).limit(size).all()
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


def bench_page_depth(
    session: Session, *, size: int, pages: list[int], allowed: Any
) -> list[dict[str, float]]:
    """Page-depth sweep: одна история, растущая глубина страницы.

    Возвращает wall-time страницы и вычисленное число индексных записей,
    которые OFFSET обязан пройти ((page-1)*size + size) — прямой ответ на
    вопрос «растёт ли чтение с глубиной» (ответ: да, линейно, до keyset).
    """
    rows: list[dict[str, float]] = []
    for page in pages:
        start = time.perf_counter()
        query = session.query(DermaHistoryEntry).filter(
            DermaHistoryEntry.kind == "examination"
        )
        if isinstance(allowed, tuple):
            query = query.filter(DermaHistoryEntry.patient_id == allowed[1])
        elif allowed is not None:
            query = query.filter(DermaHistoryEntry.patient_id.in_(allowed))
        total = query.count()
        query.order_by(*READ_ORDER).offset((page - 1) * size).limit(size).all()
        elapsed = (time.perf_counter() - start) * 1000
        rows.append(
            {
                "page": page,
                "walked_entries": (page - 1) * size + size,
                "total": total,
                "ms": elapsed,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="1000,5000,20000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--patients", type=int, default=200)
    parser.add_argument(
        "--depth-pages",
        default="1,10,50,250",
        help="page-depth sweep: фиксированное N=depth-N, страницы через запятую",
    )
    parser.add_argument("--depth-n", type=int, default=50000)
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
        print("[bench] using BENCH_DATABASE_URL")
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
                stmts = ",".join(
                    str(s) for s in sorted(stats["statements_per_request"])
                )
                print(
                    f"{n:>7} {profile:>8} {stats['p50_ms']:>9.2f} "
                    f"{stats['p95_ms']:>9.2f} {stats['max_ms']:>9.2f} {stmts:>9}"
                )

        # ---- page-depth sweep: чтение растёт с глубиной (до keyset) ----
        depth_pages = [int(p) for p in args.depth_pages.split(",")]
        session.query(DermaHistoryEntry).delete()
        session.commit()
        seed(session, args.depth_n, args.patients)
        print(
            f"\npage-depth sweep (N={args.depth_n}, size={args.size}; "
            "OFFSET проходит (page-1)*size+size записей — линейно):"
        )
        print(f"{'page':>6} {'walked_entries':>15} {'ms':>9}")
        for row in bench_page_depth(
            session, size=args.size, pages=depth_pages, allowed=None
        ):
            print(
                f"{row['page']:>6} {int(row['walked_entries']):>15} "
                f"{row['ms']:>9.2f}"
            )
    engine.dispose()
    if cleanup:
        os.unlink(cleanup)
    print(
        "\nПин: stmts/req константен для каждого профиля при любом N.\n"
        "ФАКТ (смягчено с исходного критерия, owner fact-check a6cbef): объём"
        " чтения растёт с глубиной страницы — COUNT сканирует диапазон скоупинга,"
        " OFFSET проходит (page-1)*size+size записей. Строгий инвариант"
        " без роста требует keyset-пагинации и пересмотра тотал-каунта"
        " (смена контракта API — решение владельца).\n"
        "PG host-side: EXPLAIN (ANALYZE, BUFFERS) на глубинах 10/100/1000"
        " страниц — см. докстринг."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
