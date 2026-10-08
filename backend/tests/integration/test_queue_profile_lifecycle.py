"""
RQ-12.a + RQ-12.b: lifecycle contract of DELETE/preview/archive for
/registrar/queues/profiles (F-11 / ACCEPTANCE S-10).

RQ-12.a (merged #3221, E-026): the cascade cleanup in delete_queue_profile
must not clear Service.queue_tag when the SAME tag is still owned by
another (remaining) QueueProfile.

RQ-12.b (D-02 owner decision 2026-09-15, E-039): the contract FLIPPED for
used profiles — hard delete of a profile with significant links (services
on its tags, daily queues incl. historical, waiting entries) is now
BLOCKED with 409 and the profile must be archived instead (the existing
QueueProfile.is_active=False transition; no competing archive flag).
Rationale: owner D-02 — "Hard delete — only with proven absence of
significant links". The RQ-12.a expectation "delete succeeds and cleans
exclusively-owned tags" applied to profiles WITH services, which are now
protected; the shared-tag preservation logic remains in the endpoint as
defense-in-depth and the no-data-loss guarantee is now enforced by the
guard itself (nothing is deleted, so no tag can be lost).

RQ-12.b adds:
- GET /queues/profiles/{key}/impact-preview — server-side delete link counts
- POST /queues/profiles/{key}/impact-preview — proposed binding impact
  (services / daily queues / waiting / total entries);
- stale-preview protection: the delete guard re-computes links at
  execution time from the same SSOT, so a stale preview never authorizes
  destruction (S-10 "повторить со stale preview");
- archive/restore through the existing is_active transition preserves
  all links; already-waiting patients stay serviceable by staff after
  the archive (existing queue remains accessible).

Disposable PostgreSQL: the module provisions its own scratch database
(rq12a_check), runs `alembic upgrade head` against it and drops it at the
end. Skips (NOT_RUN, per plan P0) when no disposable PostgreSQL server is
reachable. SQLite is never a substitute here. Only localhost admin
endpoints are ever used for provisioning — a production DATABASE_URL
(remote host) is deliberately rejected.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB_PREFIX = "rq12a_check"
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))

from tests._pg_admin_guard import is_local_admin_dsn  # noqa: E402


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []

    explicit = os.getenv("RQ12B_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)

    # RQ-12.a legacy name kept for cross-slice reuse of the same holder.
    legacy = os.getenv("RQ12A_PG_ADMIN_URL", "").strip()
    if legacy:
        urls.append(legacy)

    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")

    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        u = make_url(env_url)
        # PR #3468 audit P1: a libpq DSN can carry a comma-separated
        # failover host list (netloc host or ?host= / ?hostaddr= query
        # params). EVERY possible endpoint — not just the first failover
        # target — must be local before scratch provisioning may run.
        if u.host and is_local_admin_dsn(env_url):
            urls.append(
                f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}/postgres"
            )
        elif not u.host and is_local_admin_dsn(env_url):
            # Unix-socket DSN (userspace pgserver holder): the socket dir
            # travels in the query string; is_local_admin_dsn has verified
            # every endpoint of the (possibly multi-host) list is local.
            urls.append(env_url)

    return urls


def _scratch_url(admin_url: str) -> tuple[str, str]:
    """(psycopg conninfo, sqlalchemy URL) for the scratch database.

    Preserves unix-socket DSNs (host in the query string) alongside the
    classic TCP form.
    """
    u = make_url(admin_url)
    if not u.host and u.query.get("host"):
        socket_dir = u.query["host"]
        conninfo = (
            f"postgresql://{u.username}:{u.password}@/{SCRATCH_DB}"
            f"?host={socket_dir}"
        )
        sa_url = (
            f"postgresql+psycopg://{u.username}:{u.password}@/{SCRATCH_DB}"
            f"?host={socket_dir}"
        )
        return conninfo, sa_url
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
        # No pre-drop: the run-unique name cannot pre-exist (a collision would
        # take 2**48 parallel runs), and dropping a fixed name unconditionally
        # is exactly the cross-run hazard this fixture used to carry.
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    # PR #3468 audit P2: from this point on a scratch database EXISTS on the
    # admin server. Run-unique names mean the next run can no longer sweep a
    # leaked database (the old fixed-name pre-drop used to), so every
    # provisioning step between CREATE DATABASE and the yield is
    # failure-safe: teardown runs on ALL exit paths — a pre-yield setup
    # failure included — instead of only after a successful yield.
    engine = None
    try:
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
            version = conn.execute(
                text("select version_num from alembic_version")
            ).scalar()
        assert version, "alembic_version must be present after upgrade"
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        with psycopg.connect(admin_url, autocommit=True) as c:
            # Cleanup touches ONLY the run-unique database this process created;
            # WITH (FORCE) clears lingering connections (PG 13+), falling back
            # to the plain form on older servers.
            try:
                c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
            except psycopg.errors.SyntaxError:
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

    user = pg_session.query(User).filter(User.username == "rq12a_admin").first()
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

    existing = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key.in_([key_a, key_b]))
        .all()
    )
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
    return pg_client.delete(f"/api/v1/queues/profiles/{key}", headers=headers)


def _service_tag(pg_session, service_id: int) -> str | None:
    from app.models.service import Service

    service = pg_session.query(Service).filter(Service.id == service_id).first()
    return service.queue_tag if service else "<missing>"


def test_delete_used_profile_blocked_and_shared_tag_intact(
    pg_client, pg_session, pg_admin_user
):
    """(a) RQ-12.b flip (D-02): profile A has services on its tags
    (including the tag shared with profile B) — hard delete is now
    BLOCKED (409); no tag can be lost because nothing is deleted.
    Previously (RQ-12.a) this delete succeeded and cleaned tags."""
    ids = _seed_world(pg_session, "k")

    response = _delete_profile(pg_client, pg_admin_user, ids["key_a"])
    assert response.status_code == 409, response.text

    detail = response.json()["detail"]
    assert detail["reason"] == "profile_has_significant_links"
    assert detail["links"]["services"] >= 1

    # The shared tag must survive for the remaining owner's tab.
    assert _service_tag(pg_session, ids["s_shared"]) == ids["tag_shared"]
    # Exclusive-tag services are intact too — blocked delete cleans nothing.
    assert _service_tag(pg_session, ids["s_onlya"]) == ids["tag_onlya"]
    # Unrelated services are untouched.
    assert _service_tag(pg_session, ids["s_other"]) == ids["tag_b"]
    assert _service_tag(pg_session, ids["s_notag"]) is None


def test_delete_blocked_leaves_exclusive_tag_services_untouched(
    pg_client, pg_session, pg_admin_user
):
    """(b) RQ-12.b flip (D-02): the RQ-12.a "legacy cleanup" contract is
    superseded — a profile WITH services is never deleted, so even a tag
    owned ONLY by the blocked profile keeps its service (archive is the
    supported action instead of deletion)."""
    ids = _seed_world(pg_session, "c")

    response = _delete_profile(pg_client, pg_admin_user, ids["key_a"])
    assert response.status_code == 409, response.text

    assert _service_tag(pg_session, ids["s_onlya"]) == ids["tag_onlya"]


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


def test_delete_blocked_response_reports_no_partial_cleanup(
    pg_client, pg_session, pg_admin_user
):
    """(e) RQ-12.b flip (D-02): the blocked delete must not perform ANY
    partial cleanup — the RQ-12.a services_cleaned inflation pin is
    superseded: a used profile delete changes nothing at all."""
    ids = _seed_world(pg_session, "n")

    response = _delete_profile(pg_client, pg_admin_user, ids["key_a"])
    assert response.status_code == 409, response.text
    payload = response.json()

    # Structured guard payload, not a success payload.
    assert payload["detail"]["reason"] == "profile_has_significant_links"
    assert "success" not in payload
    assert _service_tag(pg_session, ids["s_shared"]) == ids["tag_shared"]


# ===================== RQ-12.b (D-02): preview / archive / delete guard =====================


def _put_profile(pg_client, pg_admin_user, key: str, payload: dict):
    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}
    return pg_client.put(
        f"/api/v1/queues/profiles/{key}", json=payload, headers=headers
    )


def _preview_profile(pg_client, pg_admin_user, key: str):
    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}
    return pg_client.get(
        f"/api/v1/queues/profiles/{key}/impact-preview", headers=headers
    )


def _preview_profile_update(pg_client, pg_admin_user, key: str, payload: dict):
    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}
    return pg_client.post(
        f"/api/v1/queues/profiles/{key}/impact-preview",
        json=payload,
        headers=headers,
    )


def test_binding_update_preview_rejects_non_admin(pg_client, pg_session):
    from app.core.security import get_password_hash
    from app.models.user import User
    from tests.conftest import mint_access_token

    registrar = User(
        username="rq12b_t10_registrar",
        email="rq12b-t10-registrar@example.com",
        full_name="RQ12B T10 Registrar",
        hashed_password=get_password_hash("rq12b-t10-synthetic-password"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    pg_session.add(registrar)
    pg_session.commit()

    headers = {"Authorization": f"Bearer {mint_access_token(registrar)}"}
    response = pg_client.post(
        "/api/v1/queues/profiles/rq12b-t10-auth/impact-preview",
        json={"queue_tags": ["rq12b-t10-new-tag"]},
        headers=headers,
    )

    assert response.status_code == 403, response.text


def test_used_profile_binding_changes_are_blocked_atomically(
    pg_client, pg_session, pg_admin_user
):
    """Used profile tags/order/department are protected while presentation
    updates and archiving remain available; a mixed PUT is all-or-nothing."""
    from app.models.queue_profile import QueueProfile

    world = _seed_profile_with_queue(pg_session, "t10g")
    profile = (
        pg_session.query(QueueProfile).filter(QueueProfile.key == world["key"]).first()
    )
    assert profile is not None
    original_tags = [world["tag"], "rq12b-t10g-second"]
    profile.queue_tags = original_tags
    pg_session.commit()
    original_department = profile.department_key

    for payload in (
        {"queue_tags": [world["tag"], "rq12b-t10g-other"]},
        {"queue_tags": list(reversed(original_tags))},
        {"department_key": "rq12b-t10g-other-dept"},
    ):
        response = _put_profile(pg_client, pg_admin_user, world["key"], payload)
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["reason"] == "profile_binding_change_blocked"
        pg_session.refresh(profile)
        assert profile.queue_tags == original_tags
        assert profile.department_key == original_department

    mixed = _put_profile(
        pg_client,
        pg_admin_user,
        world["key"],
        {
            "title": "RQ-12.b title must not partially save",
            "queue_tags": ["rq12b-t10g-rebound"],
            "department_key": "rq12b-t10g-rebound-dept",
        },
    )
    assert mixed.status_code == 409, mixed.text
    pg_session.refresh(profile)
    assert profile.title == "RQ-12.b t10g profile"
    assert profile.queue_tags == original_tags
    assert profile.department_key == original_department

    # Presentation/archive changes do not rebind queue history.
    archived = _put_profile(
        pg_client,
        pg_admin_user,
        world["key"],
        {"title": "RQ-12.b renamed", "is_active": False},
    )
    assert archived.status_code == 200, archived.text
    pg_session.refresh(profile)
    assert profile.title == "RQ-12.b renamed"
    assert profile.is_active is False
    assert profile.queue_tags == original_tags

    from app.models.online_queue import OnlineQueueEntry

    entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == world["entry_id"])
        .first()
    )
    assert entry is not None and entry.status == "waiting"


def test_unused_profile_can_change_bindings_and_preview_is_read_only(
    pg_client, pg_session, pg_admin_user
):
    from app.models.queue_profile import QueueProfile

    key = "rq12b-t10-unused"
    profile = QueueProfile(
        key=key,
        title="RQ-12.b unused",
        queue_tags=["rq12b-t10-old", "rq12b-t10-second"],
        department_key="rq12b-t10-old-dept",
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()

    payload = {
        "queue_tags": ["rq12b-t10-new", "rq12b-t10-final"],
        "department_key": "rq12b-t10-new-dept",
    }
    preview = _preview_profile_update(pg_client, pg_admin_user, key, payload)
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()
    assert preview_data["current"]["queue_tags"] == [
        "rq12b-t10-old",
        "rq12b-t10-second",
    ]
    assert preview_data["proposed"]["queue_tags"] == payload["queue_tags"]
    assert preview_data["blocked_fields"] == []
    assert preview_data["can_update"] is True
    assert all(value == 0 for value in preview_data["links"].values())

    pg_session.refresh(profile)
    assert profile.queue_tags == ["rq12b-t10-old", "rq12b-t10-second"]
    assert profile.department_key == "rq12b-t10-old-dept"

    updated = _put_profile(pg_client, pg_admin_user, key, payload)
    assert updated.status_code == 200, updated.text
    pg_session.refresh(profile)
    assert profile.queue_tags == payload["queue_tags"]
    assert profile.department_key == payload["department_key"]


def test_legacy_dental_tags_allow_unchanged_binding_on_used_profile(
    pg_client, pg_session, pg_admin_user
):
    """Canonical expansion must not turn an unchanged legacy list into a rebind."""
    from app.models.queue_profile import QueueProfile

    key = "rq12b-t10-dental-legacy"
    legacy_tags = ["dental", "dentistry", "stomatology"]
    profile = QueueProfile(
        key=key,
        title="RQ-12.b legacy dental",
        queue_tags=legacy_tags,
        department_key="stomatology",
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()
    _add_service(pg_session, "t10dent", "T10DENT", "dentist")

    payload = {"title": "RQ-12.b renamed dental", "queue_tags": legacy_tags}
    preview = _preview_profile_update(pg_client, pg_admin_user, key, payload)
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()
    assert preview_data["links"]["services"] == 1
    assert preview_data["changed_binding_fields"] == []
    assert preview_data["blocked_fields"] == []
    assert preview_data["current"]["queue_tags"] == legacy_tags
    assert preview_data["proposed"]["queue_tags"] == legacy_tags

    updated = _put_profile(pg_client, pg_admin_user, key, payload)
    assert updated.status_code == 200, updated.text
    pg_session.refresh(profile)
    assert profile.title == payload["title"]
    assert profile.queue_tags == legacy_tags


def test_doctor_qr_profile_key_queue_blocks_binding_update(
    pg_client, pg_session, pg_admin_user
):
    """Doctor QR queues use profile.key even when it is absent from tags."""
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue
    from app.models.queue_profile import QueueProfile

    world = _seed_profile_with_queue(pg_session, "t10key")
    profile = pg_session.query(QueueProfile).filter_by(key=world["key"]).one()
    doctor = pg_session.query(Doctor).filter_by(id=world["doctor_id"]).one()
    queue = pg_session.query(DailyQueue).filter_by(id=world["queue_id"]).one()
    assert profile.key not in profile.queue_tags

    # join_queue_with_token matches doctors from profile.queue_tags but
    # persists their DailyQueue under profile.key.
    doctor.specialty = world["tag"]
    queue.queue_tag = profile.key
    pg_session.commit()

    payload = {"queue_tags": ["rq12b-t10key-rebound"]}
    preview = _preview_profile_update(pg_client, pg_admin_user, world["key"], payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["links"]["daily_queues"] == 1
    assert preview.json()["links"]["entries_waiting"] == 1
    assert preview.json()["can_update"] is False

    update = _put_profile(pg_client, pg_admin_user, world["key"], payload)
    assert update.status_code == 409, update.text
    assert update.json()["detail"]["reason"] == "profile_binding_change_blocked"
    pg_session.refresh(profile)
    pg_session.refresh(queue)
    assert profile.queue_tags == [world["tag"]]
    assert queue.queue_tag == profile.key


def test_active_public_address_counts_as_profile_usage(
    pg_client, pg_session, pg_admin_user
):
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress
    from app.models.queue_profile import QueueProfile

    key = "rq12b-t10-address-only"
    profile = QueueProfile(
        key=key,
        title="RQ-12.b address only",
        queue_tags=["rq12b-t10-address-tag"],
        department_key="rq12b-t10-address-dept",
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.flush()
    address = QueueDirectionPublicAddress(
        queue_profile_id=profile.id,
        public_code="t10addr23456",
    )
    pg_session.add(address)
    pg_session.commit()

    blocked_delete = _delete_profile(pg_client, pg_admin_user, key)
    assert blocked_delete.status_code == 409, blocked_delete.text
    assert blocked_delete.json()["detail"]["links"]["active_public_addresses"] == 1

    preview = _preview_profile_update(
        pg_client,
        pg_admin_user,
        key,
        {"queue_tags": ["rq12b-t10-address-new"]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["links"]["active_public_addresses"] == 1
    assert preview.json()["blocked_fields"] == ["queue_tags"]
    assert preview.json()["can_update"] is False

    changed = _put_profile(
        pg_client,
        pg_admin_user,
        key,
        {"queue_tags": ["rq12b-t10-address-new"]},
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["links"]["active_public_addresses"] == 1
    pg_session.refresh(profile)
    pg_session.refresh(address)
    assert profile.queue_tags == ["rq12b-t10-address-tag"]
    assert address.queue_profile_id == profile.id
    assert address.retired_at is None

    archived = _put_profile(pg_client, pg_admin_user, key, {"is_active": False})
    assert archived.status_code == 200, archived.text
    pg_session.refresh(profile)
    pg_session.refresh(address)
    assert profile.is_active is False
    assert address.queue_profile_id == profile.id
    assert address.retired_at is None


def test_empty_department_key_is_no_change_for_used_profile(
    pg_client, pg_session, pg_admin_user
):
    """The Select's empty-string value preserves a NULL binding on used profiles."""
    from app.models.queue_profile import QueueProfile

    world = _seed_profile_with_queue(pg_session, "t10emptydept")
    profile = pg_session.query(QueueProfile).filter_by(key=world["key"]).one()
    assert profile.department_key is None

    payload = {"title": "RQ-12.b presentation update", "department_key": ""}
    preview = _preview_profile_update(pg_client, pg_admin_user, world["key"], payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["proposed"]["department_key"] is None
    assert preview.json()["changed_binding_fields"] == []
    assert preview.json()["blocked_fields"] == []

    updated = _put_profile(pg_client, pg_admin_user, world["key"], payload)
    assert updated.status_code == 200, updated.text
    pg_session.refresh(profile)
    assert profile.title == payload["title"]
    assert profile.department_key is None


def test_active_doctor_mapping_blocks_profile_rebinding(
    pg_client, pg_session, pg_admin_user
):
    from app.models.clinic import Doctor
    from app.models.queue_profile import QueueProfile

    key = "rq12b-t10-doctor-only"
    tag = "rq12b-t10-doctor-only-tag"
    profile = QueueProfile(
        key=key,
        title="RQ-12.b doctor only",
        queue_tags=[tag],
        department_key=None,
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add_all(
        [
            profile,
            Doctor(specialty=tag, active=True),
            # The canonical DailyQueue identity is not automatically a
            # doctor-routing tag when it is absent from queue_tags.
            Doctor(specialty=key, active=True),
        ]
    )
    pg_session.commit()

    payload = {"queue_tags": ["rq12b-t10-doctor-only-new"]}
    preview = _preview_profile_update(pg_client, pg_admin_user, key, payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["links"]["active_doctors"] == 1
    assert preview.json()["can_update"] is False

    updated = _put_profile(pg_client, pg_admin_user, key, payload)
    assert updated.status_code == 409, updated.text
    assert updated.json()["detail"]["links"]["active_doctors"] == 1


def test_active_queue_resource_mapping_blocks_profile_rebinding(
    pg_client, pg_session, pg_admin_user
):
    from app.models.online_queue import QueueResource
    from app.models.queue_profile import QueueProfile

    key = "rq12b-t10-resource-only"
    tag = "rq12b-t10-resource-only-tag"
    profile = QueueProfile(
        key=key,
        title="RQ-12.b resource only",
        queue_tags=[tag],
        department_key=None,
        is_active=True,
        show_on_qr_page=False,
    )
    resource = QueueResource(
        code="t10-resource-only",
        queue_tag=tag,
        display_name="RQ-12.b synthetic resource",
        active=True,
    )
    pg_session.add_all(
        [
            profile,
            resource,
            # The profile key is a queue identity, not a resource mapping
            # unless it is also explicitly one of the profile's tags.
            QueueResource(
                code="t10-resource-profile-key",
                queue_tag=key,
                display_name="RQ-12.b synthetic profile-key resource",
                active=True,
            ),
        ]
    )
    pg_session.commit()

    payload = {"queue_tags": ["rq12b-t10-resource-only-new"]}
    preview = _preview_profile_update(pg_client, pg_admin_user, key, payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["links"]["active_queue_resources"] == 1
    assert preview.json()["can_update"] is False

    updated = _put_profile(pg_client, pg_admin_user, key, payload)
    assert updated.status_code == 409, updated.text
    assert updated.json()["detail"]["links"]["active_queue_resources"] == 1


def test_department_linked_service_blocks_department_binding_change(
    pg_client, pg_session, pg_admin_user
):
    from app.models.queue_profile import QueueProfile
    from app.models.service import Service

    key = "rq12b-t10-dept-service"
    department_key = "rq12b-t10-dept-service-dept"
    profile = QueueProfile(
        key=key,
        title="RQ-12.b department service",
        queue_tags=["rq12b-t10-dept-service-tag"],
        department_key=department_key,
        is_active=True,
        show_on_qr_page=False,
    )
    service = Service(
        name="RQ-12.b department-only service",
        code="T10DSVC",
        service_code="T10DSVC",
        queue_tag=None,
        department_key=department_key,
        active=True,
    )
    pg_session.add_all([profile, service])
    pg_session.commit()

    payload = {"department_key": "rq12b-t10-dept-service-new"}
    preview = _preview_profile_update(pg_client, pg_admin_user, key, payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["links"]["department_services"] == 1
    assert preview.json()["can_update"] is False

    updated = _put_profile(pg_client, pg_admin_user, key, payload)
    assert updated.status_code == 409, updated.text
    assert updated.json()["detail"]["links"]["department_services"] == 1


def test_binding_update_rechecks_after_stale_preview(
    pg_client, pg_session, pg_admin_user
):
    from app.models.queue_profile import QueueProfile

    key = "rq12b-t10-stale"
    tag = "rq12b-t10-stale-tag"
    profile = QueueProfile(
        key=key,
        title="RQ-12.b stale binding",
        queue_tags=[tag],
        department_key="rq12b-t10-stale-dept",
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()

    payload = {"queue_tags": ["rq12b-t10-stale-new"]}
    preview = _preview_profile_update(pg_client, pg_admin_user, key, payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["can_update"] is True

    _add_service(pg_session, "t10stale", "T10ST1", tag)
    response = _put_profile(pg_client, pg_admin_user, key, payload)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["reason"] == "profile_binding_change_blocked"

    pg_session.refresh(profile)
    assert profile.queue_tags == [tag]


def test_public_address_provision_serializes_with_binding_update(
    pg_engine, pg_session, pg_admin_user, monkeypatch
):
    """A binding PUT waits on the shared scope, then rechecks and blocks."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        QueueProfileUpdate,
        update_queue_profile,
    )
    from app.models.queue_profile import QueueProfile
    from app.services.queue_service import queue_service
    from app.services.queue_svc import _operations as queue_operations

    key = "rq12b-t10-address-race"
    original_tags = ["rq12b-t10-address-race-tag"]
    profile = QueueProfile(
        key=key,
        title="RQ-12.b address race",
        queue_tags=original_tags,
        department_key=None,
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()
    profile_id = profile.id

    session_factory = sessionmaker(bind=pg_engine, future=True)
    provision_locked = threading.Event()
    finish_provision = threading.Event()
    update_started = threading.Event()
    pids: dict[str, int] = {}
    original_generator = queue_operations.generate_public_code

    def paused_generator():
        provision_locked.set()
        if not finish_provision.wait(timeout=10):
            raise TimeoutError("test did not release address provisioning")
        return original_generator()

    monkeypatch.setattr(queue_operations, "generate_public_code", paused_generator)

    def provision():
        db = session_factory()
        try:
            pids["provision"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            profile_row = (
                db.query(QueueProfile).filter(QueueProfile.id == profile_id).first()
            )
            assert profile_row is not None
            row, created = queue_service.provision_public_address(
                db, profile=profile_row
            )
            return row.public_code, created
        finally:
            db.rollback()
            db.close()

    def update_binding():
        db = session_factory()
        try:
            pids["update"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            update_started.set()
            try:
                update_queue_profile(
                    profile_key=key,
                    profile_data=QueueProfileUpdate(
                        queue_tags=["rq12b-t10-address-race-new"]
                    ),
                    db=db,
                    current_user=pg_admin_user,
                )
                return 200
            except HTTPException as exc:
                return exc.status_code
        finally:
            db.rollback()
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        provision_future = executor.submit(provision)
        update_future = None
        try:
            provision_lock_observed = provision_locked.wait(timeout=5)
            assert provision_lock_observed, "provision did not lock the profile"
            update_future = executor.submit(update_binding)
            assert update_started.wait(timeout=5), "binding update did not start"

            deadline = time.monotonic() + 5
            blocked_by_provision = False
            while time.monotonic() < deadline:
                with pg_engine.connect() as connection:
                    blockers = connection.execute(
                        text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": pids["update"]},
                    ).scalar_one()
                if pids["provision"] in blockers:
                    blocked_by_provision = True
                    break
                if update_future.done():
                    break
                time.sleep(0.02)
            assert blocked_by_provision, "update must wait on the shared binding scope"
        finally:
            finish_provision.set()

        address_code, created = provision_future.result(timeout=10)
        assert update_future is not None
        assert update_future.result(timeout=10) == 409

    pg_session.expire_all()
    pg_session.refresh(profile)
    assert profile.queue_tags == original_tags
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress

    address = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(QueueDirectionPublicAddress.public_code == address_code)
        .one()
    )
    assert created is True
    assert address.queue_profile_id == profile.id
    assert address.retired_at is None


def test_delete_serializes_with_public_address_provision(
    pg_engine, pg_session, pg_admin_user, monkeypatch
):
    """DELETE waits for provisioning, then observes and preserves its address."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.orm import Query, sessionmaker

    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        delete_queue_profile,
    )
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress
    from app.models.queue_profile import QueueProfile
    from app.services.queue_service import queue_service
    from app.services.queue_svc import _operations as queue_operations

    key = "rq12b-t10-delete-address-race"
    profile = QueueProfile(
        key=key,
        title="RQ-12.b delete/address race",
        queue_tags=["rq12b-t10-delete-address-tag"],
        department_key=None,
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()
    profile_id = profile.id

    session_factory = sessionmaker(bind=pg_engine, future=True)
    provision_locked = threading.Event()
    finish_provision = threading.Event()
    delete_started = threading.Event()
    delete_counted_address = threading.Event()
    pids: dict[str, int] = {}
    original_generator = queue_operations.generate_public_code
    original_count = Query.count

    def paused_generator():
        provision_locked.set()
        if not finish_provision.wait(timeout=10):
            raise TimeoutError("test did not release address provisioning")
        return original_generator()

    def observe_address_usage_count(query):
        result = original_count(query)
        if (
            threading.current_thread().name == "t10-delete-worker"
            and query.column_descriptions[0].get("entity")
            is QueueDirectionPublicAddress
        ):
            delete_counted_address.set()
        return result

    monkeypatch.setattr(queue_operations, "generate_public_code", paused_generator)
    monkeypatch.setattr(Query, "count", observe_address_usage_count)

    def provision_address():
        with session_factory() as db:
            pids["provision"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            profile_row = db.get(QueueProfile, profile_id)
            assert profile_row is not None
            row, created = queue_service.provision_public_address(
                db, profile=profile_row
            )
            assert created is True
            return row.public_code

    def delete_profile():
        threading.current_thread().name = "t10-delete-worker"
        with session_factory() as db:
            pids["delete"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            delete_started.set()
            try:
                delete_queue_profile(key, db, pg_admin_user)
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        provision_future = executor.submit(provision_address)
        delete_future = None
        try:
            assert provision_locked.wait(timeout=5), "provision did not lock profile"
            delete_future = executor.submit(delete_profile)
            assert delete_started.wait(timeout=5), "profile deletion did not start"

            deadline = time.monotonic() + 5
            blocked_by_provision = False
            while time.monotonic() < deadline:
                with pg_engine.connect() as connection:
                    blockers = connection.execute(
                        text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": pids["delete"]},
                    ).scalar_one()
                if pids["provision"] in blockers:
                    blocked_by_provision = True
                    break
                if delete_future.done():
                    break
                time.sleep(0.02)

            assert blocked_by_provision, "DELETE must wait for the profile row lock"
            assert (
                not delete_counted_address.is_set()
            ), "DELETE must acquire the profile lock before reading dependencies"
        finally:
            finish_provision.set()

        public_code = provision_future.result(timeout=10)
        assert delete_future is not None
        assert delete_future.result(timeout=10) == 409

    pg_session.expire_all()
    profile = pg_session.query(QueueProfile).filter_by(key=key).one()
    address = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter_by(public_code=public_code)
        .one()
    )
    assert address.queue_profile_id == profile.id
    assert address.retired_at is None


def test_tagged_daily_queue_writer_serializes_profile_binding_update(
    pg_engine, pg_session, pg_admin_user
):
    """A tagged queue commit wins the shared scope and blocks a rebind."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date

    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        QueueProfileUpdate,
        update_queue_profile,
    )
    from app.crud.queue_resource_routing import lock_daily_queue_creation
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue
    from app.models.queue_profile import QueueProfile
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    key = f"rq12b-t10-writer-first-{suffix}"
    tag = f"rq12b-wf-{suffix}"
    profile = QueueProfile(
        key=key,
        title="T10 writer first",
        queue_tags=[tag],
        department_key=None,
        is_active=True,
        show_on_qr_page=False,
    )
    doctor = Doctor(specialty=f"unrelated-{suffix}", active=False)
    pg_session.add_all([profile, doctor])
    pg_session.commit()
    pg_session.refresh(doctor)

    session_factory = sessionmaker(bind=pg_engine, future=True)
    writer_holds_scope = threading.Event()
    allow_writer_commit = threading.Event()
    update_started = threading.Event()
    pids: dict[str, int] = {}

    def tagged_writer() -> None:
        with session_factory() as db:
            pids["writer"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            lock_daily_queue_creation(db, date.today(), doctor.id, queue_tag=tag)
            writer_holds_scope.set()
            if not allow_writer_commit.wait(timeout=10):
                raise TimeoutError("profile update did not reach the lock")
            db.add(
                DailyQueue(
                    day=date.today(),
                    specialist_id=doctor.id,
                    queue_tag=tag,
                    active=True,
                )
            )
            db.commit()

    def update_binding() -> int:
        with session_factory() as db:
            pids["update"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            user = db.get(User, pg_admin_user.id)
            update_started.set()
            try:
                update_queue_profile(
                    profile_key=key,
                    profile_data=QueueProfileUpdate(queue_tags=[f"rq12b-new-{suffix}"]),
                    db=db,
                    current_user=user,
                )
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer_future = executor.submit(tagged_writer)
        update_future = None
        try:
            assert writer_holds_scope.wait(timeout=5)
            update_future = executor.submit(update_binding)
            assert update_started.wait(timeout=5)

            deadline = time.monotonic() + 5
            update_waited_for_writer = False
            while time.monotonic() < deadline:
                with pg_engine.connect() as connection:
                    blockers = connection.execute(
                        text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": pids["update"]},
                    ).scalar_one()
                if pids["writer"] in blockers:
                    update_waited_for_writer = True
                    break
                if update_future.done():
                    break
                time.sleep(0.02)
            assert update_waited_for_writer, (
                "binding update must wait for tagged writer"
            )
        finally:
            allow_writer_commit.set()

        writer_future.result(timeout=10)
        assert update_future is not None
        assert update_future.result(timeout=10) == 409

    pg_session.expire_all()
    pg_session.refresh(profile)
    assert profile.queue_tags == [tag]
    assert (
        pg_session.query(DailyQueue)
        .filter(DailyQueue.queue_tag == tag, DailyQueue.specialist_id == doctor.id)
        .count()
        == 1
    )


def test_tagged_daily_queue_writer_rejects_binding_changed_while_waiting(
    pg_engine, pg_session, pg_admin_user, monkeypatch
):
    """A stale tagged writer returns 409 and inserts nothing after a rebind."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date

    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints.registrar_integration import _queue_profiles
    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        QueueProfileUpdate,
        update_queue_profile,
    )
    from app.crud.queue_owner_invariant import QueueProfileBindingChanged
    from app.crud.queue_resource_routing import lock_daily_queue_creation
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue
    from app.models.queue_profile import QueueProfile
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    key = f"rq12b-t10-update-first-{suffix}"
    tag = f"rq12b-uf-{suffix}"
    stale_tag_variant = tag.upper()
    new_tag = f"rq12b-new-{suffix}"
    profile = QueueProfile(
        key=key,
        title="T10 update first",
        queue_tags=[tag],
        department_key=None,
        is_active=True,
        show_on_qr_page=False,
    )
    doctor = Doctor(specialty=f"unrelated-{suffix}", active=False)
    pg_session.add_all([profile, doctor])
    pg_session.commit()
    pg_session.refresh(doctor)

    session_factory = sessionmaker(bind=pg_engine, future=True)
    usage_checked = threading.Event()
    allow_update_commit = threading.Event()
    writer_started = threading.Event()
    pids: dict[str, int] = {}
    original_link_counts = _queue_profiles._profile_link_counts

    def pause_after_usage_check(db, current_profile):
        counts = original_link_counts(db, current_profile)
        if threading.current_thread().name.startswith("t10-update-first"):
            usage_checked.set()
            if not allow_update_commit.wait(timeout=10):
                raise TimeoutError("tagged writer did not reach the profile lock")
        return counts

    monkeypatch.setattr(
        _queue_profiles, "_profile_link_counts", pause_after_usage_check
    )

    def update_binding() -> int:
        with session_factory() as db:
            user = db.get(User, pg_admin_user.id)
            try:
                update_queue_profile(
                    profile_key=key,
                    profile_data=QueueProfileUpdate(queue_tags=[new_tag]),
                    db=db,
                    current_user=user,
                )
                return 200
            except HTTPException as exc:
                return exc.status_code

    def tagged_writer() -> int:
        with session_factory() as db:
            pids["writer"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            writer_started.set()
            try:
                lock_daily_queue_creation(
                    db,
                    date.today(),
                    doctor.id,
                    queue_tag=stale_tag_variant,
                )
            except QueueProfileBindingChanged as exc:
                return exc.status_code
            db.add(
                DailyQueue(
                    day=date.today(),
                    specialist_id=doctor.id,
                    queue_tag=stale_tag_variant,
                    active=True,
                )
            )
            db.commit()
            return 201

    with ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="t10-update-first"
    ) as executor:
        update_future = executor.submit(update_binding)
        writer_future = None
        try:
            assert usage_checked.wait(timeout=5)
            writer_future = executor.submit(tagged_writer)
            assert writer_started.wait(timeout=5)

            deadline = time.monotonic() + 5
            writer_waited_for_update = False
            while time.monotonic() < deadline:
                if "writer" not in pids:
                    time.sleep(0.02)
                    continue
                with pg_engine.connect() as connection:
                    blockers = connection.execute(
                        text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": pids["writer"]},
                    ).scalar_one()
                if blockers:
                    writer_waited_for_update = True
                    break
                if writer_future.done():
                    break
                time.sleep(0.02)
            assert writer_waited_for_update, (
                "tagged writer must wait for profile update"
            )
        finally:
            allow_update_commit.set()

        assert update_future.result(timeout=10) == 200
        assert writer_future is not None
        assert writer_future.result(timeout=10) == 409

    pg_session.expire_all()
    pg_session.refresh(profile)
    assert profile.queue_tags == [new_tag]
    assert (
        pg_session.query(DailyQueue)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.specialist_id == doctor.id,
        )
        .count()
        == 0
    )


def test_tagged_service_writer_rejects_binding_changed_while_waiting(
    pg_engine, pg_session, pg_admin_user, monkeypatch
):
    """A Service insert waiting behind a rebind returns 409 without writing."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints.registrar_integration import _queue_profiles
    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        QueueProfileUpdate,
        update_queue_profile,
    )
    from app.models.queue_profile import QueueProfile
    from app.models.service import Service
    from app.models.user import User
    from app.services.services_api_service import ServicesApiService

    suffix = uuid.uuid4().hex[:8]
    key = f"rq12b-t10-service-{suffix}"
    tag = f"rq12b-svc-{suffix}"
    new_tag = f"rq12b-new-svc-{suffix}"
    service_name = f"T10 concurrent service {suffix}"
    profile = QueueProfile(
        key=key,
        title="T10 service writer",
        queue_tags=[tag],
        department_key=None,
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()

    session_factory = sessionmaker(bind=pg_engine, future=True)
    usage_checked = threading.Event()
    allow_update_commit = threading.Event()
    writer_started = threading.Event()
    pids: dict[str, int] = {}
    original_link_counts = _queue_profiles._profile_link_counts

    def pause_after_usage_check(db, current_profile):
        counts = original_link_counts(db, current_profile)
        if threading.current_thread().name.startswith("t10-service-update"):
            usage_checked.set()
            if not allow_update_commit.wait(timeout=10):
                raise TimeoutError("service writer did not reach the profile lock")
        return counts

    monkeypatch.setattr(
        _queue_profiles, "_profile_link_counts", pause_after_usage_check
    )

    def update_binding() -> int:
        with session_factory() as db:
            user = db.get(User, pg_admin_user.id)
            try:
                update_queue_profile(
                    profile_key=key,
                    profile_data=QueueProfileUpdate(queue_tags=[new_tag]),
                    db=db,
                    current_user=user,
                )
                return 200
            except HTTPException as exc:
                return exc.status_code

    def create_service() -> int:
        with session_factory() as db:
            pids["writer"] = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            writer_started.set()
            try:
                ServicesApiService(db).create_service(
                    service_data={
                        "name": service_name,
                        "queue_tag": tag,
                        "requires_doctor": False,
                    }
                )
                return 201
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="t10-service-update"
    ) as executor:
        update_future = executor.submit(update_binding)
        writer_future = None
        try:
            assert usage_checked.wait(timeout=5)
            writer_future = executor.submit(create_service)
            assert writer_started.wait(timeout=5)

            deadline = time.monotonic() + 5
            writer_waited_for_update = False
            while time.monotonic() < deadline:
                if "writer" not in pids:
                    time.sleep(0.02)
                    continue
                with pg_engine.connect() as connection:
                    blockers = connection.execute(
                        text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": pids["writer"]},
                    ).scalar_one()
                if blockers:
                    writer_waited_for_update = True
                    break
                if writer_future.done():
                    break
                time.sleep(0.02)
            assert writer_waited_for_update, "service writer must wait for profile update"
        finally:
            allow_update_commit.set()

        assert update_future.result(timeout=10) == 200
        assert writer_future is not None
        assert writer_future.result(timeout=10) == 409

    pg_session.expire_all()
    pg_session.refresh(profile)
    assert profile.queue_tags == [new_tag]
    assert (
        pg_session.query(Service).filter(Service.name == service_name).count() == 0
    )


def _public_profile_keys(pg_client) -> set[str]:
    response = pg_client.get("/api/v1/queues/profiles/public")
    assert response.status_code == 200, response.text
    return {s["specialty"] for s in response.json().get("specialists", [])}


def _add_service(pg_session, suffix: str, code: str, tag: str | None) -> int:
    from app.models.clinic import ServiceCategory
    from app.models.service import Service

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

    service = Service(
        name=f"RQ-12.b synthetic {suffix} {code}",
        code=code[:10],
        service_code=code[:10],
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
    return service.id


def _seed_profile_with_queue(pg_session, suffix: str) -> dict[str, Any]:
    """A used profile whose ONLY significant links are queue-side:
    one active DailyQueue under its tag with one waiting entry
    (no services). Mirrors the D-02 case 'архивирование используемой
    вкладки с ожидающими пациентами'."""
    from datetime import date, datetime

    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.queue_profile import QueueProfile

    tag = f"rq12b-{suffix}-tag"
    key = f"rq12b-{suffix}-profile"

    existing = pg_session.query(QueueProfile).filter(QueueProfile.key == key).first()
    if existing:
        pg_session.delete(existing)
        pg_session.commit()

    profile = QueueProfile(
        key=key,
        title=f"RQ-12.b {suffix} profile",
        queue_tags=[tag],
        display_order=9,
        is_active=True,
        show_on_qr_page=True,
    )
    pg_session.add(profile)
    pg_session.commit()
    pg_session.refresh(profile)

    doctor = Doctor(
        specialty="rq12b-synthetic",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
    )
    pg_session.add(doctor)
    pg_session.commit()
    pg_session.refresh(doctor)

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag=tag,
        active=True,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=15,
    )
    pg_session.add(queue)
    pg_session.commit()
    pg_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_name=f"RQ12B{suffix} SYNTHETIC PATIENT",
        status="waiting",
        source="desk",
        queue_time=datetime.now(),
    )
    pg_session.add(entry)
    pg_session.commit()
    pg_session.refresh(entry)

    return {
        "key": key,
        "tag": tag,
        "queue_id": queue.id,
        "entry_id": entry.id,
        "day": date.today().isoformat(),
        "doctor_id": doctor.id,
    }


def test_impact_preview_counts_links_without_mutating(
    pg_client, pg_session, pg_admin_user
):
    """RQ-12.b: the preview reports services/queues/entries counts from
    the server SSOT, recommends archive for a used profile and delete
    for a linkless one, and mutates nothing."""
    from app.models.queue_profile import QueueProfile
    from app.models.service import Service

    ids = _seed_world(pg_session, "p")

    before_services = pg_session.query(Service).count()
    before_profiles = pg_session.query(QueueProfile).count()

    response = _preview_profile(pg_client, pg_admin_user, ids["key_a"])
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["profile"]["key"] == ids["key_a"]
    # s_shared (tag shared with B) + s_onlya (exclusive tag of A).
    assert payload["links"]["services"] == 2
    assert payload["can_hard_delete"] is False
    assert payload["recommendation"] == "archive"

    unused = _preview_profile(pg_client, pg_admin_user, ids["key_b"])
    assert unused.status_code == 200
    # Profile B also owns tags with services (s_shared, s_other).
    assert unused.json()["links"]["services"] == 2
    assert unused.json()["can_hard_delete"] is False

    missing = _preview_profile(pg_client, pg_admin_user, "rq12b-missing")
    assert missing.status_code == 404

    after_services = pg_session.query(Service).count()
    after_profiles = pg_session.query(QueueProfile).count()
    assert (before_services, before_profiles) == (
        after_services,
        after_profiles,
    ), "preview must be read-only"


def test_delete_blocked_when_only_link_is_queue_with_waiting_patient(
    pg_client, pg_session, pg_admin_user
):
    """RQ-12.b (D-02): a profile whose tags own an active daily queue
    with a waiting patient has significant links even with ZERO
    services — delete is blocked; the waiting patient stays serviceable
    after the profile is archived (existing queue remains accessible to
    staff); restore brings the tab back."""
    world = _seed_profile_with_queue(pg_session, "w")

    preview = _preview_profile(pg_client, pg_admin_user, world["key"])
    assert preview.status_code == 200, preview.text
    links = preview.json()["links"]
    assert links["services"] == 0
    assert links["daily_queues"] == 1
    assert links["entries_waiting"] == 1
    assert links["entries_total"] == 1
    assert preview.json()["can_hard_delete"] is False

    blocked = _delete_profile(pg_client, pg_admin_user, world["key"])
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["links"]["entries_waiting"] == 1

    from app.models.online_queue import OnlineQueueEntry
    from app.models.queue_profile import QueueProfile

    entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == world["entry_id"])
        .first()
    )
    assert entry is not None and entry.status == "waiting"

    # Archive via the EXISTING is_active transition (D-02: no new flag).
    archived = _put_profile(
        pg_client, pg_admin_user, world["key"], {"is_active": False}
    )
    assert archived.status_code == 200, archived.text

    # Public QR entry points no longer offer the archived profile...
    assert world["key"] not in _public_profile_keys(pg_client)
    # ...but staff can still see it via the admin listing...
    from tests.conftest import mint_access_token

    headers = {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}
    staff_list = pg_client.get(
        "/api/v1/queues/profiles",
        params={"active_only": "false"},
        headers=headers,
    )
    assert staff_list.status_code == 200, staff_list.text
    staff_keys = {p["key"] for p in staff_list.json().get("profiles", [])}
    assert world["key"] in staff_keys

    # ...and the already-waiting patient remains serviceable: the staff
    # today surface still shows the queue data (it is driven by the
    # queue/entries rows, not by the profile's active flag).
    today = pg_client.get(
        "/api/v1/registrar/queues/today",
        params={"target_date": world["day"]},
        headers=headers,
    )
    assert today.status_code == 200, today.text
    # The waiting patient (synthetic marker RQ12Bw) must stay visible to
    # staff after the archive — the today surface is driven by queue and
    # entry rows, not by the profile's active flag (D-02).
    assert (
        "RQ12B" in today.text
    ), "waiting patient must stay visible to staff after archive"

    restored = _put_profile(pg_client, pg_admin_user, world["key"], {"is_active": True})
    assert restored.status_code == 200, restored.text
    assert world["key"] in _public_profile_keys(pg_client)

    profile = (
        pg_session.query(QueueProfile).filter(QueueProfile.key == world["key"]).first()
    )
    assert profile is not None and profile.is_active is True


def test_stale_preview_does_not_authorize_delete(pg_client, pg_session, pg_admin_user):
    """RQ-12.b (D-02, S-10): preview said 'can_hard_delete', then the
    world changed (a service took the profile's tag) — the delete must
    re-verify links at execution time and refuse (409). A stale preview
    never authorizes destruction."""
    from app.models.queue_profile import QueueProfile

    tag = "rq12b-stale-tag"
    key = "rq12b-stale-profile"

    existing = pg_session.query(QueueProfile).filter(QueueProfile.key == key).first()
    if existing:
        pg_session.delete(existing)
        pg_session.commit()

    profile = QueueProfile(
        key=key,
        title="RQ-12.b stale preview profile",
        queue_tags=[tag],
        display_order=10,
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()

    # Step 1: no links yet — the preview honestly allows hard delete.
    preview = _preview_profile(pg_client, pg_admin_user, key)
    assert preview.status_code == 200, preview.text
    assert preview.json()["can_hard_delete"] is True
    assert preview.json()["recommendation"] == "delete"

    # Step 2: the world changes AFTER the preview was rendered.
    _add_service(pg_session, "stale", "RQ12B1", tag)

    # Step 3: delete must re-check reality, not trust the stale preview.
    blocked = _delete_profile(pg_client, pg_admin_user, key)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["links"]["services"] == 1

    # And the refreshed preview agrees with the execution-time reality.
    refreshed = _preview_profile(pg_client, pg_admin_user, key)
    assert refreshed.json()["can_hard_delete"] is False

    pg_session.refresh(profile)
    assert profile is not None


def test_delete_unused_profile_succeeds(pg_client, pg_session, pg_admin_user):
    """RQ-12.b (D-02): hard delete is still available for a profile with
    PROVEN absence of significant links — no services, no queues, no
    entries; exclusive tags with no service rows are no obstacle."""
    from app.models.queue_profile import QueueProfile

    key = "rq12b-unused-profile"
    tag = "rq12b-unused-tag"

    existing = pg_session.query(QueueProfile).filter(QueueProfile.key == key).first()
    if existing:
        pg_session.delete(existing)
        pg_session.commit()

    profile = QueueProfile(
        key=key,
        title="RQ-12.b unused profile",
        queue_tags=[tag],
        display_order=11,
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add(profile)
    pg_session.commit()

    # Sanity: preview proves zero significant links.
    preview = _preview_profile(pg_client, pg_admin_user, key)
    assert preview.status_code == 200
    assert all(v == 0 for v in preview.json()["links"].values())

    response = _delete_profile(pg_client, pg_admin_user, key)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    # Nothing could be cleaned: no service rows referenced the tags.
    assert payload["services_cleaned"] == 0

    gone = pg_session.query(QueueProfile).filter(QueueProfile.key == key).first()
    assert gone is None


# ============================================================
# RQ-13.a — department ↔ profile lifecycle coherence (D-06)
#
# Owner decision D-06 (APPROVED 2026-09-15, E-039): effective settings
# resolve server-side clinic → department → owner; deactivating a
# department BLOCKS new records but keeps waiting patients serviceable
# and never finishes/blocks existing service. Plan RQ-13: rename/order/
# active must be traced to профиль/QR/запись — today the profile only
# MIRRORS the department at creation time and diverges afterwards (F-12):
# rename leaves diverging titles, deactivation hides nothing on the tab
# or QR layer, and department hard-delete destroys the 1:1 profile via
# raw db.delete() bypassing the RQ-12.b D-02 guard (waiting patients
# would disappear from every tab surface — S-11 violation).
#
# Contract pinned here:
# - deactivating a department hides ALL profiles linked to it
#   (department_key == dept.key or the 1:1 key == dept.key) on the
#   registrar tabs AND the public QR page; queues/entries are untouched;
# - reactivating restores ONLY the 1:1 department-owned profile
#   (key == dept.key AND department_key == dept.key); independently
#   archived profiles are never resurrected (D-02 coherence);
# - renaming syncs title/title_ru of the 1:1 profile only; display_order
#   and icon/color stay independent axes (F-19/RQ-23 territory);
# - DELETE /admin/departments/{id} is blocked with 409 when any linked
#   profile still has queue history/waiting entries (same bar as the
#   D-02 profile guard: patient data must not disappear); a linkless
#   department keeps today's cascade behavior.
# ============================================================


def _dep_headers(pg_admin_user) -> dict:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}


def _create_department(pg_client, headers: dict, suffix: str, **overrides) -> dict:
    payload = {
        "key": f"rq13a{suffix}",
        "name_ru": f"RQ13A {suffix} Dept",
        "active": True,
    }
    payload.update(overrides)
    # service_code DB column is VARCHAR(10): the auto-created consultation
    # service needs an explicit short code for these synthetic keys.
    payload.setdefault("integration", {})
    if not payload["integration"].get("service_code"):
        payload["integration"] = dict(payload["integration"])
        payload["integration"]["service_code"] = f"S{len(suffix)}{suffix[:2]}"
    resp = pg_client.post("/api/v1/admin/departments", headers=headers, json=payload)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


def _linked_profiles(pg_session, dept_key: str) -> list:
    from app.models.queue_profile import QueueProfile

    return (
        pg_session.query(QueueProfile)
        .filter(
            (QueueProfile.department_key == dept_key) | (QueueProfile.key == dept_key)
        )
        .all()
    )


def _tab_keys(pg_client, headers: dict) -> set[str]:
    resp = pg_client.get("/api/v1/queues/profiles", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    if isinstance(items, dict):
        items = items.get("profiles", items.get("data", []))
    return {p["key"] for p in items}


def _tab_keys_debug(pg_client, headers: dict):
    resp = pg_client.get("/api/v1/queues/profiles", headers=headers)
    return resp


def _public_keys(pg_client) -> set[str]:
    resp = pg_client.get("/api/v1/queues/profiles/public")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    if isinstance(items, dict):
        items = items.get("specialists", items.get("profiles", []))
    return {p["specialty"] for p in items}


def _seed_waiting_entry_for_department(pg_session, dept_key: str, suffix: str) -> dict:
    """One active DailyQueue + one waiting entry under a tag owned by the
    department's 1:1 profile (expand_queue_tags guarantees the bare key
    is owned). Mirrors the S-11 harm: a department hard-delete that
    takes the profile (and its tabs) away while patients still wait."""
    from datetime import date, datetime

    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    tag = f"rq13a{suffix}"
    doctor = Doctor(
        specialty=f"rq13a{suffix}-synthetic",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
    )
    pg_session.add(doctor)
    pg_session.commit()
    pg_session.refresh(doctor)

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag=tag,
        active=True,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=15,
    )
    pg_session.add(queue)
    pg_session.commit()
    pg_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_name=f"RQ13A{suffix} SYNTHETIC PATIENT",
        status="waiting",
        source="desk",
        queue_time=datetime.now(),
    )
    pg_session.add(entry)
    pg_session.commit()
    pg_session.refresh(entry)

    return {"tag": tag, "queue_id": queue.id, "entry_id": entry.id}


def _seed_active_public_address_for_department(
    pg_session, dept_key: str, suffix: str
) -> dict[str, int]:
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress
    from app.models.queue_profile import QueueProfile

    profile = pg_session.query(QueueProfile).filter_by(key=dept_key).one()
    address = QueueDirectionPublicAddress(
        queue_profile_id=profile.id,
        public_code=f"r13{suffix}".ljust(12, "x")[:12],
    )
    pg_session.add(address)
    pg_session.commit()
    pg_session.refresh(address)
    return {"profile_id": profile.id, "address_id": address.id}


def test_department_deactivation_hides_linked_profiles_and_qr(
    pg_client, pg_session, pg_admin_user
):
    """D-06: department deactivation blocks new records at the tab/QR
    layer (both surfaces are driven by QueueProfile.is_active) while the
    queues/entries themselves are left untouched."""
    headers = _dep_headers(pg_admin_user)
    dept = _create_department(pg_client, headers, "hide")
    dept_key = dept["key"]

    # A manually linked second profile with its own title.
    from app.models.queue_profile import QueueProfile

    sub = QueueProfile(
        key="rq13ahide-sub",
        title="Custom sub tab",
        queue_tags=["rq13ahide-sub-tag"],
        department_key=dept_key,
        display_order=50,
        is_active=True,
        show_on_qr_page=True,
    )
    pg_session.add(sub)
    pg_session.commit()

    linked = _linked_profiles(pg_session, dept_key)
    assert {p.key for p in linked} == {dept_key, "rq13ahide-sub"}
    assert all(p.is_active for p in linked)
    raw_tabs = _tab_keys_debug(pg_client, headers)
    assert dept_key in _tab_keys(pg_client, headers), raw_tabs.text[:800]
    assert dept_key in _public_keys(pg_client)

    resp = pg_client.post(
        f"/api/v1/admin/departments/{dept['id']}/toggle", headers=headers
    )
    assert resp.status_code == 200, resp.text

    pg_session.expire_all()
    linked = _linked_profiles(pg_session, dept_key)
    assert all(
        not p.is_active for p in linked
    ), "deactivation must hide every linked profile"
    assert dept_key not in _tab_keys(pg_client, headers)
    assert dept_key not in _public_keys(pg_client)


def test_department_reactivation_restores_only_own_profile(
    pg_client, pg_session, pg_admin_user
):
    """D-06 + D-02 coherence: reactivation returns the department's own
    1:1 tab; independently archived profiles are NOT resurrected — the
    archive decision made through the profile endpoint (RQ-12.b) stays
    in force (predictable un-archive)."""
    headers = _dep_headers(pg_admin_user)
    dept = _create_department(pg_client, headers, "restore")
    dept_key = dept["key"]

    from app.models.queue_profile import QueueProfile

    sub = QueueProfile(
        key="rq13arestore-sub",
        title="Archived before deactivation",
        queue_tags=["rq13arestore-sub-tag"],
        department_key=dept_key,
        display_order=51,
        is_active=True,
        show_on_qr_page=True,
    )
    pg_session.add(sub)
    pg_session.commit()

    # Admin archives the sub-profile through the profile endpoint first
    # (the RQ-12.b archive transition, is_active=False).
    resp = pg_client.put(
        "/api/v1/queues/profiles/rq13arestore-sub",
        headers=_dep_headers(pg_admin_user),
        json={"is_active": False},
    )
    assert resp.status_code == 200, resp.text

    # Deactivate the department, then reactivate it.
    resp = pg_client.post(
        f"/api/v1/admin/departments/{dept['id']}/toggle", headers=headers
    )
    assert resp.status_code == 200, resp.text

    from app.models.queue_profile import QueueProfile as _QP

    pg_session.expire_all()
    own_mid = pg_session.query(_QP).filter(_QP.key == dept_key).first()
    sub_mid = pg_session.query(_QP).filter(_QP.key == "rq13arestore-sub").first()
    assert own_mid.is_active is False, "deactivation must hide own profile"
    assert sub_mid.is_active is False

    resp = pg_client.post(
        f"/api/v1/admin/departments/{dept['id']}/toggle", headers=headers
    )
    assert resp.status_code == 200, resp.text

    pg_session.expire_all()
    own = pg_session.query(QueueProfile).filter(QueueProfile.key == dept_key).first()
    sub_row = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == "rq13arestore-sub")
        .first()
    )
    assert own.is_active is True, "1:1 profile must be restored"
    assert sub_row.is_active is False, "manual archive must not resurrect"


