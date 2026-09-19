"""Lineage-specific post-deploy smoke (stage 4, after operator deployment).

Implements the reviewer's 7-point checklist that the generic
STAGING_VALIDATION runbook does NOT cover:

  1. deployed SHA — printed as a reminder: verify with
     `git -C <deploy-tree> rev-parse HEAD` (expected: the merged A+ head,
     eaaa08f896... or later; the DB-side script cannot see it);
  2. the deployed alembic chain includes 0070_lab_results_lineage —
     the DB's version_num must resolve (via the DEPLOYED tree's
     revision graph) to a head that has 0070 as an ancestor, so a
     future 0071_* head passes while a pre-lineage head fails;
  3. both lineage columns + FKs (RESTRICT, targeting lab_report_instances)
     + the exact partial unique index (columns AND predicate) exist;
  4. synthetic blank A -> fill -> finalize -> exactly ONE managed row with
     root=A, source=A;
  5. sibling blank B of the same order -> separate managed row with a
     DIFFERENT root (blood-vs-urine glucose collision);
  6. revision A2 -> chain-A row is refreshed in place (source=A2) and the
     sibling B row is untouched;
  7. re-sync of A2 does not create duplicates (idempotent projection).

SAFETY CONTRACT (review P1 fix on #3334):
- checks 1-3 are READ ONLY and may run against any environment;
- checks 4-7 are a WRITE path and run ONLY on explicitly chosen
  non-production databases: the DSN comes exclusively from
  LAB_LINEAGE_SMOKE_DSN and the database name MUST pass the canonical
  synthetic-seed production guard (app.synthetic_seed._check_db_safety —
  protected-name denylist plus a staging/dev/test/synthetic/sandbox
  marker). Production write-smoke is NOT a supported mode of this
  script; if an owner ever requires it, that is a separate approved
  protocol with canonical fixtures and cleanup, not direct ORM creation
  here;
- the synthetic fixture is canonical-marker compatible: the patient's
  last_name carries the SYNTHETIC- prefix so cleanup_synthetic() can
  find and remove it;
- user-facing notification side effects are suppressed for the smoke
  flow (service emit methods stubbed) and the flow VERIFIES the
  suppression (zero new rows in notification_events /
  notification_deliveries);
- ALL checks are fail-closed `if not ...: raise RuntimeError(...)` —
  they survive `python -O` (no assert statements).
- OPERATOR SPLIT (review guidance): staging proves the write path
  (STAGING_VALIDATION -> upgrade 0070 -> this script --apply -> checks
  1-7 PASS, notification delta 0); production proves the read path only
  (deploy -> this script WITHOUT --apply -> checks 1-3 PASS + the
  committed census). Production synthetic write smoke is intentionally
  unsupported.

Usage (from anywhere with the backend venv):
    LAB_LINEAGE_SMOKE_DSN=postgresql://... python \
        scripts/ops/lab_lineage_post_deploy_smoke.py            # checks 1-3
    LAB_LINEAGE_SMOKE_DSN=postgresql://... python \
        scripts/ops/lab_lineage_post_deploy_smoke.py --apply    # checks 1-7
"""
from __future__ import annotations

import os
import re
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
EXPECTED_LINEAGE_REVISION = "0070_lab_results_lineage"
LINEAGE_IN_CHAIN_MESSAGE = (
    "the deployed alembic chain does not include "
    + EXPECTED_LINEAGE_REVISION
)


def fail(message: str) -> None:
    """Fail-closed check helper: survives `python -O` (no asserts)."""
    raise RuntimeError("LINEAGE SMOKE FAILED: " + message)


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


def _print_deployed_sha_reminder() -> None:
    print("== [1] deployed SHA (operator reminder) ==")
    print(
        "verify on the deploy tree: git rev-parse HEAD — expected the merged "
        "A+ head (eaaa08f896... or later); the DB cannot show it"
    )


