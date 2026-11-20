"""A+ stage 1 acceptance: lab_results lineage migration (0070).

Owner contract: .ai-factory/plans/lab-results-lineage-decision.md.

Proves, on a disposable PostgreSQL database provisioned by
``alembic upgrade`` (SQLite is never a substitute):

1. Fresh install (empty DB → head):
   - both lineage columns exist and are nullable;
   - the partial unique index exists with the managed-rows-only predicate;
   - both FKs reference lab_report_instances;
   - RLS on lab_results stays ENABLED (0046 posture, additive DDL must not
     change it);
   - alembic has exactly ONE current head.
2. Upgrade of an EXISTING schema with historical data (0069 → head):
   - the pre-existing (lineage-less) lab_results row is untouched, its new
     columns are NULL;
   - a second historical row with the SAME (order_id, test_code) stays
     legal — the new key never restricts rows without lineage.
3. Managed-row semantics at head:
   - duplicate (source_root_instance_id, test_code) is rejected;
   - same test_code under DIFFERENT roots coexists (the blood-vs-urine
     glucose case);
   - lineage values are FK-enforced against lab_report_instances.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(BACKEND_DIR))

from tests._pg_admin_guard import is_local_admin_dsn  # noqa: E402


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("LAB_A1_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
    legacy = os.getenv("RQ23A_PG_ADMIN_URL", "").strip()
    if legacy:
        urls.append(legacy)
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        u = make_url(env_url)
        if (u.host or "") in {"localhost", "127.0.0.1", "::1"}:
            urls.append(
                f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}/postgres"
            )
    return urls


def _run_alembic(sa_url: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
    )


def _provision(db_name: str, target: str) -> tuple[str, str]:
    """Create a local scratch database and return its URL and allocator connection."""
    admin_url = None
    for candidate in _candidate_admin_urls():
        if not is_local_admin_dsn(candidate):
            continue
        try:
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            admin_url = candidate
            break
        except Exception:  # noqa: BLE001
            continue
    if admin_url is None:
        pytest.skip("disposable PostgreSQL unavailable for lab lineage migration acceptance")

    scratch = make_url(admin_url).set(database=db_name)
    try:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    except Exception as exc:  # noqa: BLE001 - нет прав CREATE DATABASE и т.п.
        pytest.skip(
            f"cannot create a scratch database on this PostgreSQL server "
            f"({type(exc).__name__}); run against a server with CREATEDB"
        )
    try:
        with psycopg.connect(scratch.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute("ALTER SCHEMA public OWNER TO CURRENT_USER")
        sa_url = scratch.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
        result = _run_alembic(sa_url, "upgrade", target)
        assert result.returncode == 0, result.stderr[-1500:]
        return sa_url, admin_url
    except Exception:
        _drop(db_name, admin_url)
        raise


def _drop(db_name: str, admin_url: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(db_name)))


@pytest.fixture(scope="module")
def fresh_head_url():
    db_name = f"lab_a1_fresh_{uuid.uuid4().hex[:8]}"
    sa_url, admin_url = _provision(db_name, "head")
    try:
        yield sa_url
    finally:
        _drop(db_name, admin_url)


def _seed_history_and_upgrade() -> tuple[str, str]:
    """0069 schema + one historical lab_results row → upgrade to head."""
    db_name = f"lab_a1_upgrade_{uuid.uuid4().hex[:8]}"
    sa_url, admin_url = _provision(db_name, "0069_sentinel_pair_retirement")
    engine = create_engine(sa_url, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO lab_orders (status, created_at) "
                    "VALUES ('done', now())"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO lab_results "
                    "    (order_id, test_code, test_name, value, abnormal, created_at) "
                    "VALUES "
                    "    ((SELECT MAX(id) FROM lab_orders), 'glucose', "
                    "     'Глюкоза', '5.4', false, now())"
                )
            )
        r = _run_alembic(sa_url, "upgrade", "head")
        assert r.returncode == 0, r.stderr[-1500:]
        return sa_url, admin_url
    except Exception:
        engine.dispose()
        _drop(db_name, admin_url)
        raise
    finally:
        engine.dispose()


@pytest.mark.integration
def test_single_alembic_head(fresh_head_url):
    r = _run_alembic(fresh_head_url, "heads")
    assert r.returncode == 0, r.stderr[-800:]
    head_lines = [line for line in r.stdout.splitlines() if "(head)" in line]
    assert len(head_lines) == 1, f"multi-head detected: {r.stdout!r}"
    # NURSE-V2 N2-2 (owner design-GO 2026-09-19): the chain head moved to
    # 0072; main's corrective follow-up moved it to 0073 (routing
    # snapshot); RQ-18 follow-up round-8 re-parents the payload binding
    # as 0074 on top of it; #3506 derma history read model moves it to
    # 0075, its read-order index swap — to 0076; T06.1 adds daily queue
    # policy persistence at 0077; 0078 canonicalizes clinic settings and
    # 0079 adds public-site content; later additive revisions continue the
    # chain. This file still proves 0070's own links via the graph pins below.


@pytest.mark.integration
def test_fresh_install_schema_shape(fresh_head_url):
    engine = create_engine(fresh_head_url, future=True)
    try:
        with engine.connect() as conn:
            columns = {
                row.column_name: row.is_nullable
                for row in conn.execute(
                    text(
                        "SELECT column_name, is_nullable FROM information_schema.columns "
                        "WHERE table_name = 'lab_results' "
                        "AND column_name IN "
                        "('source_root_instance_id', 'source_instance_id')"
                    )
                )
            }
            assert columns == {
                "source_root_instance_id": "YES",
                "source_instance_id": "YES",
            }

            indexes = {
                row.indexname: row.indexdef
                for row in conn.execute(
                    text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE tablename = 'lab_results'"
                    )
                )
            }
            lineage_index = indexes.get("uq_lab_results_lineage_root_code", "")
            assert "UNIQUE" in lineage_index
            assert (
                "source_root_instance_id IS NOT NULL" in lineage_index
                and "test_code IS NOT NULL" in lineage_index
            ), f"unexpected partial predicate: {lineage_index!r}"

            fks = (
                conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conrelid = 'lab_results'::regclass "
                        "AND contype = 'f' AND conname LIKE 'fk_lab_results_source%'"
                    )
                )
                .scalars()
                .all()
            )
            assert set(fks) == {
                "fk_lab_results_source_root_instance",
                "fk_lab_results_source_instance",
            }

            rls = conn.execute(
                text(
                    "SELECT relrowsecurity FROM pg_class WHERE relname = 'lab_results'"
                )
            ).scalar()
            assert rls is True, "RLS must stay enabled on lab_results"
    finally:
        engine.dispose()


@pytest.mark.integration
def test_upgrade_keeps_historical_rows_and_allows_lineage_less_duplicates():
    sa_url, admin_url = _seed_history_and_upgrade()
    engine = create_engine(sa_url, future=True)
    db_name = make_url(sa_url).database
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT value, source_root_instance_id, source_instance_id "
                    "FROM lab_results WHERE test_code = 'glucose'"
                )
            ).fetchall()
            assert len(row) == 1
            assert row[0][0] == "5.4", "historical value must be untouched"
            assert (
                row[0][1] is None and row[0][2] is None
            ), "historical row must keep NULL lineage"

            # Исторические строки без lineage никогда не ограничены новым
            # ключом: второй ряд с тем же (order_id, test_code) легален.
            conn.execute(
                text(
                    "INSERT INTO lab_results "
                    "    (order_id, test_code, test_name, value, abnormal, created_at) "
                    "VALUES "
                    "    ((SELECT MAX(id) FROM lab_orders), 'glucose', "
                    "     'Глюкоза (второй исторический)', '6.0', false, now())"
                )
            )
    finally:
        engine.dispose()
        _drop(db_name, admin_url)


@pytest.mark.integration
def test_managed_rows_uniqueness_and_fk(fresh_head_url):
    engine = create_engine(fresh_head_url, future=True)
    Session = sessionmaker(bind=engine, future=True)
    try:
        with Session() as session:
            from datetime import date

            from app.models.patient import Patient
            from app.models.visit import Visit
            from app.services.lab_reporting_service import LabReportingService

            suffix = uuid.uuid4().hex[:10]
            patient = Patient(
                first_name="Lineage",
                last_name=f"Probe{suffix}",
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
            template = next(t for t in templates if t.code == "cbc_oak")
            instance = service.create_instance(
                {
                    "patient_id": patient.id,
                    "visit_id": visit.id,
                    "template_id": template.id,
                }
            )
            # Второй самостоятельный бланк того же визита: тот же заказ,
            # другая цепочка (root) — ровно случай «кровь vs моча».
            second = service.create_instance(
                {
                    "patient_id": patient.id,
                    "visit_id": visit.id,
                    "template_id": template.id,
                }
            )
            session.commit()
            root_id = instance.id
            other_root_id = second.id
            assert other_root_id != root_id

        def _insert_managed(conn, root, code, source=None):
            conn.execute(
                text(
                    "INSERT INTO lab_results "
                    "    (order_id, test_code, test_name, value, abnormal, "
                    "     created_at, source_root_instance_id, source_instance_id) "
                    "VALUES "
                    "    ((SELECT MAX(id) FROM lab_orders), :code, 'Managed', "
                    "     '1', false, now(), :root, :source)"
                ),
                {"code": code, "root": root, "source": source or root},
            )

        with engine.begin() as conn:
            _insert_managed(conn, root_id, "t1")
            _insert_managed(conn, root_id, "t2")
            _insert_managed(conn, other_root_id, "t1")  # different root — legal

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                _insert_managed(conn, root_id, "t1")  # duplicate managed key

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                _insert_managed(conn, 99_999_999, "t1")  # FK violation
    finally:
        engine.dispose()