def test_department_rename_syncs_own_profile_titles_only(
    pg_client, pg_session, pg_admin_user
):
    """F-12: renaming a department must not leave diverging titles on the
    department-owned profile. Manually linked profiles keep their own
    titles, and display_order stays an independent axis (F-19/RQ-23)."""
    headers = _dep_headers(pg_admin_user)
    dept = _create_department(pg_client, headers, "ren", display_order=7)
    dept_key = dept["key"]

    from app.models.queue_profile import QueueProfile

    sub = QueueProfile(
        key="rq13aren-sub",
        title="Custom sub tab",
        queue_tags=["rq13aren-sub-tag"],
        department_key=dept_key,
        display_order=52,
        is_active=True,
        show_on_qr_page=True,
    )
    pg_session.add(sub)
    pg_session.commit()

    resp = pg_client.put(
        f"/api/v1/admin/departments/{dept['id']}",
        headers=headers,
        json={"name_ru": "Новое название", "display_order": 2},
    )
    assert resp.status_code == 200, resp.text

    from app.models.department import Department

    pg_session.expire_all()
    own = pg_session.query(QueueProfile).filter(QueueProfile.key == dept_key).first()
    sub_row = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == "rq13aren-sub")
        .first()
    )
    dept_row = pg_session.query(Department).filter(Department.id == dept["id"]).first()
    assert dept_row.name_ru == "Новое название"
    assert own.title == "Новое название", "1:1 title must follow rename"
    assert own.title_ru == "Новое название"
    assert sub_row.title == "Custom sub tab", "sub-profile title untouched"
    assert own.display_order == 7, "display_order is an independent axis"


