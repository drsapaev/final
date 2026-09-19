"""NURSE-V2 N2-2 foundation acceptance: migrations 0071 + 0072 on real PostgreSQL.

Owner contract: .ai-factory/plans/nurse-v2-clinical-serving.md (design-GO
2026-09-19, D1/D2 FINAL). Proves, on a disposable PostgreSQL provisioned
by ``alembic upgrade`` (SQLite is never a substitute):

1. Fresh install (empty DB -> head):
   - both tables exist with the agreed column shape;
   - the D2 partial unique index (active pair) and the D1 partial unique
     index (one in_progress execution per VisitService) exist with the
     exact predicates; the plain attempt-unique constraint exists;
   - FKs reference users / queue_resources / visit_services /
     queue_entries;
   - RLS is ENABLED on both new public tables (0051 convention);
   - alembic has exactly ONE head.
2. D2 invariant on data: a second ACTIVE assignment of the same
   (user_id, queue_resource_id) pair is rejected; after deactivation a
   new active row for the same pair is legal (history preserved);
   several nurses per resource and several resources per nurse coexist.
3. D1 invariants on data: a second in_progress execution for the same
   VisitService is rejected; a completed attempt + a new in_progress
   attempt coexist (retry semantics); duplicate (visit_service_id,
   attempt_no) is rejected; the performer FK enforces real users.
4. Downgrade reverses cleanly (head -> 0070 -> head).
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("N2V2_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
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


def _admin_url() -> str | None:
    last_error: Exception | None = None
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            return candidate
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    pytest.skip(
        f"disposable PostgreSQL unavailable — NURSE-V2 N2-2 migration "
        f"acceptance NOT_RUN (last error: {last_error})"
    )
    return None


def _provision(db_name: str, target: str) -> str:
    admin_url = _admin_url()
    u = make_url(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        c.execute(f'CREATE DATABASE "{db_name}"')
    sa_url = (
        f"postgresql+psycopg://{u.username}:{u.password}"
        f"@{u.host}:{u.port}/{db_name}"
    )
    r = _run_alembic(sa_url, "upgrade", target)
    assert r.returncode == 0, r.stderr[-1500:]
    return sa_url


def _drop(db_name: str) -> None:
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
            return
        except Exception:  # noqa: BLE001
            continue


@pytest.fixture(scope="module")
def head_url():
    db_name = f"n2v2_fresh_{uuid.uuid4().hex[:8]}"
    sa_url = _provision(db_name, "head")
    yield sa_url
    _drop(db_name)


def _insert_user(conn, username: str, role: str = "Nurse") -> int:
    return conn.execute(
        text(
            "INSERT INTO users (username, email, hashed_password, role, "
            "is_active, is_superuser, must_change_password) "
            f"VALUES ('{username}', '{username}@example.com', 'x', '{role}', "
            "true, false, false) RETURNING id"
        )
    ).scalar_one()


def _insert_resource(conn, code: str, active: bool = True) -> int:
    return conn.execute(
        text(
            "INSERT INTO queue_resources "
            "(code, queue_tag, display_name, active, start_number_online, "
            "max_online_per_day, default_cabinet) "
            f"VALUES ('{code}', 'tag_{code}', 'Resource {code}', "
            f"{'true' if active else 'false'}, 1, 15, 'c1') RETURNING id"
        )
    ).scalar_one()


def _insert_visit_service(conn, name: str = "Процедура") -> int:
    # baseline NOT NULLs without server defaults are provided explicitly
    # (patients.created_at/is_deleted, visits.created_at,
    # visit_services.created_at)
    patient_id = conn.execute(
        text(
            "INSERT INTO patients (last_name, first_name, birth_date, "
            "created_at, is_deleted) "
            "VALUES ('Н2', 'Пациент', '1990-01-01', now(), false) RETURNING id"
        )
    ).scalar_one()
    visit_id = conn.execute(
        text(
            "INSERT INTO visits (patient_id, status, discount_mode, "
            "approval_status, source, reminder_generation, created_at) "
            f"VALUES ({patient_id}, 'open', 'none', 'none', 'desk', 0, now()) "
            "RETURNING id"
        )
    ).scalar_one()
    return conn.execute(
        text(
            "INSERT INTO visit_services (visit_id, service_id, name, qty, "
            "created_at) "
            f"VALUES ({visit_id}, 101, '{name}', 1, now()) RETURNING id"
        )
    ).scalar_one()


def _insert_execution(
    conn,
    visit_service_id: int,
    started_by: int,
    *,
    attempt_no: int = 1,
    status: str = "in_progress",
) -> None:
    conn.execute(
        text(
            "INSERT INTO service_executions "
            "(visit_service_id, queue_entry_id, attempt_no, status, "
            "started_by_user_id, started_at) "
            f"VALUES ({visit_service_id}, NULL, {attempt_no}, '{status}', "
            f"{started_by}, now())"
        )
    )


@pytest.mark.integration
def test_single_alembic_head(head_url):
    r = _run_alembic(head_url, "heads")
    assert r.returncode == 0, r.stderr[-800:]
    head_lines = [line for line in r.stdout.splitlines() if "(head)" in line]
    assert len(head_lines) == 1, f"multi-head detected: {r.stdout!r}"
    assert "0072_service_executions" in head_lines[0]


@pytest.mark.integration
def test_fresh_install_schema_shape(head_url):
    engine = create_engine(head_url, future=True)
    try:
        with engine.connect() as conn:
            # columns
            assignment_columns = {
                row.column_name
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'nurse_workplace_assignments'"
                    )
                )
            }
            assert {
                "id",
                "user_id",
                "queue_resource_id",
                "cabinet_override",
                "is_active",
                "created_at",
                "updated_at",
            } <= assignment_columns

            execution_columns = {
                row.column_name
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'service_executions'"
                    )
                )
            }
            assert {
                "id",
                "visit_service_id",
                "queue_entry_id",
                "attempt_no",
                "status",
                "started_by_user_id",
                "started_at",
                "performed_by_user_id",
                "completed_at",
                "incomplete_reason",
                "created_at",
                "updated_at",
            } <= execution_columns

            # partial unique indexes with exact predicates
            def indexdef(table: str, name: str) -> str:
                return (
                    conn.execute(
                        text(
                            "SELECT indexdef FROM pg_indexes "
                            f"WHERE tablename = '{table}' AND indexname = '{name}'"
                        )
                    ).scalar()
                    or ""
                )

            pair_index = indexdef(
                "nurse_workplace_assignments",
                "uq_nurse_workplace_assignments_active_pair",
            )
            assert "UNIQUE" in pair_index
            # PostgreSQL may render partial predicates with ::text casts
            # (e.g. ``((is_active)::text = ...``) — normalize before the
            # exact-shape assertions.
            normalized_pair = pair_index.replace("::text", "")
            normalized_pair = normalized_pair.replace("(", "").replace(")", "")
            assert "user_id, queue_resource_id" in normalized_pair
            assert (
                "is_active" in normalized_pair
            ), f"unexpected partial predicate: {pair_index!r}"

            active_execution_index = indexdef(
                "service_executions", "uq_service_executions_one_active"
            )
            assert "UNIQUE" in active_execution_index
            normalized_active = active_execution_index.replace("::text", "")
            normalized_active = normalized_active.replace("(", "").replace(")", "")
            assert (
                "status = 'in_progress'" in normalized_active
            ), f"unexpected partial predicate: {active_execution_index!r}"

            # plain attempt-unique constraint
            attempt_unique = (
                conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conrelid = 'service_executions'::regclass "
                        "AND contype = 'u'"
                    )
                )
                .scalars()
                .all()
            )
            assert "uq_service_executions_visit_service_attempt" in attempt_unique

            # FKs
            assignment_fks = set(
                conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conrelid = 'nurse_workplace_assignments'::regclass "
                        "AND contype = 'f'"
                    )
                )
                .scalars()
                .all()
            )
            assert assignment_fks == {
                "fk_nurse_workplace_assignments_user_id",
                "fk_nurse_workplace_assignments_queue_resource_id",
            }
            execution_fks = set(
                conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conrelid = 'service_executions'::regclass "
                        "AND contype = 'f'"
                    )
                )
                .scalars()
                .all()
            )
            assert execution_fks == {
                "fk_service_executions_visit_service_id",
                "fk_service_executions_queue_entry_id",
                "fk_service_executions_started_by_user_id",
                "fk_service_executions_performed_by_user_id",
            }

            # RLS enabled on both new public tables (0051 convention)
            for table in (
                "nurse_workplace_assignments",
                "service_executions",
            ):
                rls = conn.execute(
                    text(
                        "SELECT relrowsecurity FROM pg_class WHERE relname = "
                        f"'{table}'"
                    )
                ).scalar()
                assert rls is True, f"RLS must be enabled on {table}"
    finally:
        engine.dispose()


@pytest.mark.integration
def test_d2_active_pair_uniqueness_and_replacement(head_url):
    engine = create_engine(head_url, future=True)
    try:
        with engine.begin() as conn:
            nurse_a = _insert_user(conn, "n2v2_nurse_a")
            nurse_b = _insert_user(conn, "n2v2_nurse_b")
            resource = _insert_resource(conn, "n2v2_procedures")

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO nurse_workplace_assignments "
                    "(user_id, queue_resource_id, cabinet_override, is_active) "
                    f"VALUES ({nurse_a}, {resource}, '5', true)"
                )
            )
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO nurse_workplace_assignments "
                    "(user_id, queue_resource_id, cabinet_override, is_active) "
                    f"VALUES ({nurse_b}, {resource}, '6', true)"
                )
            )
        # several nurses per resource — fine (above); the same pair twice:
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO nurse_workplace_assignments "
                        "(user_id, queue_resource_id, is_active) "
                        f"VALUES ({nurse_a}, {resource}, true)"
                    )
                )
        # deactivate, then a NEW active row for the same pair is legal
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE nurse_workplace_assignments SET is_active = false "
                    f"WHERE user_id = {nurse_a} AND queue_resource_id = {resource}"
                )
            )
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO nurse_workplace_assignments "
                    "(user_id, queue_resource_id, cabinet_override, is_active) "
                    f"VALUES ({nurse_a}, {resource}, '7', true)"
                )
            )
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT is_active FROM nurse_workplace_assignments "
                        f"WHERE user_id = {nurse_a} AND queue_resource_id = {resource} "
                        "ORDER BY id"
                    )
                )
                .scalars()
                .all()
            )
            assert rows == [False, True]
    finally:
        engine.dispose()


@pytest.mark.integration
def test_d1_execution_invariants(head_url):
    engine = create_engine(head_url, future=True)
    try:
        with engine.begin() as conn:
            nurse = _insert_user(conn, "n2v2_exec_nurse")
            other_nurse = _insert_user(conn, "n2v2_exec_other")
            visit_service_id = _insert_visit_service(conn)

        # second in_progress execution for the same VisitService -> rejected
        with engine.begin() as conn:
            _insert_execution(conn, visit_service_id, nurse, attempt_no=1)
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                _insert_execution(conn, visit_service_id, other_nurse, attempt_no=2)

        # complete the first attempt, then a new in_progress retry coexists
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE service_executions SET status = 'completed', "
                    f"performed_by_user_id = {other_nurse}, "
                    "completed_at = now() "
                    f"WHERE visit_service_id = {visit_service_id} AND attempt_no = 1"
                )
            )
        with engine.begin() as conn:
            _insert_execution(conn, visit_service_id, nurse, attempt_no=2)

        # duplicate attempt ordinal -> rejected
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                _insert_execution(conn, visit_service_id, other_nurse, attempt_no=2)

        # performer FK enforces real users (NO ACTION)
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                _insert_execution(conn, visit_service_id, 999999, attempt_no=3)

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT attempt_no, status, performed_by_user_id "
                    "FROM service_executions "
                    f"WHERE visit_service_id = {visit_service_id} "
                    "ORDER BY attempt_no"
                )
            ).fetchall()
        assert [(r[0], r[1]) for r in rows] == [
            (1, "completed"),
            (2, "in_progress"),
        ]
        assert rows[0][2] == other_nurse, "history must not be overwritten"
    finally:
        engine.dispose()


@pytest.mark.integration
def test_downgrade_reverses_cleanly():
    db_name = f"n2v2_down_{uuid.uuid4().hex[:8]}"
    sa_url = _provision(db_name, "head")
    try:
        # head -> 0070: both tables gone
        r = _run_alembic(sa_url, "downgrade", "0070_lab_results_lineage")
        assert r.returncode == 0, r.stderr[-1500:]
        engine = create_engine(sa_url, future=True)
        try:
            with engine.connect() as conn:
                tables = set(
                    conn.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert "nurse_workplace_assignments" not in tables
                assert "service_executions" not in tables
        finally:
            engine.dispose()
        # and back to head — clean re-upgrade
        r = _run_alembic(sa_url, "upgrade", "head")
        assert r.returncode == 0, r.stderr[-1500:]
        engine = create_engine(sa_url, future=True)
        try:
            with engine.connect() as conn:
                tables = set(
                    conn.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert "nurse_workplace_assignments" in tables
                assert "service_executions" in tables
        finally:
            engine.dispose()
    finally:
        _drop(db_name)
