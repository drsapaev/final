"""
RQ-16.d — runtime of the permanent public direction address (D-03).

Owner decision 2026-09-17 (E-055 §8/§9, DECISION_PROPOSALS.md; start
command trace ``1a0af66ae094ba29``): the runtime shape is ONE canonical
anonymous resolve/start operation::

    public_code
    -> server-side direction resolution (registry -> QueueProfile)
    -> eligibility / visibility checks (the SAME contract as QR)
    -> anonymous rate limit
    -> short-lived session creation
    -> the EXISTING QueueJoin session flow (join/complete)

No second join mechanism is created: ``/queue/join/:token`` stays the
canonical session path and every join rule stays in the canonical
resolver (queue_svc). The slice adds:

1. ``POST /api/v1/queue/admin/directions/{profile_key}/public-address/
   provision`` (Admin-only) — generates the opaque public code ONCE per
   direction (E-055 §3: no backfill, no admin-typed slugs), idempotent
   (re-provision keeps the SAME address), collision-retry insert loop
   (E-055 §11), the ``clinic`` sentinel key refused.
2. ``POST /api/v1/queue/public/{public_code}/start-session``
   (anonymous, rate-limited) — resolve -> visibility (S-15 anonymous
   refusal for unknown/archived/hidden/deleted/retired) -> eligibility
   probe -> mint a direction-scoped short-lived QueueToken (the SAME
   5..15 min TTL bounds as every QR token, RQ-11; the reserved
   ``qdir:``-prefixed department marks the session scope — legacy
   tokens never carry the prefix) -> existing start_join_session.
   The join path REFUSES a direction-scoped session completing for any
   other specialist/direction (queue_svc binding check).
3. The RQ-16.b entry-methods flag ``permanent_address`` becomes
   dynamic per-direction (E-055 §8): True only when the direction has a
   provisioned active address AND the canonical eligibility probe
   passes. Unprovisioned directions keep reporting False (no backfill).

S-15 refusal matrix: unknown / archived / hidden / hard-deleted
(tombstone FK NULL) / retired — all refuse 404 with the SAME anonymous
detail, byte-identical (no existence leak).

No migrations: the registry table (0068) and the Alembic chain (single
head 0069) are consumed, never modified. Disposable PostgreSQL: the
module provisions its own scratch database (rq16d_check), runs
``alembic upgrade head`` and drops it at the end; skips (NOT_RUN, per
plan P0) when no disposable PostgreSQL server is reachable. SQLite is
never a substitute here. SYNTHETIC data only.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import time
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq16d_check"

sys.path.insert(0, str(BACKEND_DIR))

pytestmark = pytest.mark.integration

PROVISION_PATH = (
    "/api/v1/queue/admin/directions/{profile_key}/public-address/provision"
)
START_PATH = "/api/v1/queue/public/{public_code}/start-session"
METHODS_PATH = "/api/v1/queue/directions/{profile_key}/entry-methods"
REFUSAL_DETAIL = "Направление недоступно"
CODE_RE = re.compile(r"^[23456789abcdefghjkmnpqrstvwxyz]{12}$")


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("RQ16D_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        urls.append(env_url)
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
            f"disposable PostgreSQL unavailable — RQ-16.d PG acceptance NOT_RUN "
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
    assert "PostgreSQL" in (dialect or ""), "RQ-16.d proof requires real PostgreSQL"

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
        full_name=f"RQ-16.d {username}",
        hashed_password=get_password_hash("rq16d-synthetic-pw"),
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
    doctor = Doctor(user_id=user_id, specialty=specialty, cabinet="209", active=True)
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _make_profile(session, key: str, tag: str, **kwargs):
    """Fresh profile per test: stale rows (and their tombstoned registry
    addresses) from earlier tests of this module are removed first."""
    from app.models.queue_profile import QueueProfile

    stale = session.query(QueueProfile).filter(QueueProfile.key == key).all()
    if stale:
        for profile in stale:
            session.delete(profile)
        session.commit()
    profile = QueueProfile(
        key=key,
        title=f"RQ-16.d {key}",
        title_ru=kwargs.pop("title_ru", f"RQ-16.d {key} (синтетик)"),
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


@pytest.fixture
def direction_world(pg_session):
    """SYNTHETIC direction world: two doctor-backed visible directions
    (cardio, derma), one visible-unprovisioned (plain), one archived,
    one hidden. Idempotent across the module-scoped scratch DB."""
    from app.models.queue_profile import QueueProfile

    keys = [
        "rq16d-cardio",
        "rq16d-derma",
        "rq16d-plain",
        "rq16d-archived",
        "rq16d-hidden",
    ]
    stale = pg_session.query(QueueProfile).filter(QueueProfile.key.in_(keys)).all()
    if stale:
        for profile in stale:
            pg_session.delete(profile)
        pg_session.commit()

    cardio = _make_profile(pg_session, "rq16d-cardio", "rq16d-cardio")
    derma = _make_profile(pg_session, "rq16d-derma", "rq16d-derma")
    plain = _make_profile(pg_session, "rq16d-plain", "rq16d-plain")
    archived = _make_profile(
        pg_session, "rq16d-archived", "rq16d-archived", is_active=False
    )
    hidden = _make_profile(
        pg_session, "rq16d-hidden", "rq16d-hidden", show_on_qr_page=False
    )
    cardio_user = _get_or_create_user(pg_session, "rq16d_doc_cardio", "Doctor")
    cardio_doctor = _get_or_create_doctor(
        pg_session, cardio_user.id, "rq16d-cardio"
    )
    derma_user = _get_or_create_user(pg_session, "rq16d_doc_derma", "Doctor")
    derma_doctor = _get_or_create_doctor(pg_session, derma_user.id, "rq16d-derma")
    return {
        "cardio": cardio,
        "derma": derma,
        "plain": plain,
        "archived": archived,
        "hidden": hidden,
        "cardio_doctor": cardio_doctor,
        "derma_doctor": derma_doctor,
    }


@pytest.fixture
def pg_admin_user(pg_session):
    return _get_or_create_user(pg_session, "rq16d_admin", "Admin")


def _auth_headers(user) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _provision_url(key: str) -> str:
    return PROVISION_PATH.replace("{profile_key}", key)


def _start_url(code: str) -> str:
    return START_PATH.replace("{public_code}", code)


def _provision(client, headers, key: str):
    return client.post(_provision_url(key), headers=headers)


def _start(client, code: str):
    return client.post(_start_url(code))


def test_openapi_schema_contains_public_direction_runtime_contract(pg_client):
    schema = pg_client.get("/openapi.json")
    assert schema.status_code == 200
    spec = schema.json()
    provision_template = (
        "/api/v1/queue/admin/directions/{profile_key}/public-address/provision"
    )
    assert provision_template in spec["paths"], (
        "RQ-16.d provision route missing from OpenAPI"
    )
    start_template = "/api/v1/queue/public/{public_code}/start-session"
    assert start_template in spec["paths"], (
        "RQ-16.d public start route missing from OpenAPI"
    )
    start_op = spec["paths"][start_template]["post"]
    assert start_op.get("responses"), "start-session must declare responses"
    assert "404" in start_op["responses"], (
        "the anonymous refusal must be a declared response (S-15)"
    )
    provision_op = spec["paths"][provision_template]["post"]
    assert "401" in provision_op["responses"] or "403" in provision_op["responses"], (
        "provision must declare its auth refusal"
    )


def test_provision_generates_opaque_code_once(pg_client, pg_admin_user, direction_world):
    response = _provision(pg_client, _auth_headers(pg_admin_user), "rq16d-cardio")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["direction_key"] == "rq16d-cardio"
    assert body["profile_id"] == direction_world["cardio"].id
    assert body["created"] is True
    assert CODE_RE.match(body["public_code"]), (
        "public_code must be 12 lowercase Crockford/Base32-like chars (E-055 §2)"
    )
    assert body["url_path"] == f"/q/{body['public_code']}"


def test_provision_is_idempotent_never_regenerates(
    pg_client, pg_admin_user, direction_world
):
    headers = _auth_headers(pg_admin_user)
    first = _provision(pg_client, headers, "rq16d-cardio")
    assert first.status_code == 200
    code = first.json()["public_code"]
    second = _provision(pg_client, headers, "rq16d-cardio")
    assert second.status_code == 200
    body = second.json()
    assert body["created"] is False, (
        "E-055 §3: the code is generated ONCE — re-provision must return "
        "the SAME address, never regenerate"
    )
    assert body["public_code"] == code


def test_provision_requires_admin(pg_session, pg_client, pg_admin_user, direction_world):
    registrar = _get_or_create_user(pg_session, "rq16d_registrar", "Registrar")
    no_auth = _provision(pg_client, {}, "rq16d-cardio")
    assert no_auth.status_code in (401, 403), "provision must never be anonymous"
    registrar_response = _provision(
        pg_client, _auth_headers(registrar), "rq16d-cardio"
    )
    assert registrar_response.status_code == 403, registrar_response.text


def test_provision_unknown_key_refuses(pg_client, pg_admin_user, direction_world):
    response = _provision(pg_client, _auth_headers(pg_admin_user), "rq16d-never")
    assert response.status_code == 404


def test_provision_refuses_clinic_sentinel_key(
    pg_client, pg_admin_user, direction_world
):
    """The ``clinic`` key is the clinic-wide QR sentinel: it must never
    become a direction address (defense in depth — the session scope is
    carried by the reserved ``qdir:`` prefix, and the sentinel key stays
    out of the direction-address namespace entirely)."""
    response = _provision(pg_client, _auth_headers(pg_admin_user), "clinic")
    assert response.status_code == 400, response.text


def test_collision_retry_generates_fresh_code(
    pg_session, pg_client, pg_admin_user, direction_world, monkeypatch
):
    """E-055 §11: on a (astronomically unlikely) collision the provisioner
    retries with a FRESH code — the global UNIQUE constraint arbitrates."""
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress

    burned = "2aaaaaaaaaaa"
    stale = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(QueueDirectionPublicAddress.public_code.in_([burned, "2bbbbbbbbbbb"]))
        .all()
    )
    for row in stale:
        row.queue_profile_id = None
    pg_session.add(
        QueueDirectionPublicAddress(queue_profile_id=None, public_code=burned)
    )
    pg_session.commit()

    calls = {"n": 0}

    def fake_generate():
        calls["n"] += 1
        return burned if calls["n"] == 1 else "2bbbbbbbbbbb"

    import app.services.queue_svc._operations as ops_module

    monkeypatch.setattr(ops_module, "generate_public_code", fake_generate)
    response = _provision(pg_client, _auth_headers(pg_admin_user), "rq16d-derma")
    assert response.status_code == 200, response.text
    assert calls["n"] >= 2, "the collision must trigger a retry"
    assert response.json()["public_code"] == "2bbbbbbbbbbb"
    assert response.json()["public_code"] != burned


def test_public_start_happy_path_continues_existing_join_flow(
    pg_client, pg_admin_user, direction_world
):
    provisioned = _provision(
        pg_client, _auth_headers(pg_admin_user), "rq16d-cardio"
    )
    assert provisioned.status_code == 200
    code = provisioned.json()["public_code"]

    # ASCII-case normalization at the input boundary (E-055 §11): lookup
    # is case-insensitive, storage stays canonical lowercase.
    response = _start(pg_client, f"  {code.upper()} ")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_token"], "a short-lived session must be created"
    assert body["permanent_address"] is True
    assert body["direction"]["profile_id"] == direction_world["cardio"].id
    assert body["direction"]["key"] == "rq16d-cardio"
    assert body["direction"]["public_code"] == code.lower()
    info = body["queue_info"]
    assert info.get("is_clinic_wide") is True
    selectable = info.get("selectable_specialists") or []
    assert {item["id"] for item in selectable} == {
        direction_world["cardio_doctor"].id
    }, "the direction session must advertise ONLY its own eligible owners"
    assert "token" not in info, (
        "the internal minted token is not a second credential — the "
        "session_token drives the existing QueueJoin flow"
    )

    complete = pg_client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": body["session_token"],
            "patient_name": "RQ16d Синтетик Пациент",
            "phone": "+998900000001",
            "specialist_ids": [direction_world["cardio"].id],
            "specialist_entity_types": ["profile"],
        },
    )
    assert complete.status_code == 200, complete.text
    complete_body = complete.json()
    assert complete_body["success"] is True
    entries = complete_body.get("entries") or []
    assert entries and entries[0]["queue_number"] >= 1, (
        "the direction session must complete through the EXISTING "
        "typed-profile QueueJoin flow"
    )


def test_public_start_refusal_matrix_byte_identical(
    pg_session, pg_client, pg_admin_user, direction_world
):
    """S-15: unknown / archived / hidden / tombstone / retired refuse with
    the SAME anonymous response — no existence leak."""
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress
    from app.models.queue_profile import QueueProfile

    headers = _auth_headers(pg_admin_user)
    codes: dict[str, str] = {}
    for key in ("rq16d-cardio", "rq16d-archived", "rq16d-hidden", "rq16d-plain"):
        resp = _provision(pg_client, headers, key)
        assert resp.status_code == 200, resp.text
        codes[key] = resp.json()["public_code"]

    # 1) tombstone: hard delete the profile (permitted with zero
    # significant links); the FK ON DELETE SET NULL leaves the registry
    # row behind — the burned code must refuse, never route anywhere.
    cardio = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == "rq16d-cardio")
        .first()
    )
    pg_session.delete(cardio)
    pg_session.commit()
    tombstone_row = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(
            QueueDirectionPublicAddress.queue_profile_id.is_(None),
            QueueDirectionPublicAddress.public_code == codes["rq16d-cardio"],
        )
        .first()
    )
    assert tombstone_row is not None, "the tombstone row must survive the delete"

    # 2) retired: the row is retired while the profile stays visible —
    # a retired address is dead (rotation is a separate future workstream).
    plain_row = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(QueueDirectionPublicAddress.public_code == codes["rq16d-plain"])
        .first()
    )
    plain_row.retired_at = plain_row.created_at
    pg_session.commit()

    unknown = _start(pg_client, "2zzzzzzzzzzz")
    archived = _start(pg_client, codes["rq16d-archived"])
    hidden = _start(pg_client, codes["rq16d-hidden"])
    tombstone = _start(pg_client, codes["rq16d-cardio"])
    retired = _start(pg_client, codes["rq16d-plain"])
    for response in (unknown, archived, hidden, tombstone, retired):
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": REFUSAL_DETAIL}
    assert (
        unknown.content
        == archived.content
        == hidden.content
        == tombstone.content
        == retired.content
    ), "the five refusals must be byte-identical (S-15 no-leak)"


def test_rename_keeps_the_same_address(
    pg_session, pg_client, pg_admin_user, direction_world
):
    from app.models.queue_profile import QueueProfile

    headers = _auth_headers(pg_admin_user)
    code = _provision(pg_client, headers, "rq16d-derma").json()["public_code"]
    assert _start(pg_client, code).status_code == 200

    profile = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == "rq16d-derma")
        .first()
    )
    profile.title_ru = "RQ-16.d дерма ПЕРЕИМЕНОВАН"
    pg_session.commit()

    response = _start(pg_client, code)
    assert response.status_code == 200, (
        "E-055 §7: rename must never change the address"
    )


def test_reactivate_restores_the_same_address(
    pg_session, pg_client, pg_admin_user, direction_world
):
    """Archive a doctor-backed direction -> the address refuses; reactivate
    the SAME profile -> the SAME address becomes usable again (E-055 §7).
    (The hidden profile is NOT usable here: show_on_qr_page stays False
    and the eligibility probe honestly refuses a direction without
    owners — that is the S-15 contract, not a defect.)"""
    from app.models.queue_profile import QueueProfile

    headers = _auth_headers(pg_admin_user)
    code = _provision(pg_client, headers, "rq16d-cardio").json()["public_code"]

    profile = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == "rq16d-cardio")
        .first()
    )
    profile.is_active = False
    pg_session.commit()
    assert _start(pg_client, code).status_code == 404, (
        "archive must block the join by the old address (E-055 §7)"
    )

    profile.is_active = True
    pg_session.commit()
    response = _start(pg_client, code)
    assert response.status_code == 200, (
        "reactivating the SAME profile restores the SAME address (E-055 §7)"
    )


def test_unprovisioned_direction_refuses_start(
    pg_client, pg_admin_user, direction_world
):
    """No backfill (E-055 §3): a visible, eligible direction WITHOUT a
    provisioned address has NO permanent address yet."""
    response = _start(pg_client, "2ccccccccccc")
    assert response.status_code == 404
    assert response.json() == {"detail": REFUSAL_DETAIL}


def test_session_binding_scopes_the_direction(
    pg_session, pg_client, pg_admin_user, direction_world
):
    """A session opened through the permanent address of direction A must
    NEVER complete for direction B (or for an untyped doctor id): the
    join path enforces the scope server-side."""
    headers = _auth_headers(pg_admin_user)
    cardio_code = _provision(pg_client, headers, "rq16d-cardio").json()["public_code"]
    _provision(pg_client, headers, "rq16d-derma")

    started = _start(pg_client, cardio_code)
    assert started.status_code == 200, started.text
    session_token = started.json()["session_token"]

    cross = pg_client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "RQ16d Синтетик Пациент",
            "phone": "+998900000002",
            "specialist_ids": [direction_world["derma"].id],
            "specialist_entity_types": ["profile"],
        },
    )
    assert cross.status_code == 400, cross.text
    # NOTE: the complete endpoint masks ValueError details (legacy
    # behavior); the binding proof is the refusal PLUS the zero-entry
    # state — the happy-path test proves the SAME session shape succeeds
    # for its OWN direction.
    from app.models.online_queue import OnlineQueueEntry

    entries_after_cross = (
        pg_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.patient_name == "RQ16d Синтетик Пациент",
            OnlineQueueEntry.phone == "+998900000002",
        )
        .count()
    )
    assert entries_after_cross == 0, (
        "a cross-direction completion must not create a queue entry"
    )

    untyped_doctor = pg_client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "RQ16d Синтетик Пациент",
            "phone": "+998900000003",
            "specialist_ids": [direction_world["cardio_doctor"].id],
            "specialist_entity_types": ["doctor"],
        },
    )
    assert untyped_doctor.status_code == 400, untyped_doctor.text


def test_entry_methods_permanent_address_flag_is_dynamic(
    pg_client, pg_admin_user, direction_world
):
    """E-055 §8: the flag is True only for a provisioned direction whose
    canonical eligibility probe passes; unprovisioned stays False."""
    headers = _auth_headers(pg_admin_user)

    def _flag(key: str) -> bool:
        response = pg_client.get(METHODS_PATH.replace("{profile_key}", key))
        assert response.status_code == 200, response.text
        flags = {
            item["method"]: item["supported"]
            for item in response.json()["entry_methods"]
        }
        return flags["permanent_address"]

    assert _flag("rq16d-cardio") is False, "not provisioned yet — must not claim"
    _provision(pg_client, headers, "rq16d-cardio")
    assert _flag("rq16d-cardio") is True, (
        "provisioned + visible + eligible — the flag must flip honestly"
    )
    assert _flag("rq16d-plain") is False, "unprovisioned — no backfill (E-055 §3)"


def test_rate_limit_knob_is_configured():
    """The anonymous start is rate-limited (E-055 §9 item 6) through the
    repo's env-configurable slowapi knob (PR-34/CHAT-10.1 pattern)."""
    from app.core.rate_limiter import RATE_LIMITS

    assert "public_direction_start" in RATE_LIMITS
    assert re.match(r"^\d+/\S+$", RATE_LIMITS["public_direction_start"])


def test_public_start_rate_limit_enforced_when_enabled(
    pg_client, pg_admin_user, direction_world, monkeypatch
):
    """Behavioral proof: with the limiter ENABLED the anonymous surface
    returns 429 after its budget. TESTING mode keeps the limiter off for
    every other test — enabled here only, and reset afterwards."""
    from slowapi.errors import RateLimitExceeded

    from app.core.rate_limiter import _rate_limit_exceeded_handler, limiter

    # slowapi reads the plain ``enabled`` attribute at request time (the
    # constructor sets it from TESTING); monkeypatch restores it after.
    monkeypatch.setattr(limiter, "enabled", True)
    pg_client.app.add_exception_handler(
        RateLimitExceeded, _rate_limit_exceeded_handler
    )
    try:
        codes = [_start(pg_client, "2eeeeeeeeeee").status_code for _ in range(12)]
        assert 429 in codes, f"the anonymous surface must rate-limit (got {codes})"
    finally:
        limiter.reset()