def test_department_delete_blocked_when_queue_history_exists(
    pg_client, pg_session, pg_admin_user
):
    """S-11/D-02: a department whose linked profile still owns queues
    (even historical) and waiting entries cannot be hard-deleted —
    patients must not disappear. The department row and all profile
    data survive; the response explains the impact."""
    headers = _dep_headers(pg_admin_user)
    dept = _create_department(pg_client, headers, "del")
    dept_key = dept["key"]
    seeded = _seed_waiting_entry_for_department(pg_session, dept_key, "del")

    resp = pg_client.delete(f"/api/v1/admin/departments/{dept['id']}", headers=headers)
    assert resp.status_code == 409, resp.text
    payload = resp.json()
    detail = json.dumps(payload, ensure_ascii=False)
    assert "waiting" in detail or "ожида" in detail

    from app.models.department import Department
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.queue_profile import QueueProfile

    pg_session.expire_all()
    assert (
        pg_session.query(Department).filter(Department.id == dept["id"]).first()
        is not None
    ), "department must survive a blocked delete"
    assert (
        pg_session.query(QueueProfile).filter(QueueProfile.key == dept_key).first()
        is not None
    ), "linked profile must survive a blocked delete"
    entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == seeded["entry_id"])
        .first()
    )
    assert entry is not None and entry.status == "waiting"
    assert (
        pg_session.query(DailyQueue).filter(DailyQueue.id == seeded["queue_id"]).first()
        is not None
    )


