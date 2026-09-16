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
- GET /queues/profiles/{key}/impact-preview — server-side link counts
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
from pathlib import Path
from typing import Any

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
        if (u.host or "") in {"localhost", "127.0.0.1", "::1"}:
            urls.append(
                f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}/postgres"
            )
        elif not u.host and (u.query.get("host") or "").startswith(
            ("/", "./")
        ):
            # Unix-socket DSN (userspace pgserver holder): the socket dir
            # travels in the query string; still localhost-only by
            # construction, so safe for scratch provisioning.
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


def _public_profile_keys(pg_client) -> set[str]:
    response = pg_client.get("/api/v1/queues/profiles/public")
    assert response.status_code == 200, response.text
    return {
        s["specialty"] for s in response.json().get("specialists", [])
    }


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

    existing = pg_session.query(QueueProfile).filter(
        QueueProfile.key == key
    ).first()
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
    staff_keys = {
        p["key"] for p in staff_list.json().get("profiles", [])
    }
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
    assert "RQ12B" in today.text, (
        "waiting patient must stay visible to staff after archive"
    )

    restored = _put_profile(
        pg_client, pg_admin_user, world["key"], {"is_active": True}
    )
    assert restored.status_code == 200, restored.text
    assert world["key"] in _public_profile_keys(pg_client)

    profile = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == world["key"])
        .first()
    )
    assert profile is not None and profile.is_active is True


def test_stale_preview_does_not_authorize_delete(
    pg_client, pg_session, pg_admin_user
):
    """RQ-12.b (D-02, S-10): preview said 'can_hard_delete', then the
    world changed (a service took the profile's tag) — the delete must
    re-verify links at execution time and refuse (409). A stale preview
    never authorizes destruction."""
    from app.models.queue_profile import QueueProfile

    tag = "rq12b-stale-tag"
    key = "rq12b-stale-profile"

    existing = pg_session.query(QueueProfile).filter(
        QueueProfile.key == key
    ).first()
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


def test_delete_unused_profile_succeeds(
    pg_client, pg_session, pg_admin_user
):
    """RQ-12.b (D-02): hard delete is still available for a profile with
    PROVEN absence of significant links — no services, no queues, no
    entries; exclusive tags with no service rows are no obstacle."""
    from app.models.queue_profile import QueueProfile

    key = "rq12b-unused-profile"
    tag = "rq12b-unused-tag"

    existing = pg_session.query(QueueProfile).filter(
        QueueProfile.key == key
    ).first()
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

    gone = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == key)
        .first()
    )
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
    resp = pg_client.post(
        "/api/v1/admin/departments", headers=headers, json=payload
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


def _linked_profiles(pg_session, dept_key: str) -> list:
    from app.models.queue_profile import QueueProfile

    return (
        pg_session.query(QueueProfile)
        .filter(
            (QueueProfile.department_key == dept_key)
            | (QueueProfile.key == dept_key)
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


def _seed_waiting_entry_for_department(
    pg_session, dept_key: str, suffix: str
) -> dict:
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
    sub_mid = (
        pg_session.query(_QP)
        .filter(_QP.key == "rq13arestore-sub")
        .first()
    )
    assert own_mid.is_active is False, "deactivation must hide own profile"
    assert sub_mid.is_active is False

    resp = pg_client.post(
        f"/api/v1/admin/departments/{dept['id']}/toggle", headers=headers
    )
    assert resp.status_code == 200, resp.text

    pg_session.expire_all()
    own = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == dept_key)
        .first()
    )
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
    dept = _create_department(
        pg_client, headers, "ren", display_order=7
    )
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
    own = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == dept_key)
        .first()
    )
    sub_row = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == "rq13aren-sub")
        .first()
    )
    dept_row = pg_session.query(Department).filter(
        Department.id == dept["id"]
    ).first()
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

    resp = pg_client.delete(
        f"/api/v1/admin/departments/{dept['id']}", headers=headers
    )
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
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == dept_key)
        .first()
        is not None
    ), "linked profile must survive a blocked delete"
    entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == seeded["entry_id"])
        .first()
    )
    assert entry is not None and entry.status == "waiting"
    assert (
        pg_session.query(DailyQueue)
        .filter(DailyQueue.id == seeded["queue_id"])
        .first()
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
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == dept_key)
        .first()
        is not None
    )

    resp = pg_client.delete(
        f"/api/v1/admin/departments/{dept['id']}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["cascade"]["queue_profile"] is True

    pg_session.expire_all()
    assert (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == dept_key)
        .first()
        is None
    )


def test_bulk_deactivation_follows_hide_contract(
    pg_client, pg_session, pg_admin_user
):
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
