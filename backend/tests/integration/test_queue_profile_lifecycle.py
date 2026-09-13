"""
RQ-12.a: DELETE /registrar/queues/profiles/{profile_key} must NOT clear
Service.queue_tag when the SAME tag is still owned by another (remaining)
QueueProfile (F-11 / ACCEPTANCE S-10 data-loss defect).

Defect being pinned: the cascade cleanup in delete_queue_profile collected
tags_to_clean from the profile being deleted and blanked queue_tag on every
matching service WITHOUT checking whether any remaining profile still owns
the tag — deleting one profile silently untagged services that another
profile's tab still routes, so those services disappeared from the
registrar wizard.

Legacy behavior preserved (pinned here too): tags owned ONLY by the deleted
profile are still cleaned from services, and services_cleaned must count
only services actually cleaned.

Product model unchanged: lifecycle/archive/preview belongs to RQ-12.b/D-02.

Disposable PostgreSQL: the module provisions its own scratch database
(rq12a_check), runs `alembic upgrade head` against it and drops it at the
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
SCRATCH_DB = "rq12a_check"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []

    explicit = os.getenv("RQ12A_PG_ADMIN_URL", "").strip()
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
            f"disposable PostgreSQL unavailable — RQ-12.a PG acceptance NOT_RUN "
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
        pg_session.query(User).filter(User.username == "rq12a_admin").first()
    )
    if user:
        return user
    user = User(
        username="rq12a_admin",
        email="rq12a-admin@example.com",
        full_name="RQ-12.a Admin",
        hashed_password=get_password_hash("rq12a-synthetic-pw"),
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


def _seed_world(pg_session, suffix: str) -> dict[str, int]:
    # service_code is String(10): keep the suffix to one character.
    sfx = suffix[:1]
    """Two SYNTHETIC profiles (A, B) sharing tag T, plus services.

    - profile A owns [T, TA]
    - profile B owns [T, TB]
    - s_shared has tag T  (must SURVIVE delete of A — the defect)
    - s_onlya has tag TA  (must still be cleaned — legacy behavior)
    - s_other has tag TB  (unrelated to A, untouched)
    - s_notag has no tag  (untouched)
    """
    from app.models.clinic import ServiceCategory
    from app.models.queue_profile import QueueProfile
    from app.models.service import Service

    tag_shared = f"rq12a-{suffix}-shared"
    tag_onlya = f"rq12a-{suffix}-onlya"
    tag_b = f"rq12a-{suffix}-b"

    key_a = f"rq12a-{suffix}-a"
    key_b = f"rq12a-{suffix}-b"

    existing = pg_session.query(QueueProfile).filter(
        QueueProfile.key.in_([key_a, key_b])
    ).all()
    if existing:
        for p in existing:
            pg_session.delete(p)
        pg_session.commit()

    profile_a = QueueProfile(
        key=key_a,
        title=f"RQ-12.a {suffix} A",
        queue_tags=[tag_shared, tag_onlya],
        display_order=1,
        is_active=True,
    )
    profile_b = QueueProfile(
        key=key_b,
        title=f"RQ-12.a {suffix} B",
        queue_tags=[tag_shared, tag_b],
        display_order=2,
        is_active=True,
    )
    pg_session.add_all([profile_a, profile_b])
    pg_session.commit()

    category = (
        pg_session.query(ServiceCategory)
        .filter(ServiceCategory.code == "rq12a-cat")
        .first()
    )
    if not category:
        category = ServiceCategory(
            code="rq12a-cat",
            name_ru="RQ-12.a synthetic category",
            specialty="procedures",
            active=True,
        )
        pg_session.add(category)
        pg_session.commit()
        pg_session.refresh(category)

    service_specs = [
        ("s_shared", f"RQ12A{sfx}1", tag_shared),
        ("s_onlya", f"RQ12A{sfx}2", tag_onlya),
        ("s_other", f"RQ12A{sfx}3", tag_b),
        ("s_notag", f"RQ12A{sfx}4", None),
    ]
    ids: dict[str, int] = {}
    for name, code, tag in service_specs:
        service = Service(
            name=f"RQ-12.a synthetic {suffix} {name}",
            code=code,
            service_code=code,
            category_code="R",
            category_id=category.id,
            queue_tag=tag,
            price=None,
            currency="UZS",
            duration_minutes=30,
            active=True,
        )
        pg_session.add(service)
        pg_session.commit()
        pg_session.refresh(service)
        ids[name] = service.id
    ids["key_a"] = key_a
    ids["key_b"] = key_b
    ids["tag_shared"] = tag_shared
    ids["tag_onlya"] = tag_onlya
    ids["tag_b"] = tag_b
    return ids


def _delete_profile(pg_client, pg_admin_user, key: str):
    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}
    return pg_client.delete(
        f"/api/v1/queues/profiles/{key}", headers=headers
    )


def _service_tag(pg_session, service_id: int) -> str | None:
    from app.models.service import Service

    service = pg_session.query(Service).filter(Service.id == service_id).first()
    return service.queue_tag if service else "<missing>"


def test_delete_keeps_shared_tag_when_remaining_profile_owns_it(
    pg_client, pg_session, pg_admin_user
):
    """(a) fail-first: a tag still owned by profile B must keep its
    services after profile A is deleted (S-10 data-loss defect)."""
    ids = _seed_world(pg_session, "k")

    response = _delete_profile(pg_client, pg_admin_user, ids["key_a"])
    assert response.status_code == 200, response.text

    # The shared tag must survive for the remaining owner's tab.
    assert _service_tag(pg_session, ids["s_shared"]) == ids["tag_shared"]
    # Unrelated services are untouched.
    assert _service_tag(pg_session, ids["s_other"]) == ids["tag_b"]
    assert _service_tag(pg_session, ids["s_notag"]) is None


def test_delete_still_clears_tags_owned_only_by_deleted_profile(
    pg_client, pg_session, pg_admin_user
):
    """(b) legacy cleanup preserved: a tag owned ONLY by the deleted
    profile is still cleared from services."""
    ids = _seed_world(pg_session, "c")

    response = _delete_profile(pg_client, pg_admin_user, ids["key_a"])
    assert response.status_code == 200, response.text

    assert _service_tag(pg_session, ids["s_onlya"]) is None


def test_delete_unknown_profile_is_404_without_side_effects(
    pg_client, pg_session, pg_admin_user
):
    """(c) deleting a missing profile is a clean 404, twice, with no
    side effects on profiles or services."""
    ids = _seed_world(pg_session, "m")

    first = _delete_profile(pg_client, pg_admin_user, "rq12a-does-not-exist")
    assert first.status_code == 404
    second = _delete_profile(pg_client, pg_admin_user, "rq12a-does-not-exist")
    assert second.status_code == 404

    # No side effects: both profiles still exist, services untouched.
    from app.models.queue_profile import QueueProfile

    remaining = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key.in_([ids["key_a"], ids["key_b"]]))
        .count()
    )
    assert remaining == 2
    assert _service_tag(pg_session, ids["s_shared"]) == ids["tag_shared"]
    assert _service_tag(pg_session, ids["s_onlya"]) == ids["tag_onlya"]


def test_services_cleaned_counts_only_actually_cleaned(
    pg_client, pg_session, pg_admin_user
):
    """(e) the response must not inflate services_cleaned: only the
    service whose tag is exclusively owned by the deleted profile."""
    ids = _seed_world(pg_session, "n")

    response = _delete_profile(pg_client, pg_admin_user, ids["key_a"])
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["success"] is True
    # Pre-fix this was 2 (the shared-tag service was cleaned too).
    assert payload["services_cleaned"] == 1, payload
    assert _service_tag(pg_session, ids["s_shared"]) == ids["tag_shared"]
