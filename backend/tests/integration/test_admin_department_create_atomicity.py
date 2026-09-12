"""
RQ-04 acceptance: admin department creation must be ONE atomic transaction
on real PostgreSQL with the Alembic schema (docs/plans/registrar-queue-remediation
ACCEPTANCE «Дополнительная обязательная проверка RQ-04»).

Defect being pinned (F-03): create_department committed the Department
BEFORE creating DepartmentQueueSettings / DepartmentRegistrationSettings and
then created those rows a SECOND time (unconditionally, after the guarded
creation inside _ensure_department_integrations) — duplicate settings rows
plus a permanently half-configured department whenever the second commit
failed (retry then blocked by «already exists»).

Disposable PostgreSQL: the module provisions its own scratch database
(rq04_atomic), runs `alembic upgrade head` against it and drops it at the
end. Skips (NOT_RUN, per plan P0) when no disposable PostgreSQL server is
reachable. SQLite is never a substitute here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq04_atomic"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only.

    The scratch database must never be created on a remote/production
    server (Supabase DATABASE_URL points there), so DATABASE_URL-derived
    candidates are accepted only for localhost/127.0.0.1 hosts.
    """
    urls: list[str] = []

    explicit = os.getenv("RQ04_PG_ADMIN_URL", "").strip()
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


def _scratch_url(admin_url: str) -> tuple[str, str]:
    """(psycopg conninfo, sqlalchemy URL) for the scratch database."""
    u = make_url(admin_url)
    base = f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}"
    return (
        f"{base}/{SCRATCH_DB}",
        f"postgresql+psycopg://{u.username}:{u.password}"
        f"@{u.host}:{u.port}/{SCRATCH_DB}",
    )


@pytest.fixture(scope="module")
def pg_engine():
    """Provision a disposable alembic-head PostgreSQL database or skip."""
    last_error: Exception | None = None
    admin_url = None
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            admin_url = candidate
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    if admin_url is None:
        pytest.skip(
            f"disposable PostgreSQL unavailable — RQ-04 PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_url(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
    import subprocess  # noqa: E402

    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
    )
    assert r.returncode == 0, r.stderr[-1500:]

    engine = create_engine(sa_url, future=True)
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
    assert version, "alembic_version must be present after upgrade"

    yield engine

    engine.dispose()
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')


@pytest.fixture
def db_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _counts(db, key: str) -> dict:
    dept_id = db.execute(
        text("select id from departments where key = :k"), {"k": key}
    ).scalar()
    out: dict = {"departments": 1 if dept_id else 0}
    if dept_id:
        for label, table in (
            ("queue_settings", "department_queue_settings"),
            ("registration_settings", "department_registration_settings"),
            ("services", "services"),
        ):
            out[label] = db.execute(
                text(
                    f"select count(*) from {table} where department_id = :d"
                ),
                {"d": dept_id},
            ).scalar()
        out["queue_profiles"] = db.execute(
            text("select count(*) from queue_profiles where key = :k"), {"k": key}
        ).scalar()
        out["clinic_settings"] = db.execute(
            text(
                "select count(*) from clinic_settings where key in "
                "(:s, :m)"
            ),
            {"s": f"start_number_{key}", "m": f"max_per_day_{key}"},
        ).scalar()
        out["service_categories"] = db.execute(
            text("select count(*) from service_categories where specialty = :k"),
            {"k": key},
        ).scalar()
    return out


def _cleanup(db, key: str) -> None:
    dept_id = db.execute(
        text("select id from departments where key = :k"), {"k": key}
    ).scalar()
    if dept_id:
        db.execute(
            text("delete from department_services where department_id = :d"),
            {"d": dept_id},
        )
        db.execute(
            text("delete from services where department_id = :d"), {"d": dept_id}
        )
        db.execute(
            text(
                "delete from department_queue_settings where department_id = :d"
            ),
            {"d": dept_id},
        )
        db.execute(
            text(
                "delete from department_registration_settings where department_id = :d"
            ),
            {"d": dept_id},
        )
    db.execute(
        text("delete from queue_profiles where key = :k"), {"k": key}
    )
    db.execute(
        text(
            "delete from clinic_settings where key = :s or key = :m"
        ),
        {"s": f"start_number_{key}", "m": f"max_per_day_{key}"},
    )
    db.execute(
        text("delete from service_categories where specialty = :k"), {"k": key}
    )
    db.execute(text("delete from departments where key = :k"), {"k": key})
    db.commit()


def test_real_pg_unique_index_blocks_raw_duplicate_insert(db_session):
    """ACCEPTANCE #5: the UNIQUE on departments.key exists in the real
    Alembic schema - a raw INSERT that bypasses the API pre-check still
    fails at the DB level."""
    from sqlalchemy.exc import IntegrityError

    db_session.execute(
        text(
            "insert into departments (key, name_ru, display_order, active) "
            "values (:k, :n, 7, true)"
        ),
        {"k": "rq04a_raw", "n": "Raw"},
    )
    db_session.commit()
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "insert into departments (key, name_ru, display_order, active) "
                "values (:k, :n, 7, true)"
            ),
            {"k": "rq04a_raw", "n": "Raw duplicate"},
        )
    db_session.rollback()