def _lineage_in_deployed_chain(version_num: str) -> bool:
    """True when 0070 is the deployed version or one of its ancestors.

    Parses the DEPLOYED tree's alembic revision graph (this script ships
    from the same tree the operator deployed) and walks the ancestor
    closure of the database's version_num. A future head descending from
    0070 passes; a pre-lineage head fails.
    """
    versions_dir = BACKEND_DIR / "alembic" / "versions"
    if not versions_dir.is_dir():
        fail(f"deployed alembic versions directory not found: {versions_dir}")
    graph: dict[str, tuple[str, ...]] = {}
    for path in versions_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        revision_match = re.search(
            r"^revision\s*=\s*['\"]([^'\"]+)['\"]", source, re.M
        )
        if not revision_match:
            continue
        down_match = re.search(r"^down_revision\s*=\s*(.+)$", source, re.M)
        parents = (
            tuple(re.findall(r"['\"]([^'\"]+)['\"]", down_match.group(1)))
            if down_match
            else ()
        )
        graph[revision_match.group(1)] = parents
    if version_num not in graph:
        fail(
            f"the deployed alembic code does not know version {version_num!r} — "
            f"this script and the deployed backend appear to be from "
            f"different trees"
        )
    # The history is a DAG (branch/merge points exist): a shared ancestor
    # reached via two paths is legal and must NOT be flagged as a cycle.
    # Cycle = a node re-entered while still on the current walk path.
    visited: set[str] = set()
    on_path: set[str] = set()

    def _walk(node: str) -> None:
        if node in visited:
            return
        if node in on_path:
            fail(f"corrupt revision chain: cycle at {node!r}")
        visited.add(node)
        on_path.add(node)
        for parent in graph.get(node, ()):
            _walk(parent)
        on_path.discard(node)

    _walk(version_num)
    return EXPECTED_LINEAGE_REVISION in visited


def check_migration_state(engine) -> None:
    print("== [2] migration state ==")
    with engine.connect() as conn:
        version = conn.execute(
            text("select version_num from alembic_version")
        ).scalar()
    if not _lineage_in_deployed_chain(str(version)):
        fail(
            f"{LINEAGE_IN_CHAIN_MESSAGE}: version_num={version!r}; "
            f"deployment incomplete — DO NOT run the synthetic data path"
        )
    print("alembic_version:", version, "(0070 in chain)")


def check_schema_shape(engine) -> None:
    print("== [3] lineage schema shape (strict pg_catalog verification) ==")
    with engine.connect() as conn:
        schema = conn.execute(text("select current_schema()")).scalar()

        columns = conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema = :schema and table_name = 'lab_results' "
            "and column_name in ('source_root_instance_id','source_instance_id') "
            "order by column_name"
        ), {"schema": schema}).scalars().all()
        if sorted(columns) != ["source_instance_id", "source_root_instance_id"]:
            fail(f"lineage columns missing or misplaced: {columns!r}")

        # FKs: exact names, target table lab_report_instances, ON DELETE
        # RESTRICT ('r'), and the constrained lineage column identity.
        fks = conn.execute(text(
            "select con.conname, confrelid::regclass::text as target, "
            "       pg_get_constraintdef(con.oid) as constraint_def, con.confdeltype "
            "from pg_constraint con "
            "where con.conrelid = 'lab_results'::regclass "
            "  and con.contype = 'f' "
            "  and con.conname in ("
            "      'fk_lab_results_source_root_instance',"
            "      'fk_lab_results_source_instance')"
        )).fetchall()
        by_name = {row.conname: row for row in fks}
        if set(by_name) != {
            "fk_lab_results_source_root_instance",
            "fk_lab_results_source_instance",
        }:
            fail(f"lineage FKs missing or renamed: {sorted(by_name)}")
        for name, row in by_name.items():
            if row.target != "lab_report_instances":
                fail(f"FK {name} targets {row.target!r}, expected lab_report_instances")
            if row.confdeltype != "r":
                fail(
                    f"FK {name} is not ON DELETE RESTRICT "
                    f"(confdeltype={row.confdeltype!r}); deleting a source "
                    f"blank must never cascade"
                )
            if "source_root_instance_id" not in row.constraint_def and "source_instance_id" not in row.constraint_def:
                fail(f"FK {name} does not constrain a lineage column: {row.constraint_def!r}")

        # Partial unique index: exactly one, in the current schema, UNIQUE,
        # exact column list AND exact partial predicate.
        index_rows = conn.execute(text(
            "select schemaname, indexdef from pg_indexes "
            "where indexname = 'uq_lab_results_lineage_root_code'"
        )).fetchall()
        if len(index_rows) != 1:
            fail(f"expected exactly one lineage unique index, got {index_rows!r}")
        if index_rows[0].schemaname != schema:
            fail(
                f"lineage index lives in schema {index_rows[0].schemaname!r}, "
                f"expected {schema!r}"
            )
        indexdef = index_rows[0].indexdef
        for fragment in (
            "CREATE UNIQUE INDEX",
            "(source_root_instance_id, test_code)",
            "(source_root_instance_id IS NOT NULL) AND (test_code IS NOT NULL)",
        ):
            if fragment not in indexdef:
                fail(
                    f"lineage index does not match the managed-key contract "
                    f"({fragment!r} missing): {indexdef!r}"
                )
    print(
        "columns, FKs (RESTRICT -> lab_report_instances), exact partial unique index: OK"
    )


