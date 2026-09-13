"""
RQ-05 serializer slice: GET /registrar/services must expose the
`requires_doctor` flag of every service (F-04: the registrar catalog DTO
omitted it, so the wizard and the server could disagree about whether a
doctor is mandatory).

Acceptance S-03 (part a): the DTO contains a non-null requires_doctor for
each service, with unambiguous semantics for consultation and
non-consultation services alike.

Server-side booking validation ("a requires_doctor service cannot be saved
without an eligible doctor") is traced in the RQ-05 evidence and is
registered as a separate follow-up slice (RQ-05.x) — NOT pinned or fixed
here.

Disposable PostgreSQL: the module provisions its own scratch database
(rq05_check), runs `alembic upgrade head` against it and drops it at the
end. Skips (NOT_RUN, per plan P0) when no disposable PostgreSQL server is
reachable. SQLite is never a substitute here. Only localhost admin
endpoints are ever used for provisioning — a production DATABASE_URL
(remote host) is deliberately rejected.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq05_check"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []

    explicit = os.getenv("RQ05_PG_ADMIN_URL", "").strip()
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
            f"disposable PostgreSQL unavailable — RQ-05 PG acceptance NOT_RUN "
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
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def pg_admin_user(pg_session):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = (
        pg_session.query(User).filter(User.username == "rq05_admin").first()
    )
    if user:
        return user
    user = User(
        username="rq05_admin",
        email="rq05-admin@example.com",
        full_name="RQ-05 Admin",
        hashed_password=get_password_hash("rq05-synthetic-pw"),
        role="Admin",
        is_active=True,
        is_superuser=True,
    )
    pg_session.add(user)
    pg_session.commit()
    pg_session.refresh(user)
    return user


@pytest.fixture
def pg_client(pg_session):
    """TestClient wired to the disposable PostgreSQL session."""
    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        try:
            yield pg_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_services(pg_session) -> dict[str, int]:
    """Three SYNTHETIC services covering the F-04 semantics matrix."""
    from app.models.clinic import ServiceCategory
    from app.models.service import Service

    category = (
        pg_session.query(ServiceCategory)
        .filter(ServiceCategory.code == "rq05-cat")
        .first()
    )
    if not category:
        category = ServiceCategory(
            code="rq05-cat",
            name_ru="RQ-05 synthetic category",
            specialty="laboratory",
            active=True,
        )
        pg_session.add(category)
        pg_session.commit()
        pg_session.refresh(category)

    specs = [
        # (key, service_code, requires_doctor, is_consultation, queue_tag)
        ("proc", "RQ05P", True, False, "lab"),
        ("free", "RQ05F", False, False, "lab"),
        ("cons", "RQ05C", True, True, "cardio"),
    ]
    ids: dict[str, int] = {}
    for key, code, req_doc, is_cons, tag in specs:
        existing = (
            pg_session.query(Service)
            .filter(Service.service_code == code)
            .first()
        )
        if existing:
            ids[key] = existing.id
            continue
        service = Service(
            name=f"RQ-05 synthetic {key}",
            code=code,
            service_code=code,
            category_code="R",
            category_id=category.id,
            queue_tag=tag,
            department_key=tag,
            price=None,
            currency="UZS",
            duration_minutes=30,
            requires_doctor=req_doc,
            is_consultation=is_cons,
            active=True,
        )
        pg_session.add(service)
        pg_session.commit()
        pg_session.refresh(service)
        ids[key] = service.id
    return ids


def _all_rows(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for group_rows in payload["services_by_group"].values():
        rows.extend(group_rows)
    return rows


def test_services_dto_exposes_requires_doctor(pg_client, pg_session, pg_admin_user):
    """S-03(a) fail-first: every service row carries a non-null
    requires_doctor matching the DB value (consultation and not)."""
    from tests.conftest import mint_access_token

    ids = _seed_services(pg_session)
    headers = {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}
    response = pg_client.get("/api/v1/registrar/services", headers=headers)

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in _all_rows(response.json())}

    # F-04 fail-first: pre-fix these rows have no requires_doctor key at all.
    assert rows[ids["proc"]]["requires_doctor"] is True
    assert rows[ids["free"]]["requires_doctor"] is False
    assert rows[ids["cons"]]["requires_doctor"] is True

    # Unambiguous semantics: the flag is present and boolean on EVERY row,
    # for consultation and non-consultation services alike.
    for row in rows.values():
        assert isinstance(row["requires_doctor"], bool), row


def test_requires_doctor_reflects_db_state(pg_client, pg_session, pg_admin_user):
    """The serializer reads the column, it does not inject a constant:
    flipping the DB value flips the DTO value."""
    from tests.conftest import mint_access_token
    from app.models.service import Service

    ids = _seed_services(pg_session)
    service = pg_session.query(Service).filter(Service.id == ids["free"]).first()
    service.requires_doctor = True
    pg_session.commit()

    headers = {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}
    response = pg_client.get("/api/v1/registrar/services", headers=headers)

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in _all_rows(response.json())}
    assert rows[ids["free"]]["requires_doctor"] is True

    service.requires_doctor = False
    pg_session.commit()