class _Boom:
    """Constructor raises — any use of this model aborts the flow."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("RQ-04 injected failure")


def _create(db, key: str, current_user, service_code: str = "RQ04A"):
    """service_code обязателен и коротким: services.service_code —
    String(10) unique; длинные department-ключи дают код > 10 (это
    отдельный латентный дефект хелпера, вне среза RQ-04)."""
    from app.api.v1.endpoints.admin_departments._crud import create_department
    from app.api.v1.endpoints.admin_departments._helpers import DepartmentCreate

    payload = DepartmentCreate(
        key=key,
        name_ru=f"RQ-04 {key}",
        active=True,
        integration={"service_code": service_code},
    )
    return create_department(payload, db=db, current_user=object())


def test_create_builds_exactly_one_settings_row(db_session):
    from types import SimpleNamespace

    result = _create(db_session, "rq04a_ok", SimpleNamespace(id=999, role="Admin"), service_code="RQ04A")
    assert result["success"] is True

    counts = _counts(db_session, "rq04a_ok")
    # F-03 fail-first: pre-fix this is 2/2 (settings created twice)
    assert counts["queue_settings"] == 1, counts
    assert counts["registration_settings"] == 1, counts
    assert counts["departments"] == 1
    _cleanup(db_session, "rq04a_ok")


def test_default_service_contract(db_session):
    from types import SimpleNamespace

    result = _create(db_session, "rq04a_ok", SimpleNamespace(id=999, role="Admin"), service_code="RQ04A")
    assert result["success"] is True
    service_id = result["integration"].get("default_service_id")
    assert service_id, result["integration"]

    row = db_session.execute(
        text(
            "select requires_doctor, queue_tag, coalesce(price::text,'NULL') as price, "
            "is_consultation, coalesce(category_code,'-') as category_code "
            "from services where id = :i"
        ),
        {"i": service_id},
    ).fetchone()
    # ACCEPTANCE #6: no accidental requires_doctor / queue_tag / price;
    # values must match the live contract (consultation, category letter)
    assert row.requires_doctor is False
    assert row.queue_tag is None
    assert row.price == "NULL"
    assert row.is_consultation is True
    assert row.category_code == "R"
    _cleanup(db_session, "rq04a_ok")


def test_injected_failure_in_settings_rolls_back_everything(
    db_session, monkeypatch
):
    """The settings constructor must be invoked exactly ONCE (inside the
    guarded helper). Pre-fix, _crud.py constructed DepartmentQueueSettings
    AGAIN after the intermediate commit; injecting a raising stub there
    left the department persisted without settings. Post-fix the stub is
    never called and creation succeeds with exactly one guarded row."""
    from app.api.v1.endpoints.admin_departments import _crud
    from types import SimpleNamespace

    class _Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("RQ-04 injected failure")

    monkeypatch.setattr(_crud, "DepartmentQueueSettings", _Boom)

    result = _create(db_session, "rq04a_boom", SimpleNamespace(id=999, role="Admin"), service_code="RQ04B")
    assert result["success"] is True

    counts = _counts(db_session, "rq04a_boom")
    assert counts["departments"] == 1, counts
    assert counts["queue_settings"] == 1, counts
    assert counts["registration_settings"] == 1, counts


def test_failure_at_late_staging_rolls_back_everything(db_session, monkeypatch):
    """QueueProfile creation is the LAST onboarding step: a failure there
    (after settings/services staged, before the single commit) must leave
    NOTHING persisted."""
    from app.api.v1.endpoints.admin_departments import _helpers
    from types import SimpleNamespace

    def _boom_tags(*args, **kwargs):
        raise RuntimeError("RQ-04 late-staging failure")

    monkeypatch.setattr(_helpers, "expand_queue_tags", _boom_tags)

    with pytest.raises(RuntimeError):
        _create(db_session, "rq04a_late", SimpleNamespace(id=999, role="Admin"), service_code="RQ04C")

    # teardown-level rollback: nothing staged may survive
    db_session.rollback()

    counts = _counts(db_session, "rq04a_late")
    # nothing persisted at all: no department, hence no dependent rows
    assert counts == {"departments": 0}, counts


def test_retry_after_failure_succeeds(db_session, monkeypatch):
    """A failed attempt must leave zero rows; the immediate retry then
    succeeds cleanly (no «key already taken» from partial state)."""
    from app.api.v1.endpoints.admin_departments import _helpers
    from types import SimpleNamespace

    def _boom_tags(*args, **kwargs):
        raise RuntimeError("RQ-04 late-staging failure")

    monkeypatch.setattr(_helpers, "expand_queue_tags", _boom_tags)

    with pytest.raises(RuntimeError):
        _create(db_session, "rq04a_retry", SimpleNamespace(id=999, role="Admin"), service_code="RQ04D")

    db_session.rollback()  # the failed attempt must leave nothing behind
    monkeypatch.undo()

    result = _create(db_session, "rq04a_retry", SimpleNamespace(id=999, role="Admin"), service_code="RQ04D2")
    assert result["success"] is True

    counts = _counts(db_session, "rq04a_retry")
    assert counts["departments"] == 1
    assert counts["queue_settings"] == 1
    assert counts["registration_settings"] == 1
    _cleanup(db_session, "rq04a_retry")


def test_duplicate_key_conflict_is_consistent(db_session):
    from types import SimpleNamespace

    from fastapi import HTTPException

    first = _create(db_session, "rq04a_dup", SimpleNamespace(id=999, role="Admin"), service_code="RQ04E")
    assert first["success"] is True

    with pytest.raises(HTTPException) as exc:
        _create(db_session, "rq04a_dup", SimpleNamespace(id=999, role="Admin"), service_code="RQ04E")
    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail

    counts = _counts(db_session, "rq04a_dup")
    # ACCEPTANCE #4: the conflict creates no new dependencies
    assert counts["departments"] == 1
    assert counts["queue_settings"] == 1
    assert counts["registration_settings"] == 1