def _notification_snapshot(session) -> dict:
    snapshot = {}
    for table in ("notification_events", "notification_deliveries"):
        exists = session.execute(text(
            "select exists (select 1 from information_schema.tables "
            "where table_name = :t)"
        ), {"t": table}).scalar()
        if exists:
            snapshot[table] = session.execute(
                text(f"select count(*) from {table}")
            ).scalar()
    return snapshot


def _assert_no_notification_rows_created(session, snapshot: dict) -> None:
    for table, before in snapshot.items():
        after = session.execute(text(f"select count(*) from {table}")).scalar()
        if after != before:
            fail(
                f"user-facing notification side effect detected: {table} "
                f"rows {before} -> {after} (suppression broken)"
            )


def _suppress_user_facing_notifications() -> None:
    """Stub the service emit methods so the smoke flow cannot create
    user-facing notification rows; the flow then VERIFIES the suppression
    by counting notification_events/notification_deliveries deltas."""
    from app.services.lab_reporting_service import LabReportingService

    LabReportingService._emit_lab_new_study_notification = (
        lambda self, **kwargs: None
    )
    LabReportingService._emit_lab_results_ready_notification = (
        lambda self, instance: None
    )
    # NOTE: the critical-values path uses asyncio.create_task without a
    # running loop in this script context -> RuntimeError -> caught as a
    # non-blocking warning inside finalize(); it cannot deliver anything
    # here.


