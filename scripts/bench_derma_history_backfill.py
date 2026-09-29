#!/usr/bin/env python3
"""Бенчмарк backfill 0075: старая полная материализация vs пакетированный rebuild.

Review follow-up (owner fact-check a6cbef, finding «Backfill 0075»):
требование — пакетная обработка и замер времени/памяти на синтетическом
объёме, близком к верхней ожидаемой нагрузке, ДО production-применения.

Сравнивает на ОДНИХ И ТЕХ ЖЕ синтетических источниках:
- OLD — точная копия алгоритма backfill 0075 до ревизии: три .all() по
  источникам, накопление всех строк в списке, один insert;
- NEW — rebuild_derma_history_entries (keyset-батчи, память O(batch)).

Каждая реализация исполняется в ОТДЕЛЬНОМ процессе-потомке, чтобы
peak RSS (ru_maxrss) был чистым на прогон. Синтетика по умолчанию:
40k дерма-ЭМК (каждая с осмотром + 2 процедурами = 120k строк read model)
+ 10k legacy-осмотров + 10k legacy-процедур.

Запуск (от корня репо):
    python scripts/bench_derma_history_backfill.py
    python scripts/bench_derma_history_backfill.py --emr 100000 --legacy 25000

SQLite здесь — индикатив механики памяти/батчей; абсолютные тайминги PG
зависят от железа. PG host-side: тот же скрипт с
BENCH_DATABASE_URL=postgresql+psycopg://... (create_all + Core-insert
синтетики работают на обоих диалектах).
"""

from __future__ import annotations

import argparse
import os
import resource
import subprocess
import sys
import tempfile
import time
from datetime import UTC, date, datetime, timedelta

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))
if not os.environ.get("DATABASE_URL", "").startswith(("postgresql", "sqlite")):
    os.environ["DATABASE_URL"] = (
        "postgresql+psycopg://clinic:clinic@localhost:5432/clinicdb"
    )
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")

import sqlalchemy as sa  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.models.derma_examination import DermaExamination  # noqa: E402
from app.models.derma_history import DermaHistoryEntry  # noqa: E402
from app.models.derma_procedure import DermaProcedure  # noqa: E402
from app.models.emr_v2 import EMRRecord  # noqa: E402
from app.models.visit import Visit  # noqa: E402


