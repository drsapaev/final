"""
RQ-26.b — CSV export contract verified against the new target/lifecycle
contracts (plan §RQ-26.b: «проверить/дополнить экспорт после принятых
новых контрактов target/lifecycle»).

VERIFICATION slice: the application runtime is consumed, never modified.
The frontend CSV round-trip helpers (frontend/src/components/admin/
queueProfilesCsv.ts, RQ-26.a #3195) build payloads for the lifecycle
endpoints POST/PUT ``/api/v1/queues/profiles`` and read the admin list
GET ``/api/v1/queues/profiles?active_only=false``. This module pins the
API-side semantics those helpers rely on, now that RQ-12.b (D-02 archive
lifecycle) and RQ-16.b/c/d (direction target + public-address registry,
E-055) have landed:

1. Export completeness (lifecycle): ``GET ?active_only=false`` returns
   archived profiles too — the admin CSV export (the manager loads the
   list with ``active_only=false``) can never silently drop them; the
   default ``active_only=true`` view hides them.
2. CSV source shape: every admin-list profile dict carries exactly the
   contract fields the CSV helper consumes (plus the derived
   ``settings_key``) and never leaks registry internals (``public_code``
   stays in the registry table, never in the profile surfaces).
3. Archive via the CSV payload shape (``PUT is_active=false``) preserves
   the provisioned public address (E-055 §5: archive keeps the row; the
   SAME code revives when the same profile is reactivated); an archived
   direction refuses the anonymous start-session and entry-methods
   surfaces (S-15 anonymous refusal) — and reactivation restores the
   SAME address, never a regenerated code.
4. E-055 §3/§6 (server-SSOT address): a hand-edited CSV cannot push a
   ``public_code`` through the profile PUT — the unknown field is
   dropped at the schema boundary and the registry row is untouched.
5. The partial-update contract (``exclude_unset=True``) behind the CSV
   "old format never wipes fields" guarantee: a PUT carrying only
   ``is_active`` keeps every other stored field stable.
6. CSV-driven create round-trip: a POST payload built from CSV cells
   survives storage with every contract field intact (``display_order``
   under the ``order`` alias, omitted optional cells → NULL).

No migrations: the registry table (0068) and the Alembic chain are
consumed, never modified. Disposable PostgreSQL: the module provisions
its own scratch database (rq26b_check), runs ``alembic upgrade head``
and drops it at the end; skips (NOT_RUN, plan P0) when no disposable
PostgreSQL server is reachable. SQLite is never a substitute here.
SYNTHETIC data only (``rq26b-``/``RQ26B-`` markers, no PHI/PII).

Modeled on tests/integration/test_rq16d_public_direction_runtime.py and
test_rq24b_cross_panel_s21_pg.py (merged real-PG harness precedents).

Run::

    cd backend && RQ26B_PG_ADMIN_URL='postgresql://postgres:@/postgres?host=/path/to/sock' \\
        pytest tests/integration/test_rq26b_csv_lifecycle_contract_pg.py -q
"""

from __future__ import annotations

import os
import sys
from datetime import time
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq26b_check"

sys.path.insert(0, str(BACKEND_DIR))

pytestmark = pytest.mark.integration

PROFILES_PATH = "/api/v1/queues/profiles"
PROVISION_PATH = (
    "/api/v1/queue/admin/directions/{profile_key}/public-address/provision"
)
START_PATH = "/api/v1/queue/public/{public_code}/start-session"
METHODS_PATH = "/api/v1/queue/directions/{profile_key}/entry-methods"
REFUSAL_DETAIL = "Направление недоступно"

# The admin-list profile dict is the CSV export SOURCE contract
# (queueProfilesCsv.ts QueueProfileCsvSource). ``order`` is the API alias
# of the stored display_order; ``settings_key`` is the derived D-1
# clinic-settings segment. No registry field may leak here.
CSV_SOURCE_PROFILE_KEYS = {
    "key",
    "title",
    "title_ru",
    "queue_tags",
    "department_key",
    "icon",
    "color",
    "order",
    "is_active",
    "show_on_qr_page",
    "settings_key",
}


# ------------------------------------------------------------------
# disposable PostgreSQL harness (scratch DB + alembic head)
# ------------------------------------------------------------------