def test_department_delete_without_queue_history_keeps_cascade(
    pg_client, pg_session, pg_admin_user
):
    """Existing cascade behavior is preserved for a department with no
    queue history: profile/queue settings/reg settings are cleaned as
    before (RQ-22 PR-22 contract)."""
    headers = _dep_headers(pg_admin_user)
    dept = _create_department(pg_client, headers, "gone")
    dept_key = dept["key"]

    from app.models.queue_profile import QueueProfile

    assert (
        pg_session.query(QueueProfile).filter(QueueProfile.key == dept_key).first()
        is not None
    )

    resp = pg_client.delete(f"/api/v1/admin/departments/{dept['id']}", headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["cascade"]["queue_profile"] is True

    pg_session.expire_all()
    assert (
        pg_session.query(QueueProfile).filter(QueueProfile.key == dept_key).first()
        is None
    )


def test_department_delete_blocked_when_profile_has_active_public_address(
    pg_client, pg_session, pg_admin_user
):
    """The single department delete preserves address-only profile links."""
    from app.models.department import Department
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress
    from app.models.queue_profile import QueueProfile

    headers = _dep_headers(pg_admin_user)
    dept = _create_department(pg_client, headers, "addr")
    seeded = _seed_active_public_address_for_department(
        pg_session, dept["key"], "single"
    )

    response = pg_client.delete(
        f"/api/v1/admin/departments/{dept['id']}", headers=headers
    )
    assert response.status_code == 409, response.text
    profiles = response.json()["detail"]["profiles"]
    blocked = next(row for row in profiles if row["profile_key"] == dept["key"])
    assert blocked["active_public_addresses"] == 1

    pg_session.expire_all()
    assert pg_session.query(Department).filter_by(id=dept["id"]).one()
    assert pg_session.query(QueueProfile).filter_by(key=dept["key"]).one()
    address = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter_by(id=seeded["address_id"])
        .one()
    )
    assert address.queue_profile_id == seeded["profile_id"]
    assert address.retired_at is None


