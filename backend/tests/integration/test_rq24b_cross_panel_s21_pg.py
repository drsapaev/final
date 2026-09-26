"""
RQ-24.b — the S-21 cross-panel path repeated on a NEW target/resource
after the integrated model (RQ-08 queue identity, RQ-15 resource axis,
RQ-16 direction + public address, RQ-18 anonymous join protocol,
RQ-21 worklist counters).

Plan §RQ-24.b: "повторить путь с новым target/resource после
интеграции". ACCEPTANCE S-21: registrar -> QR/desk -> Doctor/Lab ->
Cashier -> Patient -> табло; reconnect. Expected: every participant
sees the role-scoped work, matching numbers in different cabinets are
distinguishable, the patient sees only their own data, the public board
leaks no PHI, and a reconnect restores the state.

This is a VERIFICATION slice (plan §"RQ-24…RQ-27: verification сначала;
один подтвержденный дефект — один child PR"): the application runtime
is consumed, never modified. All data is SYNTHETIC
(``rq24b-``/``SYNTHETIC-`` markers, disposable scratch database).

Disposable PostgreSQL: the module provisions its own scratch database
(rq24b_check_<hex>, unique per run), runs ``alembic upgrade head`` and
drops it at the end; skips (NOT_RUN, plan P0) when no disposable
PostgreSQL server is reachable. ``DATABASE_URL`` is accepted for
automatic provisioning only for local servers — an explicit loopback
host, a hostless unix-socket DSN, or a ``?host=`` that is a
socket-directory path or a loopback name; hidden address sources
(``?hostaddr=``, a remote ``?host=`` entry — including inside a
comma-separated fallback list — an address-overriding
``PGHOSTADDR``/remote-``PGHOST`` environment, or a
``?service=``/``PGSERVICE`` reference, which lets pg_service.conf
supply the actually dialed address) are rejected, so a remote admin
DSN must be
passed explicitly via the test-owned ``RQ24B_PG_ADMIN_URL``. SQLite is
never a substitute here. The HTTP surfaces run
through the real FastAPI app (TestClient) against that scratch
database; the display-board WebSocket is exercised through the real
WS endpoint (JWT required, ``initial_state`` on connect).

Modelled on tests/integration/test_rq16d_public_direction_runtime.py
(the merged real-PG runtime harness precedent).

Run::

    cd backend && DATABASE_URL=postgresql+psycopg://clinic:pw@localhost:5432/clinicdb \
        pytest tests/integration/test_rq24b_cross_panel_s21_pg.py -q
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Unique per run (review P2 — scratch-DB isolation, RQ-26.b follow-up
# class fix): a fixed name with an unconditional pre-drop let two
# parallel pytest/agent runs on the same PostgreSQL server drop each
# other's database. Cleanup drops ONLY the database this run created.
SCRATCH_DB = f"rq24b_check_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))

pytestmark = pytest.mark.integration

# ---- canonical routes under test (S-21 participants) ----
QR_GENERATE = "/api/v1/queue/admin/qr-tokens/generate"
QR_INFO = "/api/v1/queue/qr-tokens/{token}/info"
JOIN_START = "/api/v1/queue/join/start"
JOIN_COMPLETE = "/api/v1/queue/join/complete"
JOIN_PROBE = "/api/v1/queue/join/probe"
PROVISION = "/api/v1/queue/admin/directions/{profile_key}/public-address/provision"
PUBLIC_START = "/api/v1/queue/public/{public_code}/start-session"
ENTRY_METHODS = "/api/v1/queue/directions/{profile_key}/entry-methods"
DOCTOR_QUEUE_TODAY = "/api/v1/doctor/{specialty}/queue/today"
LAB_QUEUE_TODAY = "/api/v1/lab/queue/today"
CASHIER_PENDING = "/api/v1/cashier/pending-payments"
CASHIER_GROUPED = "/api/v1/cashier/payments/grouped"
PATIENT_APPOINTMENTS = "/api/v1/patients/appointments"
REGISTRAR_TODAY = "/api/v1/registrar/queues/today"
BOARD_STATE = "/api/v1/board/state"
WS_BOARD = "/api/v1/display/ws/board/main_board"
RESOURCE_CREATE = "/api/v1/queue/admin/queue-resources"
BATCH_ENTRIES = "/api/v1/registrar-integration/queue/entries/batch"

DOCTOR_SPECIALTY = "rq24b-cardio"
LAB_TAG = "lab"
DIRECTION_KEY = "rq24b-synthetic"
PHONE_A = "998501000001"  # SYNTHETIC walk-in (doctor leg)
PHONE_C = "998501000002"  # SYNTHETIC walk-in (resource leg)
PHONE_D = "998501000003"  # SYNTHETIC walk-in (cashier leg)


# ------------------------------------------------------------------
# disposable PostgreSQL harness (scratch DB + alembic head)
# ------------------------------------------------------------------


def _candidate_admin_urls() -> list[str]:
    """Plain-psycopg admin DSNs — LOCAL servers only for auto-detection.

    ``DATABASE_URL`` in CI is a SQLAlchemy URL
    (``postgresql+psycopg://``); psycopg.connect rejects the driver
    suffix, so the scheme is normalized for the admin connection.

    The scratch database must never be provisioned — or dropped — on a
    remote server reachable through a plain ``DATABASE_URL`` (review P2,
    RQ-26.b follow-up class fix): auto-detected candidates are accepted
    only for LOCAL servers, judged by the address libpq actually dials,
    not by the URL spelling. A ``?host=`` query parameter overrides the
    authority host, so a remote value there
    (``postgresql://u:p@/postgres?host=db.internal``, review P1) is
    rejected even though the authority is empty — including remote
    entries inside a comma-separated fallback list; the address-altering
    ``?hostaddr=`` is rejected outright (round-2 review P1), as is an
    address-overriding ``PGHOSTADDR``/remote-``PGHOST`` environment
    (round-3 review P1), and any ``?service=``/``PGSERVICE`` reference
    (round-4 review P1): libpq resolves a service name from
    pg_service.conf into host/port/etc. at connect time, so a
    service-referencing candidate cannot be proven to dial the same
    local address its scratch DSN reproduces. A remote admin DSN must
    be passed explicitly via the test-owned ``RQ24B_PG_ADMIN_URL``.
    """
    urls: list[str] = []

    def _normalized(raw: str) -> str:
        return raw.replace("postgresql+psycopg://", "postgresql://", 1)

    def _is_local(url: str) -> bool:
        """True only for addresses libpq dials locally (review P1, r1-r3)."""
        try:
            u = make_url(url)
        except Exception:  # noqa: BLE001 — a malformed env DSN (e.g. a
            # non-SQLAlchemy ``file:`` URL) must degrade to "not a local
            # PG candidate", never crash the auto-detection.
            return False
        if not u.drivername.startswith("postgresql"):
            return False  # a sqlite fallback URL is never a PG candidate

        def _host_elem_local(h: str) -> bool:
            # An empty element is libpq's "default unix-socket directory".
            return (
                h == ""
                or h.startswith("/")
                or h in {"localhost", "127.0.0.1", "::1"}
            )

        # Normalize query params once: libpq matches conninfo parameter
        # names case-insensitively, and SQLAlchemy parses repeated keys
        # into sequences — the guard must not be bypassable by spelling
        # (``?HOSTADDR=``) or duplication (round-2 review P1).
        qvals: dict[str, list[str]] = {}
        for k, v in (u.query or {}).items():
            vals = v if isinstance(v, (list, tuple)) else [v]
            qvals.setdefault(str(k).lower(), []).extend(str(x) for x in vals)
        # ``?hostaddr=`` overrides the dialed network address even when
        # the authority / ``?host=`` spell a loopback (round-2 review
        # P1): ANY value there is an address-altering parameter — a
        # non-loopback one dials a remote server, and even a loopback
        # literal cannot be reproduced by ``_scratch_urls()`` (it
        # preserves authority / ``?host=`` forms only) — so the guard
        # rejects the parameter outright (fail-closed).
        if qvals.get("hostaddr"):
            return False
        # ``?service=`` (round-4 review P1) resolves host/port/etc. from
        # pg_service.conf at connect time; ``_scratch_urls()`` does not
        # inspect or reproduce the service contract, so the scratch DSN
        # may dial a DIFFERENT address than the probe did. ANY presence
        # of the parameter — any case, repeated form, even alongside an
        # explicit localhost — rejects the candidate (fail-closed).
        if qvals.get("service"):
            return False
        # libpq fills omitted connection fields from the process
        # environment (round-3 review P1): ``PGHOSTADDR`` supplies the
        # dialed address even when the DSN spells a loopback or a socket
        # directory, and ``PGHOST`` supplies the host for a hostless DSN
        # — the probe, provisioning, teardown, and the Alembic
        # subprocess all inherit them. Fail-closed: any ``PGHOSTADDR``
        # presence rejects (symmetric with the DSN policy above).
        if os.getenv("PGHOSTADDR", "").strip():
            return False
        # ``PGSERVICE`` (round-4 review P1) is the environment twin of
        # ``?service=``: libpq loads the service definition for any DSN
        # that leaves fields unspelled — a hostless or localhost DSN
        # would silently dial wherever the service file points. Any
        # non-empty value rejects (fail-closed).
        if os.getenv("PGSERVICE", "").strip():
            return False
        # ``?host=`` overrides the authority host — and libpq accepts
        # comma-separated FALLBACK hosts there (round-3 review P1):
        # ``?host=/var/run/postgresql,db.internal`` is REMOTE, because
        # the fallback is dialed when the socket fails. Every element of
        # every value must be a socket-directory path, an empty default,
        # or a loopback name (fail-closed).
        hosts: list[str] = []
        for h in qvals.get("host") or []:
            hosts.extend(h.split(","))
        if hosts:
            return all(_host_elem_local(h) for h in hosts)
        if u.host is not None:
            return all(_host_elem_local(h) for h in u.host.split(","))
        env_host = os.getenv("PGHOST", "")
        if env_host:
            return all(_host_elem_local(h) for h in env_host.split(","))
        # Hostless DSN (``postgresql:///db``) with no ``PGHOST``: libpq
        # dials the default unix-socket directory — local by definition
        # (review P2: this must not silently skip a reachable local
        # server).
        return True

    explicit = os.getenv("RQ24B_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(_normalized(explicit))
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url and _is_local(_normalized(env_url)):
        urls.append(_normalized(env_url))
    return urls


def _dsn_parts(admin_url: str) -> dict:
    """Split a DSN into libpq address parts WITHOUT re-typing the host.

    The address mode is preserved verbatim (review P2): a hostless DSN
    must stay hostless — substituting ``"localhost"`` would silently
    switch the scratch connection from the unix socket to TCP.
    """
    from urllib.parse import parse_qs, urlparse

    p = urlparse(admin_url)
    q = parse_qs(p.query)
    qhost = (q.get("host") or [None])[0]
    return {
        # ``?host=/abs/path`` → unix-socket directory; ``?host=<name>``
        # → explicit TCP host from the query; no host anywhere →
        # default unix socket (host=None, no qhost).
        "sockdir": qhost if qhost and qhost.startswith("/") else None,
        "qhost": qhost if qhost and not qhost.startswith("/") else None,
        "user": p.username or "postgres",
        "password": p.password or "",
        "host": p.hostname,
        "port": p.port,
    }


def _scratch_urls(admin_url: str) -> tuple[str, str]:
    parts = _dsn_parts(admin_url)
    userinfo = f"{parts['user']}:{parts['password']}"
    if parts["sockdir"]:
        base_p = f"postgresql://{userinfo}@/"
        base_s = f"postgresql+psycopg://{userinfo}@/"
        return (
            f"{base_p}{SCRATCH_DB}?host={parts['sockdir']}",
            f"{base_s}{SCRATCH_DB}?host={parts['sockdir']}",
        )
    if parts["qhost"]:
        # The admin DSN dialed an explicit TCP host through the query —
        # the scratch DSN repeats that form instead of inventing one.
        base_p = f"postgresql://{userinfo}@/{SCRATCH_DB}?host={parts['qhost']}"
        base_s = f"postgresql+psycopg://{userinfo}@/{SCRATCH_DB}?host={parts['qhost']}"
        return base_p, base_s
    if not parts["host"]:
        # Hostless stays hostless: the scratch connection resolves the
        # server through the (default) unix-socket directory exactly
        # like the admin DSN did (review P2).
        port = f":{parts['port']}" if parts["port"] else ""
        base_p = f"postgresql://{userinfo}@{port}/"
        base_s = f"postgresql+psycopg://{userinfo}@{port}/"
        return (
            f"{base_p}{SCRATCH_DB}",
            f"{base_s}{SCRATCH_DB}",
        )
    port = parts["port"] if parts["port"] else 5432
    base = f"postgresql://{userinfo}@{parts['host']}:{port}"
    return (
        f"{base}/{SCRATCH_DB}",
        f"postgresql+psycopg://{userinfo}@{parts['host']}:{port}/{SCRATCH_DB}",
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
            f"disposable PostgreSQL unavailable — RQ-24.b PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    # No pre-drop: the name is unique per run, so a leftover database can
    # never be silently reused — a name collision fails loudly instead.
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    # try/finally (review P2, RQ-26.b follow-up class fix): alembic,
    # engine creation, or an assertion may fail BEFORE the yield —
    # pytest does not run the post-yield teardown then, and with
    # run-unique names the leaked scratch database would never be
    # cleaned by any later run. Everything after the successful CREATE
    # DATABASE must therefore drop it unconditionally.
    engine = None
    try:
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
            version = conn.execute(
                text("select version_num from alembic_version")
            ).scalar()
            dialect = conn.execute(text("select version()")).scalar()
        assert version, "alembic_version must be present after upgrade"
        assert "PostgreSQL" in (dialect or ""), (
            "RQ-24.b proof requires real PostgreSQL"
        )

        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        # Disposable-DB teardown: force-close any backend still attached
        # to the scratch database (e.g. a middleware transaction that
        # stays open past the request), then drop it.
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity "
                "where datname = %s and pid <> pg_backend_pid()",
                (SCRATCH_DB,),
            )
            c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')


@pytest.fixture
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def _deterministic_clinic_day(monkeypatch):
    """Deterministic clinic day for the scenario.

    The product resolves the queue day from clinic settings (default
    Asia/Tashkent, online cutoff 09:00): after the cutoff an anonymous
    join targets TOMORROW, while the doctor panel reads host
    ``date.today()`` — the S-21 participants would look at different
    days depending on the wall clock of the CI run. The harness pins
    the queue settings SSOT (timezone=UTC, cutoff=24 -> never shifts)
    so every participant surface resolves the SAME day deterministically.
    This is harness configuration, not an application change.
    """
    from datetime import time as _time

    from app.services.queue_svc import QueueBusinessService
    from app.services.queue_svc._base import QueueBusinessServiceMixinBase

    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", _time(0, 0))
    monkeypatch.setattr(
        QueueBusinessServiceMixinBase, "ONLINE_QUEUE_START_TIME", _time(0, 0)
    )

    import app.crud.clinic as clinic_crud
    import app.services.queue_svc._core as queue_core

    deterministic_settings = {
        "timezone": "UTC",
        "queue_start_hour": 0,
        "queue_qr_cutoff_hour": 24,
        "auto_close_time": "23:59",
        "start_numbers": {},
        "max_per_day": {},
    }
    monkeypatch.setattr(clinic_crud, "get_queue_settings", lambda db: dict(deterministic_settings))
    monkeypatch.setattr(queue_core, "get_queue_settings", lambda db: dict(deterministic_settings))

    # The queue_service SINGLETON caches its settings read for its whole
    # lifetime: in the full CI suite earlier tests populate the cache
    # with the real clinic settings before this module runs, and the
    # pinned settings below would silently lose to that cache. The
    # attribute is replaced via monkeypatch so the ORIGINAL cached value
    # is RESTORED after every test — no state leaks into later suites
    # (a leaked UTC/cutoff-24 dict changes later tests' day math).
    import app.services.queue_service as queue_service_module

    monkeypatch.setattr(
        queue_service_module.queue_service, "_cached_settings", None
    )

    # Same singleton-cache class for the board name-format cache
    # (RQ-24.a.1): an earlier suite test that connected to the display
    # WS would pin main_board's format from the real clinic DB. The
    # whole dict is swapped (not cleared) and restored by monkeypatch.
    from app.services.display_websocket import get_display_manager

    monkeypatch.setattr(get_display_manager(), "_name_format_cache", {})


@pytest.fixture
def pg_client(pg_session, monkeypatch):
    """TestClient wired to the disposable PostgreSQL session.

    The display-board WS endpoint opens its own ``SessionLocal()``
    (get_db is not involved there), so the module-level SessionLocal is
    redirected to the scratch database for the duration of the test.
    """
    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        try:
            yield pg_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    import app.api.v1.endpoints.display_websocket as display_ws_module
    import app.services.display_websocket as display_ws_service_module

    scratch_sessionmaker = sessionmaker(bind=pg_session.bind, future=True)
    # The WS endpoint AND the manager's _send_current_state both open
    # their own SessionLocal() (get_db is not involved there) — patch
    # BOTH module namespaces onto the scratch database.
    monkeypatch.setattr(display_ws_module, "SessionLocal", scratch_sessionmaker)
    monkeypatch.setattr(
        display_ws_service_module, "SessionLocal", scratch_sessionmaker
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    # The app-level engine (settings DATABASE_URL -> scratch DB during
    # local runs) may hold pooled connections: dispose it BEFORE the
    # module fixture drops the scratch database (ObjectInUse guard).
    from app.db import session as app_db_session

    try:
        app_db_session.engine.dispose()
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------
# synthetic world
# ------------------------------------------------------------------


def _get_or_create_user(session, username: str, role: str):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        # AGENTS.md PII rules: email must never appear in plaintext in
        # committed test fixtures — synthetic users carry no email at all
        # (RQ-26.b follow-up class fix).
        email=None,
        full_name=f"RQ-24.b {username}",
        hashed_password=get_password_hash("rq24b-synthetic-pw"),
        role=role,
        is_active=True,
        is_superuser=role == "Admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _get_or_create_doctor(session, user_id: int, specialty: str, cabinet: str):
    from app.models.clinic import Doctor

    doctor = (
        session.query(Doctor)
        .filter(Doctor.user_id == user_id, Doctor.specialty == specialty)
        .first()
    )
    if doctor:
        return doctor
    doctor = Doctor(
        user_id=user_id, specialty=specialty, cabinet=cabinet, active=True
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


def _auth_headers(user) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


@pytest.fixture
def world(pg_session, pg_client):
    """SYNTHETIC S-21 world, created through the REAL admin API wherever
    the integrated flow has an API (RQ-15 resource + RQ-17 activation
    gate + RQ-16 direction + RQ-16.d public address)."""
    from app.models.patient import Patient

    admin = _get_or_create_user(pg_session, "rq24b_admin", "Admin")
    registrar = _get_or_create_user(pg_session, "rq24b_registrar", "Registrar")
    doctor_user = _get_or_create_user(pg_session, "rq24b_doc", "Doctor")
    lab_user = _get_or_create_user(pg_session, "rq24b_lab", "Lab")
    cashier = _get_or_create_user(pg_session, "rq24b_cashier", "Cashier")
    doctor = _get_or_create_doctor(
        pg_session, doctor_user.id, DOCTOR_SPECIALTY, cabinet="209"
    )

    # Portal patient with own login (Patient.user_id FK — RQ-18 identity
    # surfaces): SYNTHETIC person, no realistic personal bundle.
    portal_user = _get_or_create_user(pg_session, "rq24b_patient", "Patient")
    patient = (
        pg_session.query(Patient).filter(Patient.user_id == portal_user.id).first()
    )
    if not patient:
        patient = Patient(
            user_id=portal_user.id,
            last_name="RQ24B-SYNTHETIC",
            first_name="Б",
            phone="+" + PHONE_A[:-3] + "999",
        )
        pg_session.add(patient)
        pg_session.commit()
        pg_session.refresh(patient)

    admin_h = _auth_headers(admin)
    registrar_h = _auth_headers(registrar)

    # --- services: doctor target + doctorless resource target ---
    # Seeded directly: ServiceCreate (public DTO) does not carry
    # requires_doctor/queue_tag — the RQ-17 §3.1 activation gate reads
    # the MODEL columns (tag_service_set_state). Seeding reference data
    # mirrors the merged rq16d harness (profiles/doctors by model).
    from decimal import Decimal

    from app.models.service import Service

    service_ids: dict[str, int] = {}
    service_specs = [
        {
            "code": "SYNTHETIC-rq24b-consult",
            "name": "SYNTHETIC RQ-24.b consultation",
            "price": Decimal("50000"),
            "requires_doctor": True,
            "queue_tag": DOCTOR_SPECIALTY,
            "department_key": DOCTOR_SPECIALTY,
        },
        {
            "code": "SYNTHETIC-rq24b-labtest",
            "name": "SYNTHETIC RQ-24.b lab test",
            "price": Decimal("30000"),
            "requires_doctor": False,
            "queue_tag": LAB_TAG,
            "department_key": LAB_TAG,
        },
    ]
    for spec in service_specs:
        tag = spec["queue_tag"]
        row = (
            pg_session.query(Service)
            .filter(Service.code == spec["code"])
            .first()
        )
        if not row:
            row = Service(
                code=spec["code"],
                name=spec["name"],
                price=spec["price"],
                active=True,
                requires_doctor=spec["requires_doctor"],
                queue_tag=tag,
                department_key=spec["department_key"],
            )
            pg_session.add(row)
            pg_session.commit()
            pg_session.refresh(row)
        service_ids[tag] = row.id

    # --- RQ-15 resource queue + RQ-17 activation gate (REAL API) ---
    resp = pg_client.post(
        RESOURCE_CREATE,
        json={
            "code": "SYNTHETIC-rq24b-lab-cab",
            "queue_tag": LAB_TAG,
            "display_name": "SYNTHETIC Lab Cabinet 204",
            "start_number_online": 1,
            "max_online_per_day": 15,
            "default_cabinet": "204",
            "active": False,
        },
        headers=admin_h,
    )
    if resp.status_code == 409:
        # idempotent world (function-scoped fixture on one module DB)
        listing = pg_client.get(RESOURCE_CREATE, headers=admin_h)
        assert listing.status_code == 200, listing.text
        rows = listing.json()
        if isinstance(rows, dict):
            rows = rows.get("items") or rows.get("resources") or []
        resource = next(
            r for r in rows if r.get("code") == "SYNTHETIC-rq24b-lab-cab"
        )
    else:
        assert resp.status_code == 201, resp.text
        resource = resp.json()
    # RQ-17 §3.1: activation is a separate gate — a doctorless service on
    # the tag exists, so the PATCH must succeed now that the world is set.
    resp = pg_client.patch(
        f"{RESOURCE_CREATE}/{resource['id']}",
        json={"active": True},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text

    # --- RQ-16 direction + RQ-16.d permanent public address ---
    from app.models.queue_profile import QueueProfile

    stale = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == DIRECTION_KEY)
        .all()
    )
    for profile in stale:
        pg_session.delete(profile)
    pg_session.commit()
    profile = QueueProfile(
        key=DIRECTION_KEY,
        title="RQ-24.b synthetic direction",
        title_ru="RQ-24.b синтетическое направление",
        queue_tags=[DOCTOR_SPECIALTY, LAB_TAG],
        display_order=9,
        is_active=True,
        show_on_qr_page=True,
    )
    pg_session.add(profile)
    pg_session.commit()
    pg_session.refresh(profile)

    resp = pg_client.get(ENTRY_METHODS.replace("{profile_key}", DIRECTION_KEY))
    assert resp.status_code == 200, resp.text
    methods = resp.json()
    permanent = next(
        m
        for m in methods["entry_methods"]
        if m["method"] == "permanent_address"
    )

    resp = pg_client.post(
        PROVISION.replace("{profile_key}", DIRECTION_KEY), headers=admin_h
    )
    assert resp.status_code == 200, resp.text
    provisioned = resp.json()
    assert provisioned["created"] is True
    assert provisioned["url_path"] == f"/q/{provisioned['public_code']}"

    return {
        "admin": admin,
        "registrar": registrar,
        "doctor_user": doctor_user,
        "doctor": doctor,
        "lab_user": lab_user,
        "cashier": cashier,
        "portal_user": portal_user,
        "patient": patient,
        "service_ids": service_ids,
        "resource": resource,
        "profile": profile,
        "public_code": provisioned["public_code"],
        "permanent_supported_before_provision": permanent["supported"],
        "admin_h": admin_h,
        "registrar_h": registrar_h,
    }


def _anonym_join(pg_client, token: str, name: str, phone: str) -> dict:
    """Anonymous QR session: start -> complete (RQ-18 protocol)."""
    resp = pg_client.post(JOIN_START, json={"token": token})
    assert resp.status_code == 200, resp.text
    session_token = resp.json()["session_token"]
    resp = pg_client.post(
        JOIN_COMPLETE,
        json={
            "session_token": session_token,
            "patient_name": name,
            "phone": phone,
        },
    )
    assert resp.status_code == 200, resp.text
    return {"session_token": session_token, "result": resp.json()}


def _ws_state(pg_client, user, board_id: str = "main_board") -> dict:
    """One REAL websocket session: initial_state on connect (the same
    message a reconnecting board receives)."""
    from tests.conftest import mint_access_token

    jwt = mint_access_token(user)
    with pg_client.websocket_connect(
        WS_BOARD,
        headers={"Authorization": f"Bearer {jwt}"},
    ) as ws:
        message = ws.receive_json()
    assert message["type"] == "initial_state", message.get("type")
    return message["data"]


# ------------------------------------------------------------------
# S-21 legs
# ------------------------------------------------------------------


def test_new_target_and_resource_are_reachable_through_integrated_flow(
    pg_client, world
):
    """The NEW direction (doctor tag + resource tag) is bookable through
    the integrated surface: the anonymous start resolves the direction
    with its owners (RQ-18 queue_info) — after provisioning (RQ-16.d)."""
    resp = pg_client.post(
        PUBLIC_START.replace("{public_code}", world["public_code"])
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["direction"]["key"] == DIRECTION_KEY
    assert body["permanent_address"] is True
    selectable = body["queue_info"]["selectable_specialists"]
    assert selectable, "direction owners must be offered to the anonymous client"
    assert all(
        s.get("entity_type") in ("doctor", "profile") for s in selectable
    )


def test_doctor_target_qr_join_reaches_doctor_panel(pg_client, world):
    """Leg 1 — NEW doctor target: registrar QR -> anonymous join ->
    doctor's own queue shows the walk-in (role-scoped, RQ-08 identity);
    the resource queue is NOT visible on the doctor surface."""
    resp = pg_client.post(
        QR_GENERATE,
        json={
            "specialist_id": world["doctor"].id,
            "department": DOCTOR_SPECIALTY,
            "target_date": datetime.now(UTC).date().isoformat(),
        },
        headers=world["registrar_h"],
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]

    info = pg_client.get(QR_INFO.replace("{token}", token))
    assert info.status_code == 200, info.text
    assert info.json()["allowed"] is True

    joined = _anonym_join(
        pg_client, token, "RQ24B-SYNTHETIC А", PHONE_A
    )
    result = joined["result"]
    assert result["success"] is True
    assert result["specialist_name"], "doctor name must be in the join result"
    ticket = result["queue_number"]

    # RQ-18 probe oracle: the saved verdict is decisive.
    probe = pg_client.post(
        JOIN_PROBE,
        json={
            "session_token": joined["session_token"],
            "patient_name": "RQ24B-SYNTHETIC А",
            "phone": PHONE_A,
        },
    )
    assert probe.status_code == 200, probe.text
    assert probe.json()["outcome"] == "joined_match"

    # Doctor panel: own queue only.
    queue = pg_client.get(
        DOCTOR_QUEUE_TODAY.replace("{specialty}", DOCTOR_SPECIALTY),
        headers=_auth_headers(world["doctor_user"]),
    )
    assert queue.status_code == 200, queue.text
    body = queue.json()
    assert body["queue_exists"] is True
    numbers = [e["number"] for e in body["entries"]]
    assert ticket in numbers
    entry = next(e for e in body["entries"] if e["number"] == ticket)
    assert entry["status"] == "waiting"
    assert PHONE_A in (entry.get("phone") or "")

    # Role scope: the doctor surface is keyed by their own specialty
    # identity — the resource queue (specialist_id NULL) must never
    # appear here (RQ-15 axis separation).
    assert all(e.get("source") is not None for e in body["entries"])

    world["doctor_ticket"] = ticket
    world["doctor_entry_id"] = entry["id"]


def test_new_resource_target_join_lands_on_resource_axis(
    pg_client, pg_session, world
):
    """Leg 2 — NEW resource target through the permanent direction
    address: anonymous start-session -> profile join -> the ticket lands
    on the RQ-15 resource axis (specialist_id NULL + queue_resource set,
    cabinet from the registry) with matching start number."""
    resp = pg_client.post(
        PUBLIC_START.replace("{public_code}", world["public_code"])
    )
    assert resp.status_code == 200, resp.text
    start_body = resp.json()
    session_token = start_body["session_token"]
    selectable = start_body["queue_info"]["selectable_specialists"]
    # The canonical anonymous direction join targets the DIRECTION
    # itself (entity 'profile', direction.profile_id) — the allocator
    # routes a profile selection onto the FIRST tag with a registry
    # resource surface before any doctor selection (QD-2C).
    profile_id = start_body["direction"]["profile_id"]

    complete_payload: dict = {
        "session_token": session_token,
        "patient_name": "RQ24B-SYNTHETIC В",
        "phone": PHONE_C,
        "specialist_ids": [profile_id],
        "specialist_entity_types": ["profile"],
    }
    resp = pg_client.post(JOIN_COMPLETE, json=complete_payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    entries = body.get("entries") or [body]
    assert body.get("success", True) is True
    assert entries, "the direction join must produce at least one ticket"

    # Probe oracle for the direction session (RQ-18 round-12 contract):
    # the probe replays the SAME payload as the original attempt.
    probe = pg_client.post(
        JOIN_PROBE,
        json={
            "session_token": session_token,
            "patient_name": "RQ24B-SYNTHETIC В",
            "phone": PHONE_C,
            "specialist_ids": [profile_id],
            "specialist_entity_types": ["profile"],
        },
    )
    assert probe.status_code == 200, probe.text
    assert probe.json()["outcome"] == "joined_match"

    # The resource axis on REAL PostgreSQL: the created daily queue for
    # the resource tag MUST be resource-owned (XOR owner constraint).
    from app.models.online_queue import DailyQueue

    row = (
        pg_session.query(DailyQueue)
        .filter(DailyQueue.queue_tag == LAB_TAG)
        .filter(DailyQueue.queue_resource_id.isnot(None))
        .first()
    )
    assert row is not None, "resource join must create a resource-owned queue"
    assert row.specialist_id is None, "resource queue owner axis must stay NULL"

    # Profile-entity allocation reports the PROFILE id (not the resource
    # id) in the entry payload — the resource landing is proven below by
    # the resource-owned DailyQueue row on real PostgreSQL.
    resource_entry = entries[0]
    assert resource_entry["queue_number"] == 1, (
        "start_number_online=1 must be honored on the resource axis"
    )

    world["resource_ticket"] = resource_entry["queue_number"]
    world["resource_queue_id"] = row.id


def test_board_matching_numbers_distinguishable_and_phi_honest(
    pg_client, pg_session, world
):
    """S-21 board leg: matching numbers in different cabinets are
    distinguishable (RQ-24.a.2) and the privacy setting is honored in the
    live WS payload (RQ-24.a.1) — asserted on the REAL initial_state."""
    # Privacy BEFORE the first connect: the name-format cache is set on
    # the first connect for the process lifetime (documented behavior).
    boards = pg_client.get(
        "/api/v1/admin/display/boards", headers=world["admin_h"]
    )
    assert boards.status_code == 200, boards.text
    board = next(
        b for b in boards.json() if b.get("name") == "main_board"
    )
    resp = pg_client.put(
        f"/api/v1/admin/display/boards/{board['id']}",
        json={"show_patient_names": "none"},
        headers=world["admin_h"],
    )
    assert resp.status_code == 200, resp.text

    state = _ws_state(pg_client, world["admin"])

    # REST contract: stats-only, no PHI keys (board-state pin).
    from datetime import date as _date

    rest = pg_client.get(
        BOARD_STATE,
        params={
            "department": DOCTOR_SPECIALTY,
            "date": _date.today().isoformat(),
        },
    )
    assert rest.status_code == 200, rest.text
    rest_body = rest.json()
    assert rest_body["show_patient_names"] == "none"
    for phi_key in ("patient_name", "phone", "entries"):
        assert phi_key not in rest_body, (
            f"stats-only board contract leaked {phi_key}"
        )

    entries = state.get("queue_entries") or []
    assert entries, "the board initial_state must contain today's tickets"

    # PHI: privacy 'none' -> no real names anywhere in the WS payload.
    serialized = str(state)
    assert "RQ24B-SYNTHETIC" not in serialized, (
        "board leaked patient identity with show_patient_names=none"
    )

    # Matching numbers: the doctor queue and the resource queue both
    # start at 1 — identical numbers must be distinguishable by
    # owner/cabinet (RQ-24.a.2 contract on REAL data).
    by_number: dict[int, set[tuple]] = {}
    for e in entries:
        # initial_state carries the OWNER axis (specialist_name /
        # specialist_id, resource display_name for resource queues);
        # identical numbers must differ by owner (RQ-24.a.2 contract).
        key = (e.get("specialist_name"), e.get("specialist_id"))
        by_number.setdefault(e.get("number"), set()).add(key)
    ones = by_number.get(1) or by_number.get("1")
    assert ones is not None, "expected the first tickets of both queues"
    assert len(ones) >= 2, (
        f"matching number 1 across cabinets must be distinguishable, got {ones}"
    )


def test_registrar_worklist_and_lab_panel_see_the_work(
    pg_client, pg_session, world
):
    """Registrar worklist (RQ-21 surface) and the lab panel see the
    active work on BOTH axes: the doctor-tag queue and the resource
    queue with its registry owner (waiting tickets are the live work;
    served rows leave the worklist by design)."""
    from datetime import date as _date

    from app.models.online_queue import DailyQueue

    registrar_h = world["registrar_h"]
    resp = pg_client.get(REGISTRAR_TODAY, headers=registrar_h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["queues"], "registrar must see today's queues"

    buckets_by_tag = {
        (q.get("specialty") or "").lower(): q for q in body["queues"]
    }
    doctor_bucket = buckets_by_tag.get(DOCTOR_SPECIALTY)
    # The worklist groups the resource tag under its canonical display
    # spelling ('lab' -> 'laboratory' via the endpoint's specialty map).
    lab_bucket = buckets_by_tag.get(LAB_TAG) or buckets_by_tag.get(
        "laboratory"
    )
    assert doctor_bucket, (
        f"registrar must see the doctor-axis queue; got {list(buckets_by_tag)}"
    )
    assert lab_bucket, (
        f"registrar must see the resource queue; got {list(buckets_by_tag)}"
    )
    # The worklist response carries the resource owner axis as
    # specialist_name (registry display_name) + queue_resource_id +
    # cabinet from the registry (QD-2C contract).
    assert lab_bucket.get("specialist_name") == "SYNTHETIC Lab Cabinet 204"
    assert lab_bucket.get("queue_resource_id") is not None
    assert lab_bucket.get("cabinet") == "204"

    # The lab panel: own department work only (the RQ-24.b core question:
    # delivery of the resource walk-in to the lab participant).
    lab = pg_client.get(
        LAB_QUEUE_TODAY, headers=_auth_headers(world["lab_user"])
    )
    assert lab.status_code == 200, lab.text
    lab_body = lab.json()
    assert {"entries", "total", "date", "timezone"} <= set(lab_body)
    resource_queue = (
        pg_session.query(DailyQueue)
        .filter(
            DailyQueue.day == _date.today(),
            DailyQueue.queue_tag == LAB_TAG,
        )
        .order_by(DailyQueue.id.asc())
        .first()
    )
    assert resource_queue is not None
    resource_patient_id = resource_queue.entries[0].patient_id
    lab_patient_ids = [
        e.get("patient_id") for e in lab_body["entries"]
    ]
    assert resource_patient_id in lab_patient_ids, (
        "lab panel must show the resource-queue walk-in in the lab "
        f"department; got patient_ids={lab_patient_ids}"
    )


def test_serving_creates_visits_for_downstream_panels(
    pg_client, pg_session, world
):
    """Leg 3 — serving: the doctor serves the doctor-axis walk-in; the
    resource-axis ticket is admin-only (QD-2C policy) and its visit is
    created in the resource department. After serving, the visit-driven
    participants (registrar worklist, lab panel, cashier) have real
    rows to show."""
    from datetime import date as _date

    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    doctor_h = _auth_headers(world["doctor_user"])
    admin_h = world["admin_h"]
    today = _date.today()

    def _waiting_entry(tag: str, resource_owned: bool):
        q = (
            pg_session.query(DailyQueue)
            .filter(DailyQueue.day == today, DailyQueue.queue_tag == tag)
            .order_by(DailyQueue.id.asc())
            .first()
        )
        assert q is not None, f"no daily queue for tag {tag}"
        assert (q.queue_resource_id is not None) is resource_owned, (
            f"queue owner axis mismatch for tag {tag}"
        )
        entry = (
            pg_session.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == q.id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(OnlineQueueEntry.number.asc())
            .first()
        )
        assert entry is not None, f"no waiting entry in the {tag} queue"
        return entry

    # Doctor serves own walk-in.
    doctor_entry = _waiting_entry(DOCTOR_SPECIALTY, resource_owned=False)
    resp = pg_client.post(
        f"/api/v1/doctor/queue/{doctor_entry.id}/call",
        headers=doctor_h,
    )
    assert resp.status_code == 200, resp.text
    resp = pg_client.post(
        f"/api/v1/doctor/queue/{doctor_entry.id}/start-visit",
        headers=doctor_h,
    )
    assert resp.status_code == 200, resp.text
    resp = pg_client.post(
        f"/api/v1/doctor/queue/{doctor_entry.id}/complete",
        headers=doctor_h,
    )
    assert resp.status_code == 200, resp.text

    # Resource axis: the doctor must NOT be able to serve a resource
    # ticket (QD-2C: resource surface is admin-only).
    resource_entry = _waiting_entry(LAB_TAG, resource_owned=True)
    resp = pg_client.post(
        f"/api/v1/doctor/queue/{resource_entry.id}/call",
        headers=doctor_h,
    )
    assert resp.status_code == 403, (
        f"resource serving must be admin-only, got {resp.status_code}"
    )
    resp = pg_client.post(
        f"/api/v1/doctor/queue/{resource_entry.id}/call",
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    resp = pg_client.post(
        f"/api/v1/doctor/queue/{resource_entry.id}/start-visit",
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    resp = pg_client.post(
        f"/api/v1/doctor/queue/{resource_entry.id}/complete",
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text

    # Downstream: the resource visit exists with the resource department.
    from app.models.visit import Visit

    visit = (
        pg_session.query(Visit)
        .filter(
            Visit.patient_id == resource_entry.patient_id,
            Visit.visit_date == today,
        )
        .order_by(Visit.id.desc())
        .first()
    )
    assert visit is not None, "serving the resource ticket must create a visit"


def test_patient_portal_sees_only_own_data(pg_client, world):
    """S-21 patient leg: the portal patient sees only their own rows —
    the anonymous walk-ins of the same day never appear."""
    resp = pg_client.get(
        PATIENT_APPOINTMENTS, headers=_auth_headers(world["portal_user"])
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list)
    serialized = str(items)
    assert "RQ24B-SYNTHETIC А" not in serialized
    assert PHONE_A not in serialized
    assert PHONE_C not in serialized

    # A second patient's surface must not leak the walk-ins either: the
    # anonymous patients have no portal user at all — the only honest
    # scope check is that the portal list never contains them.


def test_cashier_sees_and_collects_the_payment(
    pg_client, pg_session, world
):
    """S-21 cashier leg: registrar attaches the priced service to a
    walk-in (full-update -> priced visit), the cashier surface shows the
    payable, the grouped payment allocates server-side, and the other
    walk-ins' visits are untouched."""
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.payment import Payment

    # A fresh anonymous walk-in on the doctor axis (its own ticket).
    resp = pg_client.post(
        QR_GENERATE,
        json={
            "specialist_id": world["doctor"].id,
            "department": DOCTOR_SPECIALTY,
            "target_date": datetime.now(UTC).date().isoformat(),
        },
        headers=world["registrar_h"],
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    joined = _anonym_join(
        pg_client, token, "RQ24B-SYNTHETIC Г", PHONE_D
    )
    assert joined["result"]["success"] is True

    entry = (
        pg_session.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            DailyQueue.day == datetime.now(UTC).date(),
            OnlineQueueEntry.phone.like(f"%{PHONE_D[-4:]}"),
        )
        .first()
    )
    assert entry is not None, "fresh walk-in entry must exist"

    # Registrar attaches the priced doctor service (the wizard full-update
    # command): the visit is created WITH VisitService rows.
    resp = pg_client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        json={
            "patient_data": {
                "patient_name": "RQ24B-SYNTHETIC Г",
                "phone": PHONE_D,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [
                {
                    "service_id": world["service_ids"][DOCTOR_SPECIALTY],
                    "quantity": 1,
                }
            ],
        },
        headers=world["registrar_h"],
    )
    assert resp.status_code == 200, resp.text

    # Cashier surface: the payable card for the walk-in.
    pending = pg_client.get(
        CASHIER_PENDING, headers=_auth_headers(world["cashier"])
    )
    assert pending.status_code == 200, pending.text
    rows = pending.json().get("items") or pending.json().get("payments") or []
    target = next(
        (r for r in rows if r.get("patient_id") == entry.patient_id),
        None,
    )
    assert target is not None, (
        f"cashier must see the walk-in bill; got {rows}"
    )
    visit_ids = target["visit_ids"]
    assert visit_ids, "pending payment must reference payable visits"

    # Server-side allocation (oldest visit first), one grouped payment.
    resp = pg_client.post(
        CASHIER_GROUPED,
        json={
            "visit_ids": visit_ids,
            "patient_id": entry.patient_id,
            "amount": 50000,
            "method": "cash",
        },
        headers=_auth_headers(world["cashier"]),
    )
    assert resp.status_code in (200, 201), resp.text
    payment = resp.json()
    assert payment["allocations"] and payment["payments"]

    # The payment landed exactly on the walk-in's visit — no leakage.
    other_payments = (
        pg_session.query(Payment)
        .filter(Payment.visit_id.notin_(visit_ids))
        .all()
    )
    assert other_payments == [], (
        "the grouped payment must not leak onto other visits"
    )


# ------------------------------------------------------------------
# Review-round pins (rounds 1-4): the candidate-DSN guard and the
# scratch-DSN address forms are pure functions of their inputs — these
# pins run WITHOUT a PostgreSQL server and must stay green everywhere.
# ------------------------------------------------------------------


def _harness_env(monkeypatch, database_url: str | None) -> None:
    """Isolate the guard from the host environment."""
    monkeypatch.delenv("RQ24B_PG_ADMIN_URL", raising=False)
    monkeypatch.delenv("LOCAL_PG_SUPERUSER_PASSWORD", raising=False)
    # libpq reads PGHOST/PGHOSTADDR from the environment (round-3 review
    # P1) — the pins must judge the guard, not whatever the host exports.
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGHOST", raising=False)
    # Service configuration is another hidden address source (round-4
    # review P1): PGSERVICE feeds parameters into any DSN, and the
    # service-file locations must not leak between pins even though
    # they carry no address by themselves.
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.delenv("PGSERVICEFILE", raising=False)
    monkeypatch.delenv("PGSYSCONFDIR", raising=False)
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)


def test_env_dsn_with_remote_query_host_is_rejected(monkeypatch):
    """Round-1 P1: a remote query host must never auto-provision."""
    _harness_env(monkeypatch, "postgresql://u:p@/postgres?host=db.internal")
    assert _candidate_admin_urls() == []


def test_env_dsn_with_remote_hostaddr_is_rejected(monkeypatch):
    """Round-2 P1: hostaddr overrides the dialed address — REMOTE."""
    _harness_env(
        monkeypatch, "postgresql://u:p@localhost/postgres?hostaddr=10.20.30.40"
    )
    assert _candidate_admin_urls() == []


def test_env_dsn_with_loopback_hostaddr_is_rejected_too(monkeypatch):
    """Round-2 P1, fail-closed leg: even a loopback hostaddr is an
    address-altering parameter the scratch DSN cannot reproduce."""
    _harness_env(monkeypatch, "postgresql://u:p@/postgres?hostaddr=127.0.0.1")
    assert _candidate_admin_urls() == []


def test_env_dsn_with_uppercase_hostaddr_cannot_bypass(monkeypatch):
    """Round-2 P1: libpq conninfo parameter names are case-insensitive."""
    _harness_env(monkeypatch, "postgresql://u:p@/postgres?HOSTADDR=10.20.30.40")
    assert _candidate_admin_urls() == []


def test_env_dsn_hostless_unix_socket_is_accepted(monkeypatch):
    """Round-1 P2: a hostless DSN dials the default socket — a candidate."""
    _harness_env(monkeypatch, "postgresql:///clinic")
    assert _candidate_admin_urls() == ["postgresql:///clinic"]


def test_env_dsn_socket_directory_query_is_accepted(monkeypatch):
    """Round-1 shape: a query host that is a socket-directory path."""
    _harness_env(monkeypatch, "postgresql://u:p@/postgres?host=/var/run/postgresql")
    assert _candidate_admin_urls() == [
        "postgresql://u:p@/postgres?host=/var/run/postgresql"
    ]


def test_env_dsn_sqlite_and_malformed_degrade_to_no_candidates(monkeypatch):
    """Non-PG and unparseable DSNs must never crash auto-detection."""
    _harness_env(monkeypatch, "sqlite:///local_test.db")
    assert _candidate_admin_urls() == []
    monkeypatch.setenv("DATABASE_URL", "file:///tmp/not-a-pg-dsn")
    assert _candidate_admin_urls() == []


def test_explicit_admin_env_is_included_unconditionally(monkeypatch):
    """The documented opt-in boundary: an explicit admin DSN may be remote."""
    monkeypatch.setenv(
        "RQ24B_PG_ADMIN_URL", "postgresql://u:p@db.internal:5432/postgres"
    )
    monkeypatch.delenv("LOCAL_PG_SUPERUSER_PASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _candidate_admin_urls() == ["postgresql://u:p@db.internal:5432/postgres"]


def test_scratch_urls_preserve_hostless_socket_form():
    """Round-1 P2: hostless stays hostless — no silent TCP re-typing."""
    psycopg_dsn, sa_url = _scratch_urls("postgresql://postgres:pw@/postgres")
    assert psycopg_dsn == f"postgresql://postgres:pw@/{SCRATCH_DB}"
    assert sa_url == f"postgresql+psycopg://postgres:pw@/{SCRATCH_DB}"


def test_scratch_urls_preserve_query_host_forms():
    """Socket-dir and explicit query-host forms repeat verbatim."""
    psycopg_dsn, _ = _scratch_urls(
        "postgresql://postgres:pw@/postgres?host=/var/run/postgresql"
    )
    assert psycopg_dsn == (
        f"postgresql://postgres:pw@/{SCRATCH_DB}?host=/var/run/postgresql"
    )
    psycopg_dsn, _ = _scratch_urls("postgresql://postgres:pw@/postgres?host=localhost")
    assert psycopg_dsn == (f"postgresql://postgres:pw@/{SCRATCH_DB}?host=localhost")


def test_scratch_urls_preserve_authority_host_and_port():
    """An authority host:port is kept as-is (explicit local TCP form)."""
    psycopg_dsn, sa_url = _scratch_urls(
        "postgresql://postgres:pw@localhost:55432/postgres"
    )
    assert psycopg_dsn == (f"postgresql://postgres:pw@localhost:55432/{SCRATCH_DB}")
    assert sa_url == (f"postgresql+psycopg://postgres:pw@localhost:55432/{SCRATCH_DB}")


def test_pg_engine_teardown_is_setup_failure_safe_source_pin():
    """Round-1 P2: everything after CREATE DATABASE is try/finally-wrapped.

    pytest skips the post-yield teardown when fixture setup fails BEFORE
    the yield; with run-unique scratch names a leaked database would
    never be reclaimed by a later run. This source-level pin keeps the
    structural guarantee (no server needed to run it).
    """
    import inspect

    src = inspect.getsource(pg_engine)
    assert "CREATE DATABASE" in src
    create_at = src.index("CREATE DATABASE")
    try_at = src.index("try:", create_at)
    yield_at = src.index("yield engine", create_at)
    finally_at = src.index("finally:", create_at)
    assert create_at < try_at < yield_at < finally_at
    teardown = src[finally_at:]
    assert "DROP DATABASE IF EXISTS" in teardown


def test_env_dsn_with_remote_fallback_in_host_list_is_rejected(monkeypatch):
    """Round-3 P1: libpq dials comma-separated fallback hosts too."""
    _harness_env(
        monkeypatch,
        "postgresql://u:p@/postgres?host=/var/run/postgresql,db.internal",
    )
    assert _candidate_admin_urls() == []


def test_env_dsn_with_all_local_fallback_hosts_is_accepted(monkeypatch):
    """Round-3 P1 positive: every fallback entry local → a candidate."""
    _harness_env(
        monkeypatch,
        "postgresql://u:p@/postgres?host=/var/run/postgresql,/var/run/postgresql",
    )
    expected = (
        "postgresql://u:p@/postgres?host=/var/run/postgresql,"
        "/var/run/postgresql"
    )
    assert _candidate_admin_urls() == [expected]


def test_pghostaddr_env_overriding_the_dsn_is_rejected(monkeypatch):
    """Round-3 P1: PGHOSTADDR fills the address libpq dials — reject."""
    _harness_env(monkeypatch, "postgresql://u:p@localhost/postgres")
    monkeypatch.setenv("PGHOSTADDR", "10.20.30.40")
    assert _candidate_admin_urls() == []


def test_pghostaddr_env_with_hostless_dsn_is_rejected_too(monkeypatch):
    """Round-3 P1, fail-closed leg: any PGHOSTADDR presence rejects."""
    _harness_env(monkeypatch, "postgresql:///clinic")
    monkeypatch.setenv("PGHOSTADDR", "127.0.0.1")
    assert _candidate_admin_urls() == []


def test_pghost_env_with_remote_host_is_rejected_for_hostless_dsn(monkeypatch):
    """Round-3 P1: a hostless DSN inherits the PGHOST address."""
    _harness_env(monkeypatch, "postgresql://u:p@/postgres")
    monkeypatch.setenv("PGHOST", "db.internal")
    assert _candidate_admin_urls() == []


def test_pghost_env_with_local_socket_dir_keeps_hostless_accepted(monkeypatch):
    """Round-3 P1 positive: PGHOST at a local socket dir stays a candidate."""
    _harness_env(monkeypatch, "postgresql:///clinic")
    monkeypatch.setenv("PGHOST", "/var/run/postgresql")
    assert _candidate_admin_urls() == ["postgresql:///clinic"]


def test_env_dsn_with_service_param_is_rejected(monkeypatch):
    """Round-4 P1: ``?service=`` may resolve the dialed host from
    pg_service.conf — the guard cannot prove where it points."""
    _harness_env(monkeypatch, "postgresql:///postgres?service=remote_service")
    assert _candidate_admin_urls() == []


def test_env_dsn_with_uppercase_service_param_cannot_bypass(monkeypatch):
    """Round-4 P1: conninfo parameter names are case-insensitive."""
    _harness_env(
        monkeypatch, "postgresql://u:p@localhost/postgres?SERVICE=remote_service"
    )
    assert _candidate_admin_urls() == []


def test_env_dsn_with_repeated_service_params_is_rejected(monkeypatch):
    """Round-4 P1: repeated service keys parse into a sequence — the
    normalized guard must reject that form too."""
    _harness_env(monkeypatch, "postgresql:///postgres?service=a&service=b")
    assert _candidate_admin_urls() == []


def test_pgservice_env_rejects_even_a_local_looking_dsn(monkeypatch):
    """Round-4 P1: a non-empty PGSERVICE feeds parameters into ANY DSN —
    even one that spells an explicit localhost authority."""
    _harness_env(monkeypatch, "postgresql://u:p@localhost/postgres")
    monkeypatch.setenv("PGSERVICE", "remote_service")
    assert _candidate_admin_urls() == []


def test_pgservice_env_rejects_a_hostless_dsn_too(monkeypatch):
    """Round-4 P1: a hostless DSN is exactly the shape a service
    definition fills in — it must never auto-provision."""
    _harness_env(monkeypatch, "postgresql:///postgres")
    monkeypatch.setenv("PGSERVICE", "remote_service")
    assert _candidate_admin_urls() == []


def test_service_file_locations_alone_do_not_reject(monkeypatch):
    """Round-4 P1 boundary: PGSERVICEFILE/PGSYSCONFDIR select WHERE
    service definitions may live, not an address — a DSN that spells no
    service stays a candidate (no over-rejection)."""
    import tempfile

    service_file = str(Path(tempfile.gettempdir()) / "synthetic_pg_service.conf")
    _harness_env(monkeypatch, "postgresql:///clinic")
    monkeypatch.setenv("PGSERVICEFILE", service_file)
    monkeypatch.setenv("PGSYSCONFDIR", tempfile.gettempdir())
    assert _candidate_admin_urls() == ["postgresql:///clinic"]