def _candidate_admin_urls() -> list[str]:
    """Plain-psycopg admin DSNs.

    ``DATABASE_URL`` in CI is a SQLAlchemy URL
    (``postgresql+psycopg://``); psycopg.connect rejects the driver
    suffix, so the scheme is normalized for the admin connection
    (RQ-24.b lesson: without the normalization the module would silently
    SKIP in CI).
    """
    urls: list[str] = []

    def _normalized(raw: str) -> str:
        return raw.replace("postgresql+psycopg://", "postgresql://", 1)

    explicit = os.getenv("RQ26B_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(_normalized(explicit))
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        urls.append(_normalized(env_url))
    return urls


def _dsn_parts(admin_url: str) -> dict:
    from urllib.parse import parse_qs, urlparse

    p = urlparse(admin_url)
    q = parse_qs(p.query)
    return {
        "sockdir": (q.get("host") or [None])[0],
        "user": p.username or "postgres",
        "password": p.password or "",
        "host": p.hostname or "localhost",
        "port": p.port or 5432,
    }


def _scratch_urls(admin_url: str) -> tuple[str, str]:
    parts = _dsn_parts(admin_url)
    if parts["sockdir"]:
        base_p = f"postgresql://{parts['user']}:{parts['password']}@/"
        base_s = f"postgresql+psycopg://{parts['user']}:{parts['password']}@/"
        return (
            f"{base_p}{SCRATCH_DB}?host={parts['sockdir']}",
            f"{base_s}{SCRATCH_DB}?host={parts['sockdir']}",
        )
    base = (
        f"postgresql://{parts['user']}:{parts['password']}"
        f"@{parts['host']}:{parts['port']}"
    )
    return (
        f"{base}/{SCRATCH_DB}",
        f"postgresql+psycopg://{parts['user']}:{parts['password']}"
        f"@{parts['host']}:{parts['port']}/{SCRATCH_DB}",
    )


@pytest.fixture(scope="module")
def pg_engine():
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
            f"disposable PostgreSQL unavailable — RQ-26.b PG verification NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
    import subprocess

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
        dialect = conn.execute(text("select version()")).scalar()
    assert version, "alembic_version must be present after upgrade"
    assert "PostgreSQL" in (dialect or ""), "RQ-26.b proof requires real PostgreSQL"

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


@pytest.fixture(autouse=True)
def _no_time_gate(monkeypatch):
    """Neutralize the 07:00 same-day online-booking window (rq16d/rq24b
    canon): the CSV lifecycle assertions are clock-independent, but the
    public start-session refuses same-day anonymous joins before the
    window (queue_svc._operations reads ONLINE_QUEUE_START_TIME off BOTH
    the service class and the mixin base), so a backend suite executing
    this module before 07:00 clinic-local time would fail
    test_csv_archive_payload_… deterministically (2026-09-26 CI: two
    Unified attempts died at 06:35/06:50 local on exactly that 400).
    Patching the window to midnight makes the refusal branch
    (``now.time() < time(0, 0)``) unreachable on any clock."""
    from app.services.queue_svc import QueueBusinessService
    from app.services.queue_svc._base import QueueBusinessServiceMixinBase

    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    monkeypatch.setattr(
        QueueBusinessServiceMixinBase, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )


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


def _get_or_create_user(session, username: str, role: str):
    """Idempotent synthetic user (the scratch DB persists across tests)."""
    from app.core.security import get_password_hash
    from app.models.user import User

    user = session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=f"RQ-26.b {username}",
        hashed_password=get_password_hash("rq26b-synthetic-pw"),
        role=role,
        is_active=True,
        is_superuser=role == "Admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _get_or_create_doctor(session, user_id: int, specialty: str):
    from app.models.clinic import Doctor

    doctor = (
        session.query(Doctor)
        .filter(Doctor.user_id == user_id, Doctor.specialty == specialty)
        .first()
    )
    if doctor:
        return doctor
    doctor = Doctor(user_id=user_id, specialty=specialty, cabinet="219", active=True)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _make_profile(session, key: str, tag: str, **kwargs):
    """Fresh synthetic profile; stale rows (and their tombstoned registry
    addresses) from earlier tests of this module are removed first."""
    from app.models.queue_profile import QueueProfile

    stale = session.query(QueueProfile).filter(QueueProfile.key == key).all()
    if stale:
        for profile in stale:
            session.delete(profile)
        session.commit()
    profile = QueueProfile(
        key=key,
        title=f"RQ-26.b {key}",
        title_ru=kwargs.pop("title_ru", f"RQ-26.b {key} (синтетик)"),
        queue_tags=[tag],
        display_order=kwargs.pop("display_order", 9),
        is_active=kwargs.pop("is_active", True),
        show_on_qr_page=kwargs.pop("show_on_qr_page", True),
        **kwargs,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def _auth_headers(user) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


@pytest.fixture
def csv_world(pg_session):
    """SYNTHETIC CSV-contract world: one active QR-visible profile with a
    doctor-eligible owner (for the address round-trip leg), one archived,
    one hidden, one bare. Idempotent across the module-scoped scratch DB."""
    from app.models.queue_profile import QueueProfile

    keys = [
        "rq26b-dir",
        "rq26b-archived",
        "rq26b-hidden",
        "rq26b-bare",
    ]
    stale = pg_session.query(QueueProfile).filter(QueueProfile.key.in_(keys)).all()
    if stale:
        for profile in stale:
            pg_session.delete(profile)
        pg_session.commit()

    direction = _make_profile(
        pg_session,
        "rq26b-dir",
        "rq26b-dir",
        department_key="rq26b-dep",
        icon="Heart",
        color="#E53E3E",
        display_order=4,
    )
    archived = _make_profile(
        pg_session, "rq26b-archived", "rq26b-archived", is_active=False
    )
    hidden = _make_profile(
        pg_session, "rq26b-hidden", "rq26b-hidden", show_on_qr_page=False
    )
    bare = _make_profile(pg_session, "rq26b-bare", "rq26b-bare")
    owner_user = _get_or_create_user(pg_session, "rq26b_doc_owner", "Doctor")
    owner_doctor = _get_or_create_doctor(pg_session, owner_user.id, "rq26b-dir")
    return {
        "direction": direction,
        "archived": archived,
        "hidden": hidden,
        "bare": bare,
        "owner_doctor": owner_doctor,
    }


@pytest.fixture
def pg_admin_user(pg_session):
    return _get_or_create_user(pg_session, "rq26b_admin", "Admin")


# ------------------------------------------------------------------
# 1. Export completeness (lifecycle): archived profiles are exportable
# ------------------------------------------------------------------


def test_admin_list_active_only_false_includes_archived(
    pg_client, pg_admin_user, csv_world
):
    """D-02 lifecycle: archived (is_active=False) profiles are NOT deleted —
    the admin CSV export surface (manager loads ?active_only=false) must see
    them, while the default active view hides them."""
    headers = _auth_headers(pg_admin_user)

    full = pg_client.get(PROFILES_PATH, params={"active_only": "false"}, headers=headers)
    assert full.status_code == 200, full.text
    keys_full = {p["key"] for p in full.json()["profiles"]}
    assert "rq26b-archived" in keys_full, (
        "archived profiles must stay exportable — a CSV export that silently "
        "drops them would resurrect them on re-import elsewhere"
    )
    assert "rq26b-dir" in keys_full

    active = pg_client.get(PROFILES_PATH, headers=headers)
    assert active.status_code == 200
    keys_active = {p["key"] for p in active.json()["profiles"]}
    assert "rq26b-archived" not in keys_active
    assert "rq26b-dir" in keys_active


def test_admin_list_profile_dict_matches_csv_source_contract(
    pg_client, pg_admin_user, csv_world
):
    """Every admin-list profile dict carries exactly the CSV source fields
    (plus the derived settings_key) — and never leaks registry internals:
    public_code stays in the registry table (E-055), never on profile
    surfaces the CSV reads."""
    headers = _auth_headers(pg_admin_user)
    response = pg_client.get(PROFILES_PATH, params={"active_only": "false"}, headers=headers)
    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert profiles, "synthetic world must be visible"

    by_key = {p["key"]: p for p in profiles}
    for key in ("rq26b-dir", "rq26b-archived", "rq26b-hidden", "rq26b-bare"):
        assert key in by_key, f"synthetic profile {key} missing from admin list"
        profile = by_key[key]
        assert set(profile.keys()) == CSV_SOURCE_PROFILE_KEYS, (
            f"{key}: admin-list dict drifted from the CSV source contract — "
            f"extra={set(profile.keys()) - CSV_SOURCE_PROFILE_KEYS}, "
            f"missing={CSV_SOURCE_PROFILE_KEYS - set(profile.keys())}"
        )

    # The archived flag round-trips through the source contract (D-02).
    assert by_key["rq26b-archived"]["is_active"] is False
    assert by_key["rq26b-dir"]["is_active"] is True
    assert by_key["rq26b-hidden"]["show_on_qr_page"] is False


# ------------------------------------------------------------------
# 3. CSV archive payload (PUT is_active=false) × public-address registry
# ------------------------------------------------------------------


def test_csv_archive_payload_preserves_address_and_reactivation_restores_it(
    pg_client, pg_admin_user, csv_world, pg_session
):
    """The exact CSV-import payload shape {key,title,is_active:false} archives
    the profile: the provisioned public address row stays active (E-055 §5),
    the anonymous surfaces refuse (S-15), and reactivating the SAME profile
    restores the SAME address — a CSV-driven archive/reactivate cycle can
    never regenerate or reassign codes."""
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress

    headers = _auth_headers(pg_admin_user)
    key = "rq26b-dir"

    provisioned = pg_client.post(
        PROVISION_PATH.replace("{profile_key}", key), headers=headers
    )
    assert provisioned.status_code == 200, provisioned.text
    code = provisioned.json()["public_code"]

    # CSV import payload for an archived row (empty optional cells → omit).
    archive_payload = {"key": key, "title": csv_world["direction"].title, "is_active": False}
    archived = pg_client.put(f"{PROFILES_PATH}/{key}", json=archive_payload, headers=headers)
    assert archived.status_code == 200, archived.text
    assert archived.json()["profile"]["is_active"] is False

    # The registry row survives the archive — active, same code, same profile.
    rows = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(QueueDirectionPublicAddress.public_code == code)
        .all()
    )
    assert len(rows) == 1, "exactly one registry row must exist for the code"
    assert rows[0].retired_at is None, "archive must NOT retire the address (E-055 §5)"
    assert rows[0].queue_profile_id == csv_world["direction"].id

    # S-15: archived direction refuses the anonymous surfaces.
    refused_start = pg_client.post(START_PATH.replace("{public_code}", code))
    assert refused_start.status_code == 404
    assert refused_start.json()["detail"] == REFUSAL_DETAIL
    refused_methods = pg_client.get(METHODS_PATH.replace("{profile_key}", key))
    assert refused_methods.status_code == 404
    assert refused_methods.json()["detail"] == REFUSAL_DETAIL

    # CSV import payload for reactivation (is_active=true).
    reactivate_payload = {"key": key, "title": csv_world["direction"].title, "is_active": True}
    reactivated = pg_client.put(
        f"{PROFILES_PATH}/{key}", json=reactivate_payload, headers=headers
    )
    assert reactivated.status_code == 200, reactivated.text

    # The SAME address revives — never a regenerated code (E-055 §5).
    methods = pg_client.get(METHODS_PATH.replace("{profile_key}", key))
    assert methods.status_code == 200, methods.text
    flags = {
        item["method"]: item["supported"]
        for item in methods.json()["entry_methods"]
    }
    assert flags["permanent_address"] is True, (
        "reactivation must restore the permanent-address entry method"
    )

    rows_after = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(QueueDirectionPublicAddress.queue_profile_id == csv_world["direction"].id)
        .all()
    )
    assert len(rows_after) == 1, "no second address row may appear"
    assert rows_after[0].public_code == code
    assert rows_after[0].retired_at is None

    # The anonymous start works again through the SAME address.
    started = pg_client.post(START_PATH.replace("{public_code}", code))
    assert started.status_code == 200, started.text
    assert started.json()["direction"]["public_code"] == code