def _peak_rss_mb() -> float:
    # ru_maxrss на Linux — KiB
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def seed_sources(engine, *, emr_count: int, legacy_count: int) -> None:
    """Синтетика источников Core-insert'ами (мимо listener'а — это бенч)."""
    from app.models.patient import Patient

    patient_tbl = Patient.__table__
    with engine.begin() as conn:
        exists = conn.execute(
            sa.select(sa.func.count()).select_from(patient_tbl)
        ).scalar_one()
        if not exists:
            conn.execute(
                patient_tbl.insert().values(
                    first_name="Bench",
                    last_name="Derma",
                    birth_date=date(1990, 1, 1),
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
    base = date.today() - timedelta(days=365 * 5)
    visit_tbl, emr_tbl = Visit.__table__, EMRRecord.__table__
    exam_tbl, proc_tbl = DermaExamination.__table__, DermaProcedure.__table__
    now = datetime.now(UTC).replace(tzinfo=None)
    batch = 2000
    with engine.begin() as conn:
        visit_id_base = conn.execute(
            sa.select(sa.func.coalesce(sa.func.max(visit_tbl.c.id), 0))
        ).scalar_one()
    for start in range(0, emr_count, batch):
        chunk = min(batch, emr_count - start)
        first_id = visit_id_base + start + 1
        visits = [
            {
                "id": first_id + i,
                "patient_id": 1,
                "doctor_id": None,
                "visit_date": base + timedelta(days=(start + i) % 1825),
                "status": "closed",
                "source": "desk",
                "department": "dermatology",
                "created_at": now,
                "updated_at": now,
            }
            for i in range(chunk)
        ]
        with engine.begin() as conn:
            conn.execute(visit_tbl.insert(), visits)
        emrs = [
            {
                "patient_id": 1,
                "visit_id": first_id + i,
                "version": 1,
                "data": {
                    "specialty": "dermatology",
                    "diagnosis": {"main": "Розацеа"},
                    "specialty_data": {
                        "skin_type": "combination",
                        "cosmetic_procedures": [
                            {"procedure_type": f"Процедура {j}"} for j in range(2)
                        ],
                    },
                },
                "status": "draft",
                "created_by": 1,
                "created_at": now,
                "updated_at": now,
                "is_active": True,
                "row_version": 1,
            }
            for i in range(chunk)
        ]
        with engine.begin() as conn:
            conn.execute(emr_tbl.insert(), emrs)
    for start in range(0, legacy_count, batch):
        chunk = min(batch, legacy_count - start)
        exams = [
            {
                "patient_id": 1,
                "visit_id": None,
                "doctor_id": None,
                "examination_date": base + timedelta(days=i % 1825),
                "skin_type": "dry",
                "created_at": now,
            }
            for i in range(chunk)
        ]
        procs = [
            {
                "patient_id": 1,
                "visit_id": None,
                "doctor_id": None,
                "procedure_date": base + timedelta(days=i % 1825),
                "procedure_type": f"Чистка {i}",
                "created_at": now,
            }
            for i in range(chunk)
        ]
        with engine.begin() as conn:
            conn.execute(exam_tbl.insert(), exams)
            conn.execute(proc_tbl.insert(), procs)


def run_old_backfill(engine) -> int:
    """ТОЧНАЯ копия алгоритма 0075 до ревизии (полная материализация)."""
    from app.services.derma_history_projection import (
        DERMATOLOGY_SPECIALTY,
        emr_entry_dicts,
        legacy_examination_entry_dicts,
        legacy_procedure_entry_dicts,
    )

    entries_tbl = DermaHistoryEntry.__table__
    emr_tbl = EMRRecord.__table__
    visit_tbl = Visit.__table__
    with engine.begin() as bind:
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
        visits: dict[int, object] = {}
        # SQLite-лимит переменных: IN чанками (профиль памяти НЕ меняет —
        # records/entries всё равно материализуются целиком)
        visit_id_list = sorted(visit_ids)
        for chunk_start in range(0, len(visit_id_list), 500):
            chunk = visit_id_list[chunk_start : chunk_start + 500]
            for row in bind.execute(
                sa.select(visit_tbl).where(visit_tbl.c.id.in_(chunk))
            ).all():
                visits[row.id] = row
        entries: list[dict] = emr_entry_dicts(records, visits)
        legacy_exams = bind.execute(sa.select(DermaExamination.__table__)).all()
        entries.extend(legacy_examination_entry_dicts(legacy_exams))
        legacy_procs = bind.execute(sa.select(DermaProcedure.__table__)).all()
        entries.extend(legacy_procedure_entry_dicts(legacy_procs))
        if entries:
            bind.execute(entries_tbl.insert(), entries)
        return len(entries)


def run_new_backfill(engine, batch_size: int) -> int:
    from app.services.derma_history_projection import (
        rebuild_derma_history_entries,
    )

    with engine.begin() as bind:
        counts = rebuild_derma_history_entries(bind, batch_size=batch_size)
    return (
        counts["emr_entries"]
        + counts["legacy_examination"]
        + counts["legacy_procedure"]
    )


def child_mode(db_url: str, impl: str, batch_size: int) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(db_url)
    start = time.perf_counter()
    if impl == "old":
        total = run_old_backfill(engine)
    else:
        total = run_new_backfill(engine, batch_size)
    elapsed = time.perf_counter() - start
    print(
        f"RESULT impl={impl} total={total} seconds={elapsed:.2f} "
        f"peak_rss_mb={_peak_rss_mb():.1f}"
    )
    engine.dispose()


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        # --child <url> <impl> <batch> — до argparse: свои аргументы
        child_mode(sys.argv[2], sys.argv[3], int(sys.argv[4]))
        return 0

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emr", type=int, default=40000)
    parser.add_argument("--legacy", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--keep-db", default=None, help="переиспользовать файл БД")
    args = parser.parse_args()

    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        return 0

    url = os.environ.get("BENCH_DATABASE_URL")
    cleanup = None
    if not url:
        if args.keep_db and os.path.exists(args.keep_db):
            url = f"sqlite:///{args.keep_db}"
            print(f"[bench] reusing db: {args.keep_db}")
        else:
            handle, path = tempfile.mkstemp(suffix=".db")
            os.close(handle)
            cleanup = path
            url = f"sqlite:///{path}"
            print(f"[bench] SQLite temp db: {path}")
    else:
        print("[bench] using BENCH_DATABASE_URL")

    from sqlalchemy import create_engine

    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    t0 = time.perf_counter()
    seed_sources(engine, emr_count=args.emr, legacy_count=args.legacy)
    print(
        f"[bench] seeded sources: emr={args.emr} legacy_exams={args.legacy} "
        f"legacy_procs={args.legacy} in {time.perf_counter() - t0:.1f}s"
    )
    engine.dispose()

    env = dict(os.environ)
    results = {}
    for impl in ("old", "new"):
        proc = subprocess.run(
            [
                sys.executable,
                os.path.abspath(__file__),
                "--child",
                url,
                impl,
                str(args.batch_size),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")]
        if not line:
            print(proc.stdout, proc.stderr)
            print(f"[bench] impl={impl} FAILED", file=sys.stderr)
            return 1
        fields = dict(part.split("=", 1) for part in line[0].split()[1:])
        results[impl] = fields

    print(f"\n{'impl':>5} {'entries':>8} {'seconds':>8} {'peak RSS MB':>12}")
    for impl, fields in results.items():
        print(
            f"{impl:>5} {fields['total']:>8} {fields['seconds']:>8} "
            f"{fields['peak_rss_mb']:>12}"
        )
    if cleanup and not args.keep_db:
        os.unlink(cleanup)
    print(
        "\nКритерий приёмки (owner fact-check): NEW — O(batch) памяти"
        " (не растёт с историей), OLD — O(история). PG host-side — тот же"
        " прогон с BENCH_DATABASE_URL до production cutover."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