def test_department_bulk_delete_blocked_when_profile_has_active_public_address(
    pg_client, pg_session, pg_admin_user
):
    """Bulk delete applies the same address guard without partial cleanup."""
    from app.models.department import Department
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress
    from app.models.queue_profile import QueueProfile

    headers = _dep_headers(pg_admin_user)
    blocked = _create_department(pg_client, headers, "addrbulk_a")
    clean = _create_department(pg_client, headers, "addrbulk_b")
    seeded = _seed_active_public_address_for_department(
        pg_session, blocked["key"], "bulk"
    )

    response = pg_client.request(
        "DELETE",
        "/api/v1/admin/departments/bulk-delete",
        headers=headers,
        json={"ids": [blocked["id"], clean["id"]]},
    )
    assert response.status_code == 409, response.text
    details = response.json()["detail"]["blocked"]
    blocked_row = next(row for row in details if row["department_id"] == blocked["id"])
    profile_impact = next(
        row for row in blocked_row["profiles"] if row["profile_key"] == blocked["key"]
    )
    assert profile_impact["active_public_addresses"] == 1

    pg_session.expire_all()
    for department in (blocked, clean):
        assert pg_session.query(Department).filter_by(id=department["id"]).one()
    assert pg_session.query(QueueProfile).filter_by(key=blocked["key"]).one()
    address = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter_by(id=seeded["address_id"])
        .one()
    )
    assert address.queue_profile_id == seeded["profile_id"]
    assert address.retired_at is None