# ------------------------------------------------------------------
# 4. E-055 boundary: a hand-edited CSV cannot push public_code
# ------------------------------------------------------------------


def test_put_drops_hand_edited_public_code(pg_client, pg_admin_user, csv_world, pg_session):
    """E-055 §3/§6: the address is server-SSOT (generated ONCE, never
    admin-typed). A hand-edited CSV file may carry a public_code column —
    the frontend parser warns unknown_column and the payload builder never
    forwards it; this test pins the LAST line of defense: the profile PUT
    drops the unknown field and the registry row stays untouched."""
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress

    headers = _auth_headers(pg_admin_user)
    key = "rq26b-dir"

    provisioned = pg_client.post(
        PROVISION_PATH.replace("{profile_key}", key), headers=headers
    )
    assert provisioned.status_code == 200, provisioned.text
    real_code = provisioned.json()["public_code"]

    forged = "aaaaaaaaaaaa"  # valid-looking 12-char code the attacker prefers
    assert forged != real_code
    response = pg_client.put(
        f"{PROFILES_PATH}/{key}",
        json={"key": key, "title": csv_world["direction"].title, "public_code": forged},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    row = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(QueueDirectionPublicAddress.queue_profile_id == csv_world["direction"].id)
        .first()
    )
    assert row is not None
    assert row.public_code == real_code, (
        "the registry code must be immutable through the profile PUT (E-055)"
    )
    body = response.json()["profile"]
    assert "public_code" not in body, "profile surfaces must not echo registry fields"


