"""Lineage-specific post-deploy smoke (stage 4, after operator deployment).

Implements the reviewer's 7-point checklist that the generic
STAGING_VALIDATION runbook does NOT cover:

  1. deployed SHA — printed as a reminder: verify with
     `git -C <deploy-tree> rev-parse HEAD` (expected: the merged A+ head,
     eaaa08f896... or later; the DB-side script cannot see it);
  2. alembic_version == 0070_lab_results_lineage (or later);
  3. both lineage columns + FKs + the partial unique index exist;
  4. synthetic blank A -> fill -> finalize -> exactly ONE managed row with
     root=A, source=A;
  5. sibling blank B of the same order -> separate managed row with a
     DIFFERENT root (blood-vs-urine glucose collision);
  6. revision A2 -> chain-A row is refreshed in place (source=A2) and the
     sibling B row is untouched;
  7. re-sync of A2 does not create duplicates (idempotent projection).

Checks 1-3 are read-only. Checks 4-7 WRITE SYNTHETIC data (SYNTHETIC-
tagged patient per the repo synthetic-data policy) and therefore require
an explicit --apply; the target database is chosen exclusively via
LAB_LINEAGE_SMOKE_DSN (never implicit fallbacks) so the script cannot
accidentally point at the wrong environment.

Usage (from backend/ with the backend venv):
    LAB_LINEAGE_SMOKE_DSN=postgresql://... python \
        ../scripts/ops/lab_lineage_post_deploy_smoke.py            # checks 1-3
    LAB_LINEAGE_SMOKE_DSN=postgresql://... python \
        ../scripts/ops/lab_lineage_post_deploy_smoke.py --apply    # checks 1-7
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
from sqlalchemy import create_engine, text

# The synthetic-data path drives the real service; make `app` importable
# regardless of the caller's cwd (script lives in <repo>/scripts/ops).
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SMOKE_DSN = os.getenv("LAB_LINEAGE_SMOKE_DSN", "").strip()
EXPECTED_HEAD_PREFIX = "0070_lab_results_lineage"


def _require_dsn() -> str:
    if not SMOKE_DSN:
        raise SystemExit(
            "refusing to guess the environment: set LAB_LINEAGE_SMOKE_DSN "
            "to the database the operator deployed to"
        )
    dsn = SMOKE_DSN
    for prefix in ("postgresql+psycopg://", "postgresql+asyncpg://"):
        if dsn.startswith(prefix):
            dsn = dsn.replace(prefix, "postgresql://", 1)
    return dsn


def check_schema_shape(engine) -> None:
    print("== [2] migration state ==")
    with engine.connect() as conn:
        version = conn.execute(
            text("select version_num from alembic_version")
        ).scalar()
    print("alembic_version:", version)
    assert str(version).startswith(EXPECTED_HEAD_PREFIX), (
        f"expected lineage migration ({EXPECTED_HEAD_PREFIX}...), got {version!r}; "
        f"deployment incomplete — DO NOT run the synthetic data path"
    )

    print("== [3] lineage schema shape ==")
    with engine.connect() as conn:
        columns = conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_name = 'lab_results' "
            "and column_name in ('source_root_instance_id','source_instance_id') "
            "order by column_name"
        )).scalars().all()
        assert sorted(columns) == ["source_instance_id", "source_root_instance_id"]
        fks = conn.execute(text(
            "select conname from pg_constraint "
            "where conrelid = 'lab_results'::regclass and contype = 'f' "
            "and conname like 'fk_lab_results_source%'"
        )).scalars().all()
        assert len(fks) == 2, fks
        index_defs = conn.execute(text(
            "select indexdef from pg_indexes "
            "where indexname = 'uq_lab_results_lineage_root_code'"
        )).scalars().all()
        assert index_defs and "UNIQUE" in index_defs[0]
    print("columns, FKs, partial unique index: OK")


def run_synthetic_flow(engine) -> None:
    os.environ.setdefault("TESTING", "1")
    os.environ["DATABASE_URL"] = SMOKE_DSN
    from datetime import datetime, UTC

    from app.db import base  # noqa: F401 - registers all models
    from app.models.lab import LabResult
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.lab_reporting_service import LabReportingService

    Session = sessionmaker_factory(engine)
    with Session() as session:
        suffix = uuid4().hex[:10]
        patient = Patient(
            first_name="SYNTHETIC",
            last_name=f"LineageSmoke{suffix}",
            phone=f"+99890{suffix[:7]}",
            birth_date=date(1990, 1, 1),
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        visit = Visit(
            patient_id=patient.id,
            visit_date=date.today(),
            status="open",
            source="desk",
        )
        session.add(visit)
        session.commit()
        session.refresh(visit)

        service = LabReportingService(session)
        templates = service.list_templates()
        biochem = next(t for t in templates if t.code == "biochem_panel")
        urinalysis = next(t for t in templates if t.code == "urinalysis_oam")

        # [4] blank A: blood glucose
        a = service.create_instance(
            {"patient_id": patient.id, "visit_id": visit.id, "template_id": biochem.id}
        )
        service.bulk_upsert_values(
            a.id, [{"field_key": "glucose", "value_text": "5.4"}]
        )
        service.finalize(a.id)
        blood_rows = (
            session.query(LabResult)
            .filter(
                LabResult.source_root_instance_id == a.id,
                LabResult.test_code == "glucose",
            )
            .all()
        )
        assert len(blood_rows) == 1, blood_rows
        assert blood_rows[0].value == "5.4"
        assert blood_rows[0].source_instance_id == a.id
        print(f"== [4] chain A (root={a.id}): one managed row, source=A — OK")

        # [5] sibling blank B: urine glucose, same order, DIFFERENT root
        b = service.create_instance(
            {
                "patient_id": patient.id,
                "visit_id": visit.id,
                "template_id": urinalysis.id,
            }
        )
        assert b.order_id == a.order_id
        service.bulk_upsert_values(
            b.id, [{"field_key": "glucose", "value_text": "не обнаружено"}]
        )
        service.finalize(b.id)
        urine_rows = (
            session.query(LabResult)
            .filter(
                LabResult.source_root_instance_id == b.id,
                LabResult.test_code == "glucose",
            )
            .all()
        )
        assert len(urine_rows) == 1
        assert urine_rows[0].value == "не обнаружено"
        assert urine_rows[0].source_root_instance_id != blood_rows[0].source_root_instance_id
        print(
            f"== [5] sibling chain B (root={b.id}): independent managed row, "
            f"other root — OK (blood result untouched)"
        )

        # [6] revision A2 refreshes chain A in place; sibling B untouched
        a2 = service.revise(a.id)
        service.bulk_upsert_values(
            a2.id, [{"field_key": "glucose", "value_text": "6.0"}]
        )
        service.finalize(a2.id)
        session.refresh(blood_rows[0])
        # glucose is numeric: the projector strips trailing zeros
        # (Decimal('6.0000') -> '6').
        assert blood_rows[0].value == "6", blood_rows[0].value
        assert blood_rows[0].source_instance_id == a2.id
        session.refresh(urine_rows[0])
        assert urine_rows[0].value == "не обнаружено"
        assert urine_rows[0].source_instance_id == b.id
        print("== [6] revision A2: chain A row refreshed in place; B intact — OK")

        # [7] idempotent re-sync: no duplicates
        before = session.query(LabResult).filter(
            LabResult.source_root_instance_id == a.id
        ).count()
        service._sync_legacy_lab_results(a2, service._field_map(a2.template_version))
        session.commit()
        after = session.query(LabResult).filter(
            LabResult.source_root_instance_id == a.id
        ).count()
        assert after == before, (before, after)
        print("== [7] re-sync idempotent: no duplicates — OK")

        print(
            "\nSYNTHETIC data left in place (per repo synthetic-data policy): "
            f"patient_id={patient.id} visit_id={visit.id} order_id={a.order_id} "
            f"instance_ids={[a.id, b.id, a2.id]}"
        )


def sessionmaker_factory(engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, future=True)


def main() -> int:
    dsn = _require_dsn()
    apply_mode = "--apply" in sys.argv

    print("== [1] deployed SHA (operator reminder) ==")
    print(
        "verify on the deploy tree: git rev-parse HEAD — expected the merged "
        "A+ head (eaaa08f896... or later); the DB cannot show it"
    )

    sa_url = dsn
    if not sa_url.startswith("postgresql+"):
        sa_url = sa_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(sa_url, future=True)
    try:
        check_schema_shape(engine)
        if not apply_mode:
            print(
                "\nDRY RUN (checks 1-3 only). For the synthetic data path "
                "(checks 4-7) add --apply against the DEPLOYED environment."
            )
            return 0
        run_synthetic_flow(engine)
    finally:
        engine.dispose()
    print("\nLINEAGE POST-DEPLOY SMOKE: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