def test_bulk_deactivation_follows_hide_contract(pg_client, pg_session, pg_admin_user):
    """PR-18 bulk-activate must follow the same D-06 contract as the
    single-department toggle (one contract, not two behaviors)."""
    headers = _dep_headers(pg_admin_user)
    d1 = _create_department(pg_client, headers, "b1")
    d2 = _create_department(pg_client, headers, "b2")

    resp = pg_client.patch(
        "/api/v1/admin/departments/bulk-activate",
        headers=headers,
        json={"ids": [d1["id"], d2["id"]], "active": False},
    )
    assert resp.status_code == 200, resp.text

    pg_session.expire_all()
    for dept_key in (d1["key"], d2["key"]):
        linked = _linked_profiles(pg_session, dept_key)
        assert linked, "1:1 profile must exist"
        assert all(
            not p.is_active for p in linked
        ), f"bulk deactivation must hide {dept_key}"


# ---------------------------------------------------------------------------
# RQ-13 UI-slice (S-11 browser, D-06): bulk-delete guard parity. The single
# DELETE endpoint blocks departments whose linked profiles still own
# queues/entries (RQ-13.a), but the PR-18 bulk-delete loop hard-deleted via
# raw db.delete() with NO guard and NO 1:1 profile cleanup — a user-reachable
# S-11 violation surfaced by DepartmentManagement.tsx ("ожидающий пациент не
# исчезает"). Contract: same significant-link bar as the single endpoint,
# live recompute, all-or-nothing (no partial bulk delete), and cascade
# parity (1:1 profile + settings cleaned exactly like the single path).
# ---------------------------------------------------------------------------