# ------------------------------------------------------------------
# 5. Partial-PUT keeps omitted fields (the old-format CSV guarantee)
# ------------------------------------------------------------------


def test_partial_put_keeps_omitted_fields(pg_client, pg_admin_user, csv_world):
    """The CSV helpers omit empty cells so the backend exclude_unset update
    keeps stored values — old-format files never wipe
    department_key/show_on_qr_page. Pinned server-side: a PUT carrying only
    is_active leaves every other stored field stable."""
    headers = _auth_headers(pg_admin_user)
    key = "rq26b-dir"

    before = pg_client.get(PROFILES_PATH, params={"active_only": "false"}, headers=headers)
    source = {p["key"]: p for p in before.json()["profiles"]}[key]

    response = pg_client.put(
        f"{PROFILES_PATH}/{key}",
        json={"key": key, "title": source["title"], "is_active": False},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    updated = response.json()["profile"]
    assert updated["is_active"] is False

    after = pg_client.get(PROFILES_PATH, params={"active_only": "false"}, headers=headers)
    target = {p["key"]: p for p in after.json()["profiles"]}[key]
    assert target["queue_tags"] == source["queue_tags"]
    assert target["department_key"] == source["department_key"]
    assert target["icon"] == source["icon"]
    assert target["color"] == source["color"]
    assert target["order"] == source["order"]
    assert target["show_on_qr_page"] == source["show_on_qr_page"]


# ------------------------------------------------------------------
# 6. CSV-driven create round-trips every contract field
# ------------------------------------------------------------------


def test_csv_create_payload_round_trips_all_contract_fields(
    pg_client, pg_admin_user, csv_world
):
    """A POST payload shaped like the CSV import (typed values, omitted
    empties) survives storage with every contract field intact; the list
    response exposes display_order under the `order` alias and NULL
    optional cells, exactly what the next CSV export will read."""
    headers = _auth_headers(pg_admin_user)

    payload = {
        "key": "rq26b_created",
        "title": "RQ-26.b created (синтетик)",
        "title_ru": "RQ-26.b созданный",
        "queue_tags": ["rq26b-created"],
        "department_key": "rq26b-dep",
        "icon": "Activity",
        "color": "#3182CE",
        "display_order": 7,
        "is_active": False,
        "show_on_qr_page": False,
    }
    created = pg_client.post(PROFILES_PATH, json=payload, headers=headers)
    assert created.status_code == 200, created.text
    assert created.json()["success"] is True
    body = created.json()["profile"]
    assert body["order"] == 7, "display_order must surface under the order alias"

    listing = pg_client.get(PROFILES_PATH, params={"active_only": "false"}, headers=headers)
    assert listing.status_code == 200
    stored = {p["key"]: p for p in listing.json()["profiles"]}["rq26b_created"]
    assert set(stored.keys()) == CSV_SOURCE_PROFILE_KEYS
    assert stored["title"] == payload["title"]
    assert stored["title_ru"] == payload["title_ru"]
    assert stored["queue_tags"] == payload["queue_tags"]
    assert stored["department_key"] == payload["department_key"]
    assert stored["icon"] == payload["icon"]
    assert stored["color"] == payload["color"]
    assert stored["order"] == payload["display_order"]
    assert stored["is_active"] is False
    assert stored["show_on_qr_page"] is False

    # Re-importing the round-tripped values is idempotent (the canonical
    # tag normalization must not drift non-dental tags).
    again = dict(payload)
    updated = pg_client.put(f"{PROFILES_PATH}/rq26b_created", json=again, headers=headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["profile"]["queue_tags"] == payload["queue_tags"]


def test_csv_create_refuses_keys_outside_backend_pattern(
    pg_client, pg_admin_user, csv_world
):
    """RQ-26.b verification finding, pinned as contract: the create schema
    enforces ^[a-z][a-z0-9_]*$ on the key — a hand-edited CSV with a
    foreign key style (hyphens, digits lead) gets a deterministic 422 BEFORE
    any state change, surfacing through the import failure counter. Every
    legitimately created profile satisfies the pattern, so real CSV exports
    always re-import (the round-trip test above uses a valid key)."""
    headers = _auth_headers(pg_admin_user)

    refused = pg_client.post(
        PROFILES_PATH,
        json={"key": "rq26b-invalid-key", "title": "RQ-26.b отказ (синтетик)"},
        headers=headers,
    )
    assert refused.status_code == 422, refused.text

    listing = pg_client.get(PROFILES_PATH, params={"active_only": "false"}, headers=headers)
    assert listing.status_code == 200
    assert all(
        p["key"] != "rq26b-invalid-key" for p in listing.json()["profiles"]
    ), "a refused key must leave no partial state behind"