def run_synthetic_flow(engine) -> None:
    os.environ.setdefault("TESTING", "1")
    os.environ["DATABASE_URL"] = SMOKE_DSN
    from app.db import base  # noqa: F401 - registers all models

    from app.models.lab import LabResult
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.lab_reporting_service import LabReportingService
    from app.synthetic_seed import SYNTHETIC_PREFIX

    _suppress_user_facing_notifications()

    Session = sessionmaker_factory(engine)
    with Session() as session:
        notification_snapshot = _notification_snapshot(session)

        suffix = uuid4().hex[:10]
        # Canonical SYNTHETIC- marker: cleanup_synthetic() targets
        # last_name LIKE 'SYNTHETIC-%' and must be able to find this row.
        patient = Patient(
            first_name="SYNTHETIC",
            last_name=f"{SYNTHETIC_PREFIX}LineageSmoke{suffix}",
            phone=f"+99890{suffix[:7]}",
            birth_date=date(1990, 1, 1),
        )
        if not patient.last_name.startswith("SYNTHETIC-"):
            fail("synthetic fixture lost the canonical SYNTHETIC- marker")
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
        if len(blood_rows) != 1:
            fail(f"chain A must have exactly one glucose row, got {blood_rows!r}")
        if blood_rows[0].value != "5.4" or blood_rows[0].source_instance_id != a.id:
            fail(f"chain A projection wrong: value={blood_rows[0].value!r}")
        print(f"== [4] chain A (root={a.id}): one managed row, source=A — OK")

        # [5] sibling blank B: urine glucose, same order, DIFFERENT root
        b = service.create_instance(
            {
                "patient_id": patient.id,
                "visit_id": visit.id,
                "template_id": urinalysis.id,
            }
        )
        if b.order_id != a.order_id:
            fail("sibling blank must reuse the visit order")
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
        if len(urine_rows) != 1:
            fail(f"chain B must have exactly one glucose row, got {urine_rows!r}")
        if urine_rows[0].value != "не обнаружено":
            fail(f"chain B value wrong: {urine_rows[0].value!r}")
        if urine_rows[0].source_root_instance_id == blood_rows[0].source_root_instance_id:
            fail("sibling blank must own a DIFFERENT lineage root")
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
        if blood_rows[0].value != "6":
            fail(
                f"revision must refresh the chain row in place, got "
                f"{blood_rows[0].value!r}"
            )
        if blood_rows[0].source_instance_id != a2.id:
            fail("revision source not advanced to A2")
        session.refresh(urine_rows[0])
        if urine_rows[0].value != "не обнаружено" or urine_rows[0].source_instance_id != b.id:
            fail("sibling B must be untouched by the A2 revision")
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
        if after != before:
            fail(f"re-sync created duplicates: {before} -> {after}")
        print("== [7] re-sync idempotent: no duplicates — OK")

        # Notification suppression proof (P1 fix): zero user-facing rows.
        _assert_no_notification_rows_created(session, notification_snapshot)
        print("== [P1 fix] notification suppression verified: 0 new rows — OK")

        print(
            "\nSYNTHETIC data left in place (canonical SYNTHETIC- marker, "
            "cleanable via app.synthetic_seed cleanup): "
            f"patient_id={patient.id} visit_id={visit.id} order_id={a.order_id} "
            f"instance_ids={[a.id, b.id, a2.id]}"
        )


def sessionmaker_factory(engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, future=True)


def main() -> int:
    dsn = _require_dsn()
    apply_mode = "--apply" in sys.argv

    _print_deployed_sha_reminder()

    sa_url = dsn
    if not sa_url.startswith("postgresql+"):
        sa_url = sa_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(sa_url, future=True)
    try:
        check_migration_state(engine)
        check_schema_shape(engine)
        if not apply_mode:
            print(
                "\nDRY RUN (checks 1-3 only). For the synthetic data path "
                "(checks 4-7) add --apply; the target database must be a "
                "non-production one (canonical synthetic-seed guard) and is "
                "chosen exclusively via LAB_LINEAGE_SMOKE_DSN."
            )
            return 0

        # P1 fix: the write path refuses production-looking databases via
        # the canonical guard BEFORE any ORM session is created.
        from app.synthetic_seed import SyntheticSeedSafetyError, _check_db_safety

        try:
            _check_db_safety(sa_url)
        except SyntheticSeedSafetyError as exc:
            raise SystemExit(
                "\nWRITE SMOKE REFUSED: the target database failed the "
                f"canonical synthetic-seed production guard.\n{exc}\n"
                "Checks 1-3 (read-only) remain valid. The write path is "
                "for staging/scratch databases only — production write-smoke "
                "is not a supported mode of this script."
            ) from exc
        run_synthetic_flow(engine)
    finally:
        engine.dispose()
    print("\nLINEAGE POST-DEPLOY SMOKE: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