def test_department_bulk_delete_blocked_when_queue_history_exists(
    pg_client, pg_session, pg_admin_user
):
    """Bulk delete with one blocked department must fail CLOSED with 409
    and leave EVERY department (including the clean ones) untouched."""
    headers = _dep_headers(pg_admin_user)
    blocked = _create_department(pg_client, headers, "bulk_a")
    clean = _create_department(pg_client, headers, "bulk_b")
    seeded = _seed_waiting_entry_for_department(pg_session, blocked["key"], "bulk_a")

    resp = pg_client.request(
        "DELETE",
        "/api/v1/admin/departments/bulk-delete",
        headers=headers,
        json={"ids": [blocked["id"], clean["id"]]},
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json().get("detail") or {}
    assert detail.get("error") == "department_has_queue_history", detail
    assert detail.get("waiting_patients", 0) >= 1
    blocked_rows = detail.get("blocked") or []
    assert any(
        row.get("department_id") == blocked["id"] for row in blocked_rows
    ), f"blocked report must name the offending department: {detail}"
    assert any(
        p.get("entries_waiting", 0) >= 1
        for row in blocked_rows
        for p in (row.get("profiles") or [])
    ), "impact must report waiting entries per profile"

    from app.models.department import Department
    from app.models.queue_profile import QueueProfile

    pg_session.expire_all()
    for dept in (blocked, clean):
        assert (
            pg_session.query(Department).filter(Department.id == dept["id"]).first()
            is not None
        ), "bulk delete is all-or-nothing: no partial deletion"
    assert (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == blocked["key"])
        .first()
        is not None
    ), "linked 1:1 profile must survive the blocked bulk delete"

    from app.models.online_queue import OnlineQueueEntry

    entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == seeded["entry_id"])
        .first()
    )
    assert entry is not None and entry.status == "waiting"


def test_department_bulk_delete_without_queue_history_cascades(
    pg_client, pg_session, pg_admin_user
):
    """Clean departments delete in bulk with the SAME cascade as the
    single endpoint: the 1:1 profile is removed, not orphaned."""
    headers = _dep_headers(pg_admin_user)
    d1 = _create_department(pg_client, headers, "bulk_c")
    d2 = _create_department(pg_client, headers, "bulk_d")

    from app.models.queue_profile import QueueProfile

    resp = pg_client.request(
        "DELETE",
        "/api/v1/admin/departments/bulk-delete",
        headers=headers,
        json={"ids": [d1["id"], d2["id"]]},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload.get("deleted") == 2, payload

    pg_session.expire_all()
    for dept in (d1, d2):
        assert (
            pg_session.query(QueueProfile)
            .filter(QueueProfile.key == dept["key"])
            .first()
            is None
        ), f"1:1 profile for {dept['key']} must be cascade-deleted, not orphaned"


@pytest.mark.parametrize("mutation_path", ["single", "bulk"])
def test_user_reactivation_takes_owner_scope_before_doctor_row_lock(
    pg_engine, pg_admin_user, mutation_path
):
    """User reactivation waits on owner-config before locking Doctor rows.

    A tagged admission can hold the owner scope and then take Doctor FOR
    SHARE. Both the single-user and bulk lifecycle commands must wait on the
    advisory scope first; taking Doctor FOR UPDATE first deadlocks this order.
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    import sqlalchemy as sa
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import sessionmaker

    from app.crud.queue_owner_invariant import lock_profile_link_scopes
    from app.models.clinic import Doctor
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    application_name = f"aqs_reactivate_{suffix}"
    specialty = "cardiology"
    session_factory = sessionmaker(bind=pg_engine, future=True)

    with session_factory() as seed:
        user = User(
            username=f"aqs-reactivate-{suffix}",
            email=f"aqs-reactivate-{suffix}@example.test",
            full_name="Synthetic Queue Lifecycle",
            hashed_password="not-used-in-this-test",
            role="Doctor",
            is_active=False,
        )
        seed.add(user)
        seed.flush()
        doctor = Doctor(user_id=user.id, specialty=specialty, active=False)
        seed.add(doctor)
        seed.commit()
        user_id = user.id
        doctor_id = doctor.id

    join_session = session_factory()
    lock_profile_link_scopes(join_session, queue_tags=[specialty])
    holder_pid = join_session.execute(sa.text("SELECT pg_backend_pid()")).scalar_one()
    activation_started = threading.Event()

    def activate_owner():
        from app.schemas.user_management import (
            UserBulkActionRequest,
            UserUpdateRequest,
        )
        from app.services.user_mgmt import UserManagementService

        with session_factory() as worker:
            worker.execute(
                sa.text("SELECT set_config('application_name', :name, false)"),
                {"name": application_name},
            )
            activation_started.set()
            service = UserManagementService()
            if mutation_path == "single":
                return service.update_user(
                    worker,
                    user_id,
                    UserUpdateRequest(is_active=True),
                    pg_admin_user.id,
                )
            return service.bulk_action_users(
                worker,
                UserBulkActionRequest(user_ids=[user_id], action="activate"),
                pg_admin_user.id,
            )

    blocked_by_doctor_row = False
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(activate_owner)
        try:
            assert activation_started.wait(timeout=5)
            deadline = time.monotonic() + 10
            waiting_on_owner_scope = False
            observed_blockers: list[int] = []
            with session_factory() as observer:
                while time.monotonic() < deadline:
                    wait = observer.execute(
                        sa.text(
                            "SELECT pg_blocking_pids(pid) "
                            "FROM pg_stat_activity "
                            "WHERE application_name = :name "
                            "ORDER BY pid DESC LIMIT 1"
                        ),
                        {"name": application_name},
                    ).scalar()
                    observed_blockers = list(wait or [])
                    if holder_pid in observed_blockers:
                        waiting_on_owner_scope = True
                        break
                    if future.done():
                        break
                    time.sleep(0.02)
            assert waiting_on_owner_scope, (
                "reactivation should wait for owner-config before Doctor row locks; "
                f"blocking_pids={observed_blockers}, holder_pid={holder_pid}"
            )

            join_session.execute(sa.text("SET LOCAL lock_timeout = '500ms'"))
            try:
                joined_doctor = (
                    join_session.query(Doctor)
                    .filter(Doctor.id == doctor_id)
                    .with_for_update(read=True)
                    .populate_existing()
                    .first()
                )
                assert joined_doctor is not None
            except OperationalError:
                blocked_by_doctor_row = True
        finally:
            join_session.rollback()
            join_session.close()
        result = future.result(timeout=15)

    assert blocked_by_doctor_row is False, (
        f"{mutation_path} activation locked Doctor before waiting for owner scope"
    )
    if mutation_path == "single":
        assert result[0] is True, result
    else:
        assert result[0] is True, result
        assert result[2]["processed_count"] == 1, result

    with session_factory() as verify:
        assert verify.get(User, user_id).is_active is True
        assert verify.get(Doctor, doctor_id).active is True


def test_profile_delete_rejects_binding_rebound_while_waiting(pg_engine, pg_admin_user):
    """DELETE compares an immutable candidate snapshot after scope wait."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    import sqlalchemy as sa
    from fastapi import HTTPException
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        delete_queue_profile,
    )
    from app.crud.queue_owner_invariant import lock_profile_binding_scopes
    from app.models.queue_profile import QueueProfile
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    key = f"aqs-delete-race-{suffix}"
    old_tag = f"aqs-old-{suffix}"
    new_tag = f"aqs-new-{suffix}"
    session_factory = sessionmaker(bind=pg_engine, future=True)
    with session_factory() as seed:
        seed.add(
            QueueProfile(
                key=key,
                title="Synthetic profile delete race",
                queue_tags=[old_tag],
                department_key=None,
                is_active=True,
                show_on_qr_page=False,
            )
        )
        seed.commit()

    writer_holds_scopes = threading.Event()
    allow_rebind_commit = threading.Event()
    delete_started = threading.Event()
    pids: dict[str, int] = {}

    def rebind_profile():
        with session_factory() as writer:
            pids["writer"] = writer.execute(
                sa.text("SELECT pg_backend_pid()")
            ).scalar_one()
            lock_profile_binding_scopes(
                writer, queue_tags=[old_tag, new_tag]
            )
            profile = (
                writer.query(QueueProfile)
                .filter(QueueProfile.key == key)
                .with_for_update()
                .populate_existing()
                .one()
            )
            profile.queue_tags = [new_tag]
            writer.flush()
            writer_holds_scopes.set()
            if not allow_rebind_commit.wait(timeout=10):
                raise TimeoutError("profile delete did not wait for rebind scope")
            writer.commit()

    def delete_profile() -> tuple[int, dict | None]:
        with session_factory() as deleter:
            pids["delete"] = deleter.execute(
                sa.text("SELECT pg_backend_pid()")
            ).scalar_one()
            admin = deleter.get(User, pg_admin_user.id)
            delete_started.set()
            try:
                delete_queue_profile(key, deleter, admin)
                return (200, None)
            except HTTPException as exc:
                return (exc.status_code, exc.detail)

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer_future = executor.submit(rebind_profile)
        delete_future = None
        try:
            assert writer_holds_scopes.wait(timeout=5)
            delete_future = executor.submit(delete_profile)
            assert delete_started.wait(timeout=5)
            deadline = time.monotonic() + 5
            delete_waited = False
            while time.monotonic() < deadline:
                if "delete" not in pids:
                    time.sleep(0.02)
                    continue
                with pg_engine.connect() as connection:
                    blockers = connection.execute(
                        sa.text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": pids["delete"]},
                    ).scalar_one()
                if pids["writer"] in blockers:
                    delete_waited = True
                    break
                if delete_future.done():
                    break
                time.sleep(0.02)
            assert delete_waited, "profile delete must wait on the old binding scope"
        finally:
            allow_rebind_commit.set()
        writer_future.result(timeout=10)
        assert delete_future is not None
        status_code, detail = delete_future.result(timeout=10)
        assert status_code == 409, detail
        assert detail["stale_fields"] == ["queue_tags"]

    with session_factory() as verify:
        profile = verify.query(QueueProfile).filter_by(key=key).one()
        assert profile.queue_tags == [new_tag]


@pytest.mark.parametrize("delete_path", ["single", "bulk"])
def test_department_delete_serializes_with_active_doctor_link_writer(
    pg_engine, pg_client, pg_admin_user, delete_path
):
    """A live doctor link committed during delete preflight is not orphaned."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace

    import sqlalchemy as sa
    from fastapi import HTTPException
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints.admin_departments._crud import (
        bulk_delete_departments,
        delete_department,
    )
    from app.crud import clinic as clinic_crud
    from app.crud.queue_owner_invariant import lock_profile_link_scopes
    from app.models.clinic import Doctor
    from app.models.department import Department
    from app.models.user import User
    from app.schemas.clinic import DoctorCreate

    suffix = uuid.uuid4().hex[:8]
    headers = _dep_headers(pg_admin_user)
    department = _create_department(pg_client, headers, f"race_{suffix}")
    clean_department = None
    if delete_path == "bulk":
        clean_department = _create_department(pg_client, headers, f"clean_{suffix}")
    session_factory = sessionmaker(bind=pg_engine, future=True)
    scope_held = threading.Event()
    allow_link_commit = threading.Event()
    delete_started = threading.Event()
    pids: dict[str, int] = {}

    def create_linked_doctor():
        with session_factory() as writer:
            pids["writer"] = writer.execute(
                sa.text("SELECT pg_backend_pid()")
            ).scalar_one()
            lock_profile_link_scopes(
                writer,
                queue_tags=[department["key"]],
                department_keys=[department["key"]],
            )
            scope_held.set()
            if not allow_link_commit.wait(timeout=10):
                raise TimeoutError("department delete did not wait for link scope")
            doctor = clinic_crud.create_doctor(
                writer,
                DoctorCreate(specialty=department["key"], active=True),
            )
            return doctor.id

    def delete_department_command():
        with session_factory() as deleter:
            pids["delete"] = deleter.execute(
                sa.text("SELECT pg_backend_pid()")
            ).scalar_one()
            admin = deleter.get(User, pg_admin_user.id)
            delete_started.set()
            try:
                if delete_path == "single":
                    delete_department(department["id"], deleter, admin)
                else:
                    ids = [department["id"], clean_department["id"]]
                    bulk_delete_departments(SimpleNamespace(ids=ids), deleter, admin)
                return (200, None)
            except HTTPException as exc:
                return (exc.status_code, exc.detail)

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer_future = executor.submit(create_linked_doctor)
        delete_future = None
        try:
            assert scope_held.wait(timeout=5)
            delete_future = executor.submit(delete_department_command)
            assert delete_started.wait(timeout=5)
            deadline = time.monotonic() + 5
            delete_waited = False
            while time.monotonic() < deadline:
                if "delete" not in pids:
                    time.sleep(0.02)
                    continue
                with pg_engine.connect() as connection:
                    blockers = connection.execute(
                        sa.text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": pids["delete"]},
                    ).scalar_one()
                if pids["writer"] in blockers:
                    delete_waited = True
                    break
                if delete_future.done():
                    break
                time.sleep(0.02)
            assert delete_waited, (
                "department deletion must acquire owner-config scopes before counts"
            )
        finally:
            allow_link_commit.set()
        doctor_id = writer_future.result(timeout=10)
        assert delete_future is not None
        status_code, detail = delete_future.result(timeout=10)
        assert status_code == 409, detail
        if delete_path == "bulk":
            blocked_profiles = [
                profile
                for blocked in detail["blocked"]
                for profile in blocked["profiles"]
            ]
        else:
            blocked_profiles = detail["profiles"]
        linked = next(
            profile
            for profile in blocked_profiles
            if profile["profile_key"] == department["key"]
        )
        assert linked["active_doctors"] == 1

    with session_factory() as verify:
        assert verify.get(Department, department["id"]) is not None
        assert verify.get(Doctor, doctor_id).active is True
        if clean_department:
            assert verify.get(Department, clean_department["id"]) is not None


def test_doctor_update_and_tagged_graphql_join_follow_owner_config_lock_order(pg_engine):
    """A tagged GraphQL admission holds owner-config before Doctor FOR SHARE.

    A concurrent specialty edit must wait for that config lock before it
    acquires Doctor FOR UPDATE, allowing the join to finish without a
    PostgreSQL deadlock.
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date

    from sqlalchemy import text

    from app.crud import clinic as clinic_crud
    from app.crud.queue_resource_routing import lock_queue_tag_claim_scope
    from app.models.clinic import Doctor
    from app.schemas.clinic import DoctorUpdate

    session_factory = sessionmaker(bind=pg_engine, future=True)
    suffix = uuid.uuid4().hex[:8]
    old_tag = f"rq12b-doctor-lock-{suffix}"
    new_tag = f"rq12b-doctor-next-{suffix}"
    doctor_id = None

    with session_factory() as seed:
        doctor = Doctor(specialty=old_tag, active=True)
        seed.add(doctor)
        seed.commit()
        doctor_id = doctor.id

    join_session = session_factory()
    lock_queue_tag_claim_scope(join_session, old_tag, date.today())
    holder_pid = join_session.execute(text("SELECT pg_backend_pid()")).scalar_one()

    application_name = f"t10_doc_lock_{suffix}"
    started = threading.Event()

    def update_specialty():
        with session_factory() as worker:
            worker.execute(
                text("SELECT set_config('application_name', :name, false)"),
                {"name": application_name},
            )
            started.set()
            updated = clinic_crud.update_doctor(
                worker, doctor_id, DoctorUpdate(specialty=new_tag)
            )
            return updated.specialty

    blocked_by_row_lock = False
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(update_specialty)
        try:
            assert started.wait(timeout=5), "doctor update worker did not start"
            deadline = time.monotonic() + 10
            observed_advisory_wait = False
            observed_blockers: list[int] = []
            with session_factory() as observer:
                while time.monotonic() < deadline:
                    wait = observer.execute(
                        text(
                            "SELECT pg_blocking_pids(pid) "
                            "FROM pg_stat_activity "
                            "WHERE application_name = :name "
                            "ORDER BY pid DESC LIMIT 1"
                        ),
                        {"name": application_name},
                    ).scalar()
                    observed_blockers = list(wait or [])
                    if holder_pid in observed_blockers:
                        observed_advisory_wait = True
                        break
                    if future.done():
                        break
                    time.sleep(0.02)
            assert observed_advisory_wait, (
                "doctor update should wait on the tagged join's owner-config "
                "advisory lock before taking the Doctor row lock; "
                f"blocking_pids={observed_blockers}, holder_pid={holder_pid}"
            )

            join_session.execute(text("SET LOCAL lock_timeout = '1s'"))
            try:
                selected = (
                    join_session.query(Doctor)
                    .filter(Doctor.id == doctor_id)
                    .with_for_update(read=True)
                    .populate_existing()
                    .first()
                )
                assert selected is not None
            except Exception as exc:
                from sqlalchemy.exc import OperationalError

                if isinstance(exc, OperationalError):
                    blocked_by_row_lock = True
                else:
                    raise
        finally:
            join_session.rollback()
        updated_specialty = future.result(timeout=10)

    assert not blocked_by_row_lock, (
        "tagged GraphQL join could not take Doctor FOR SHARE while the "
        "specialty update waited on the owner-config lock"
    )
    assert updated_specialty == new_tag


def test_doctor_update_rejects_stale_specialty_snapshot_without_writing(
    pg_engine, monkeypatch
):
    """A specialty changed after the unlocked candidate read returns 409."""
    from fastapi import HTTPException

    from app.crud import clinic as clinic_crud
    from app.models.clinic import Doctor
    from app.schemas.clinic import DoctorUpdate

    session_factory = sessionmaker(bind=pg_engine, future=True)
    suffix = uuid.uuid4().hex[:8]
    old_tag = f"rq12b-doctor-stale-{suffix}"
    competing_tag = f"rq12b-doctor-winner-{suffix}"
    requested_tag = f"rq12b-doctor-loser-{suffix}"

    with session_factory() as seed:
        doctor = Doctor(specialty=old_tag, active=True)
        seed.add(doctor)
        seed.commit()
        doctor_id = doctor.id

    def concurrent_rebind(_db, *, queue_tags, department_keys=()):
        with session_factory() as competing:
            row = competing.query(Doctor).filter(Doctor.id == doctor_id).one()
            row.specialty = competing_tag
            competing.commit()

    monkeypatch.setattr(clinic_crud, "lock_profile_link_scopes", concurrent_rebind)
    with session_factory() as request:
        with pytest.raises(HTTPException) as conflict:
            clinic_crud.update_doctor(
                request, doctor_id, DoctorUpdate(specialty=requested_tag)
            )

    assert conflict.value.status_code == 409
    assert conflict.value.detail["reason"] == "profile_binding_changed"
    assert conflict.value.detail["stale_fields"] == ["specialty"]
    with session_factory() as check:
        stored = check.query(Doctor).filter(Doctor.id == doctor_id).one()
        assert stored.specialty == competing_tag


def test_department_delete_blocked_when_active_doctor_mapping_exists(
    pg_client, pg_session, pg_admin_user
):
    """A live Doctor tag mapping keeps a department profile from cascading."""
    from app.models.clinic import Doctor
    from app.models.department import Department
    from app.models.queue_profile import QueueProfile

    headers = _dep_headers(pg_admin_user)
    dept = _create_department(pg_client, headers, "active_doc_map")
    profile = pg_session.query(QueueProfile).filter_by(key=dept["key"]).one()
    doctor = Doctor(specialty=dept["key"], active=True)
    pg_session.add(doctor)
    pg_session.commit()
    doctor_id = doctor.id

    response = pg_client.delete(
        f"/api/v1/admin/departments/{dept['id']}", headers=headers
    )
    assert response.status_code == 409, response.text
    blocked = next(
        row
        for row in response.json()["detail"]["profiles"]
        if row["profile_key"] == dept["key"]
    )
    assert blocked["active_doctors"] == 1
    assert blocked["active_queue_resources"] == 0

    pg_session.expire_all()
    assert pg_session.query(Department).filter_by(id=dept["id"]).one()
    assert pg_session.query(QueueProfile).filter_by(id=profile.id).one()
    assert pg_session.query(Doctor).filter_by(id=doctor_id).one().active is True


def test_department_bulk_delete_blocked_when_active_resource_mapping_exists(
    pg_client, pg_session, pg_admin_user
):
    """Bulk deletion preserves a live QueueResource and all unselected rows."""
    from app.models.department import Department
    from app.models.online_queue import QueueResource
    from app.models.queue_profile import QueueProfile

    headers = _dep_headers(pg_admin_user)
    blocked = _create_department(pg_client, headers, "active_res_map")
    clean = _create_department(pg_client, headers, "active_res_clean")
    profile = pg_session.query(QueueProfile).filter_by(key=blocked["key"]).one()
    resource = QueueResource(
        code=f"{blocked['key']}-res",
        queue_tag=blocked["key"],
        display_name="Synthetic active resource mapping",
        active=True,
    )
    pg_session.add(resource)
    pg_session.commit()
    resource_id = resource.id

    response = pg_client.request(
        "DELETE",
        "/api/v1/admin/departments/bulk-delete",
        headers=headers,
        json={"ids": [blocked["id"], clean["id"]]},
    )
    assert response.status_code == 409, response.text
    blocked_department = next(
        row
        for row in response.json()["detail"]["blocked"]
        if row["department_id"] == blocked["id"]
    )
    impact = next(
        row
        for row in blocked_department["profiles"]
        if row["profile_key"] == blocked["key"]
    )
    assert impact["active_queue_resources"] == 1
    assert impact["active_doctors"] == 0

    pg_session.expire_all()
    assert pg_session.query(Department).filter_by(id=blocked["id"]).one()
    assert pg_session.query(Department).filter_by(id=clean["id"]).one()
    assert pg_session.query(QueueProfile).filter_by(id=profile.id).one()
    assert pg_session.query(QueueResource).filter_by(id=resource_id).one().active is True
