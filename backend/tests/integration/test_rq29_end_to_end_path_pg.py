"""
RQ-29 — the final combined scenario of the new queue system (plan §RQ-29,
ACCEPTANCE «Сквозная приемка RQ-29»): the admin connects a doctor of an
EXISTING specialty, a NEW direction and a doctorless resource; adds
services and composition and returns to editing; the registrar finds the
patient and saves the wizard cart — fixing the refused required-doctor
link on the way; the patient records through the direction's QR while
ONE extra choice refuses and the partial result stays visible; the
ticket reaches the right performer; numbers/cabinets are consistent
across registrar/patient/board; the repeated command and the second
session lose nothing; archiving the direction closes future joins and
preserves today's queue/history; a supported partial payment and a
partial service cancellation lose no other assignment.

Per the plan Commit Plan line («RQ-29: тесты объединенного пути;
исправления найденных дефектов возвращаются владельцу, статус родителя
остается незавершенным») this is a VERIFICATION slice: the application
runtime is consumed, never modified. A found defect is registered for
the owner, not fixed here.

Honest NOT_RUN: the browser half of the path (ACCEPTANCE step 10 —
keyboard and 375/768/1280/1920 px viewports, plus the visual halves of
every participant screen). No disposable staging/browser harness exists
in this sandbox; the backend-verifiable substance of steps 1–9 is
pinned here on the REAL FastAPI app + disposable PostgreSQL, and the
mock e2e specs (frontend/e2e/registrar-workflow.spec.ts,
registrar-ux-audit.spec.ts, queue-system.spec.ts) stay classified MOCK —
by the ACCEPTANCE preamble they do not close this section by
themselves. The RQ-29 DONE decision (full original volume: S-01…S-28
PASS with evidence) belongs to the owner and is recorded in PROGRESS
E-072.

All data is SYNTHETIC (``rq29-``/``SYNTHETIC-`` markers, disposable
scratch database). Disposable PostgreSQL: the module provisions its own
scratch database (``rq29_check_<hex>``, unique per run), runs
``alembic upgrade head`` and drops it at the end; skips (NOT_RUN, plan
P0) when no disposable PostgreSQL server is reachable. ``DATABASE_URL``
is accepted for automatic provisioning only for local servers — the
same fail-closed guard as the merged rq24b/rq26b harnesses: an
explicit loopback host, a hostless unix-socket DSN, or a ``?host=``
that is a socket-directory path or a loopback name; hidden address
sources (``?hostaddr=``, a remote ``?host=`` entry — including inside
a comma-separated fallback list — an address-overriding
``PGHOSTADDR``/``PGSERVICE`` environment, or a ``?service=`` reference)
are rejected, so a remote admin DSN must be passed explicitly via the
test-owned ``RQ29_PG_ADMIN_URL``. SQLite is never a substitute here.
The HTTP surfaces run through the real FastAPI app (TestClient) against
that scratch database; the display-board WebSocket is exercised through
the real WS endpoint (JWT required, ``initial_state`` on connect).

Modelled on tests/integration/test_rq24b_cross_panel_s21_pg.py (the
merged real-PG cross-panel harness precedent) and
tests/integration/test_rq26b_csv_lifecycle_contract_pg.py (the profile
PUT/archive contract precedent).

ONE continuous test (owner review round 1): the whole combined path
(world setup + steps 2-9) runs inside a single pytest test —
``test_rq29_combined_path`` — and the step artifacts flow through
explicit arguments and return values. There is NO module-level
cross-test carry and NO hidden pytest-order dependence: the module
holds exactly one test, so collection order, ``-k`` targeted execution
and ``xdist`` distribution cannot desynchronize the scenario.

Run::

    cd backend && DATABASE_URL=postgresql+psycopg://clinic:pw@localhost:5432/clinicdb \
        pytest tests/integration/test_rq29_end_to_end_path_pg.py -q
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

# Unique per run (the rq26b/rq24b scratch-isolation class fix): a fixed
# name with an unconditional pre-drop let parallel runs drop each other's
# database. Cleanup drops ONLY the database this run created.
SCRATCH_DB = f"rq29_check_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))

pytestmark = pytest.mark.integration

# ---- canonical routes under test (combined-path participants) ----
ADMIN_DOCTORS = "/api/v1/admin/doctors"
SERVICES_PATH = "/api/v1/services"
PATIENTS_PATH = "/api/v1/patients"
CART_PATH = "/api/v1/registrar/cart"
CART_QUOTE = "/api/v1/registrar/cart/quote"
RESOURCE_CREATE = "/api/v1/queue/admin/queue-resources"
PROVISION = "/api/v1/queue/admin/directions/{profile_key}/public-address/provision"
PUBLIC_START = "/api/v1/queue/public/{public_code}/start-session"
ENTRY_METHODS = "/api/v1/queue/directions/{profile_key}/entry-methods"
QR_GENERATE = "/api/v1/queue/admin/qr-tokens/generate"
JOIN_START = "/api/v1/queue/join/start"
JOIN_COMPLETE = "/api/v1/queue/join/complete"
JOIN_PROBE = "/api/v1/queue/join/probe"
DOCTOR_QUEUE_TODAY = "/api/v1/doctor/{specialty}/queue/today"
LAB_QUEUE_TODAY = "/api/v1/lab/queue/today"
REGISTRAR_TODAY = "/api/v1/registrar/queues/today"
CASHIER_PENDING = "/api/v1/cashier/pending-payments"
CASHIER_GROUPED = "/api/v1/cashier/payments/grouped"
ONLINE_ENTRY_FULL_UPDATE = "/api/v1/queue/online-entry/{entry_id}/full-update"
ONLINE_ENTRY_CANCEL_SERVICE = "/api/v1/queue/online-entry/{entry_id}/cancel-service"
PROFILES_PATH = "/api/v1/queues/profiles"
WS_BOARD = "/api/v1/display/ws/board/main_board"
DIRECTION_REFUSAL_DETAIL = "Направление недоступно"

# Catalog 0051 canonical codes (active seed): the admin doctors API
# refuses unknown codes — the combined path must connect a doctor of an
# EXISTING specialty, exactly as ACCEPTANCE step 1 spells out.
DOCTOR_SPECIALTY = "cardiology"
OTHER_SPECIALTY = "dermatology"
LAB_TAG = "lab"
DIRECTION_KEY = "rq29-synthetic"
PHONE_MAIN = "998501002001"  # SYNTHETIC cart patient
PHONE_WALKIN = "998501002002"  # SYNTHETIC direction-QR walk-in
PHONE_CANCEL = "998501002003"  # SYNTHETIC cancel-leg walk-in


# ------------------------------------------------------------------
# disposable PostgreSQL harness (scratch DB + alembic head)
# ------------------------------------------------------------------


def _candidate_admin_urls() -> list[str]:
    """Plain-psycopg admin DSNs — LOCAL servers only (rq24b/rq26b guard).

    ``DATABASE_URL`` in CI is a SQLAlchemy URL (``postgresql+psycopg://``);
    psycopg.connect rejects the driver suffix, so the scheme is normalized
    for the admin connection. The scratch database must never be
    provisioned — or dropped — on a remote server reachable through a
    plain ``DATABASE_URL``: auto-detected candidates are accepted only for
    LOCAL servers, judged by the address libpq actually dials, not by the
    URL spelling. ``?hostaddr=`` and ``?service=`` query parameters are
    rejected outright (address-altering / service-resolved at connect
    time), an address-overriding ``PGHOSTADDR``/``PGSERVICE`` environment
    rejects every candidate shape, and ``?host=``/``PGHOST`` comma-
    separated fallback lists are judged element-wise (a remote fallback
    makes the candidate remote). A remote admin DSN must be passed
    explicitly via the test-owned ``RQ29_PG_ADMIN_URL``.
    """
    urls: list[str] = []

    def _normalized(raw: str) -> str:
        return raw.replace("postgresql+psycopg://", "postgresql://", 1)

    def _env_can_re_dial() -> bool:
        """True when the environment can re-dial a DSN's address.

        libpq fills omitted connection fields from the environment; with
        both ``host`` and ``hostaddr`` present libpq dials ``hostaddr``,
        and a service name may inject any unspelled parameter. Any
        non-empty value of either rejects (fail-closed).
        """
        return bool(os.getenv("PGHOSTADDR", "").strip()) or bool(
            os.getenv("PGSERVICE", "").strip()
        )

    def _is_local(url: str) -> bool:
        """True only for addresses libpq dials locally."""
        try:
            u = make_url(url)
        except Exception:  # noqa: BLE001 — a malformed env DSN must
            # degrade to "not a local PG candidate", never crash the
            # auto-detection.
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

        # Normalize query params: libpq matches conninfo parameter names
        # case-insensitively and SQLAlchemy parses repeated keys into
        # sequences — the guard must not be bypassable by spelling or
        # duplication.
        qvals: dict[str, list[str]] = {}
        for k, v in (u.query or {}).items():
            vals = v if isinstance(v, (list, tuple)) else [v]
            qvals.setdefault(str(k).lower(), []).extend(str(x) for x in vals)
        if qvals.get("hostaddr"):
            return False  # address-altering parameter — fail-closed
        if qvals.get("service"):
            return False  # service contract unresolved — fail-closed
        if _env_can_re_dial():
            return False
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
        # dials the default unix-socket directory — local by definition.
        return True

    explicit = os.getenv("RQ29_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(_normalized(explicit))
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw and not _env_can_re_dial():
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url and _is_local(_normalized(env_url)):
        urls.append(_normalized(env_url))
    return urls


def _dsn_parts(admin_url: str) -> dict:
    """Split a DSN into libpq address parts WITHOUT re-typing the host.

    The address mode is preserved verbatim (rq24b review P2): a hostless
    DSN must stay hostless — substituting ``"localhost"`` would silently
    switch the scratch connection from the unix socket to TCP.
    """
    from urllib.parse import parse_qs, urlparse

    p = urlparse(admin_url)
    q = parse_qs(p.query)
    qhost = (q.get("host") or [None])[0]
    return {
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
        base_p = f"postgresql://{userinfo}@/{SCRATCH_DB}?host={parts['qhost']}"
        base_s = f"postgresql+psycopg://{userinfo}@/{SCRATCH_DB}?host={parts['qhost']}"
        return base_p, base_s
    if not parts["host"]:
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
            f"disposable PostgreSQL unavailable — RQ-29 PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    # No pre-drop: the name is unique per run, so a leftover database can
    # never be silently reused — a name collision fails loudly instead.
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

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
            "RQ-29 proof requires real PostgreSQL"
        )

        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        # Disposable-DB teardown: force-close any backend still attached
        # to the scratch database, then drop it.
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
    """Deterministic clinic day for the combined path (rq24b precedent).

    The product resolves the queue day from clinic settings (default
    Asia/Tashkent, online cutoff 09:00): after the cutoff an anonymous
    join targets TOMORROW while staff surfaces read host
    ``date.today()`` — the participants would look at different days
    depending on the wall clock of the CI run. The harness pins the
    queue settings SSOT (timezone=UTC, cutoff=24 -> never shifts) so
    every participant surface resolves the SAME day deterministically.
    Singleton caches are swapped via monkeypatch so the ORIGINAL values
    are restored after every test — no state leaks into later suites.
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

    import app.services.queue_service as queue_service_module

    monkeypatch.setattr(queue_service_module.queue_service, "_cached_settings", None)

    from app.services.display_websocket import get_display_manager

    monkeypatch.setattr(get_display_manager(), "_name_format_cache", {})


@pytest.fixture
def pg_client(pg_session, monkeypatch):
    """TestClient wired to the disposable PostgreSQL session (rq24b)."""
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
    from app.db import session as app_db_session

    try:
        app_db_session.engine.dispose()
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------
# synthetic world helpers
# ------------------------------------------------------------------


def _get_or_create_user(session, username: str, role: str):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        # AGENTS.md PII rules: synthetic users carry no email at all.
        email=None,
        full_name=f"RQ-29 {username}",
        hashed_password=get_password_hash("rq29-synthetic-pw"),
        role=role,
        is_active=True,
        is_superuser=role == "Admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth_headers(user) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _ws_state(pg_client, user, board_id: str = "main_board") -> dict:
    """One REAL websocket session: initial_state on connect."""
    from tests.conftest import mint_access_token

    jwt = mint_access_token(user)
    with pg_client.websocket_connect(
        WS_BOARD,
        headers={"Authorization": f"Bearer {jwt}"},
    ) as ws:
        message = ws.receive_json()
    assert message["type"] == "initial_state", message.get("type")
    return message["data"]


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


# ------------------------------------------------------------------
# SYNTHETIC world — ACCEPTANCE steps 1-2 through the REAL admin API
# wherever the merged flow has one (doctor, resource, direction
# provision, service edit, patient search/create); model seeds only
# where the merged rq16d/rq24b precedent seeds (Service.requires_doctor/
# queue_tag and QueueProfile are model columns without a public DTO).
# ------------------------------------------------------------------


@pytest.fixture
def world(pg_session, pg_client):
    from decimal import Decimal

    from app.models.queue_profile import QueueProfile
    from app.models.service import Service

    admin = _get_or_create_user(pg_session, "rq29_admin", "Admin")
    registrar = _get_or_create_user(pg_session, "rq29_registrar", "Registrar")
    doctor_user = _get_or_create_user(pg_session, "rq29_doc", "Doctor")
    other_doctor_user = _get_or_create_user(pg_session, "rq29_doc2", "Doctor")
    lab_user = _get_or_create_user(pg_session, "rq29_lab", "Lab")
    cashier = _get_or_create_user(pg_session, "rq29_cashier", "Cashier")

    admin_h = _auth_headers(admin)
    registrar_h = _auth_headers(registrar)

    # --- STEP 1 (REAL API): doctor of an EXISTING specialty ---------
    for _username, user, specialty, cabinet in (
        ("rq29_doc", doctor_user, DOCTOR_SPECIALTY, "301"),
        ("rq29_doc2", other_doctor_user, OTHER_SPECIALTY, "302"),
    ):
        resp = pg_client.post(
            ADMIN_DOCTORS,
            json={
                "user_id": user.id,
                "specialty": specialty,
                "cabinet": cabinet,
                "active": True,
            },
            headers=admin_h,
        )
        if resp.status_code == 400 and "уже привязан" in resp.text:
            # idempotent world guard (the branches make the world safe
            # to rebuild; a run gets a fresh scratch DB either way)
            continue
        assert resp.status_code in (200, 201), resp.text
        body = resp.json()
        assert body["specialty"] == specialty, body

    # --- services (model seed — merged rq16d/rq24b precedent) -------
    # BEFORE the resource activation: the RQ-17 §3.1 gate proves the tag
    # doctorless from an existing requires_doctor=False service on it.
    service_specs = {
        "consult": {
            "code": "SYNTHETIC-rq29-consult",
            "name": "SYNTHETIC RQ-29 consultation",
            "price": Decimal("50000"),
            "requires_doctor": True,
            "queue_tag": DOCTOR_SPECIALTY,
            "department_key": DOCTOR_SPECIALTY,
        },
        "extended": {
            "code": "SYNTHETIC-rq29-extended",
            "name": "SYNTHETIC RQ-29 extended consultation",
            "price": Decimal("40000"),
            "requires_doctor": True,
            "queue_tag": DOCTOR_SPECIALTY,
            "department_key": DOCTOR_SPECIALTY,
        },
        "labtest": {
            "code": "SYNTHETIC-rq29-labtest",
            "name": "SYNTHETIC RQ-29 lab test",
            "price": Decimal("30000"),
            "requires_doctor": False,
            "queue_tag": LAB_TAG,
            "department_key": LAB_TAG,
        },
    }
    service_ids: dict[str, int] = {}
    for spec in service_specs.values():
        row = pg_session.query(Service).filter(Service.code == spec["code"]).first()
        if not row:
            row = Service(
                code=spec["code"],
                name=spec["name"],
                price=spec["price"],
                active=True,
                requires_doctor=spec["requires_doctor"],
                queue_tag=spec["queue_tag"],
                department_key=spec["department_key"],
            )
            pg_session.add(row)
            pg_session.commit()
            pg_session.refresh(row)
        service_ids[spec["code"].rsplit("-", 1)[-1]] = row.id

    # --- STEP 1 (REAL API): doctorless resource + RQ-17 gate --------
    resp = pg_client.post(
        RESOURCE_CREATE,
        json={
            "code": "SYNTHETIC-rq29-lab-cab",
            "queue_tag": LAB_TAG,
            "display_name": "SYNTHETIC RQ-29 Lab Cabinet 204",
            "start_number_online": 1,
            "max_online_per_day": 15,
            "default_cabinet": "204",
            "active": False,
        },
        headers=admin_h,
    )
    if resp.status_code == 409:
        listing = pg_client.get(RESOURCE_CREATE, headers=admin_h)
        assert listing.status_code == 200, listing.text
        rows = listing.json()
        if isinstance(rows, dict):
            rows = rows.get("items") or rows.get("resources") or []
        resource = next(
            r for r in rows if r.get("code") == "SYNTHETIC-rq29-lab-cab"
        )
    else:
        assert resp.status_code == 201, resp.text
        resource = resp.json()
    resp = pg_client.patch(
        f"{RESOURCE_CREATE}/{resource['id']}",
        json={"active": True},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    # Refresh the world's snapshot: the create/listing response predates
    # the activation gate PATCH.
    listing = pg_client.get(RESOURCE_CREATE, headers=admin_h)
    assert listing.status_code == 200, listing.text
    rows = listing.json()
    if isinstance(rows, dict):
        rows = rows.get("items") or rows.get("resources") or []
    resource = next(
        r for r in rows if r.get("code") == "SYNTHETIC-rq29-lab-cab"
    )
    assert resource["active"] is True, resource

    # --- direction (model seed per rq24b) + permanent address -------
    stale = pg_session.query(QueueProfile).filter(QueueProfile.key == DIRECTION_KEY).all()
    for profile in stale:
        pg_session.delete(profile)
    pg_session.commit()
    profile = QueueProfile(
        key=DIRECTION_KEY,
        title="RQ-29 synthetic direction",
        title_ru="RQ-29 синтетическое направление",
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
        m for m in methods["entry_methods"] if m["method"] == "permanent_address"
    )

    resp = pg_client.post(
        PROVISION.replace("{profile_key}", DIRECTION_KEY), headers=admin_h
    )
    assert resp.status_code == 200, resp.text
    provisioned = resp.json()
    assert provisioned["created"] is True
    assert provisioned["url_path"] == f"/q/{provisioned['public_code']}"

    # AFTER provisioning the permanent address must be offered as
    # supported (the before-provision snapshot stays for the record).
    resp = pg_client.get(ENTRY_METHODS.replace("{profile_key}", DIRECTION_KEY))
    assert resp.status_code == 200, resp.text
    permanent_after = next(
        m
        for m in resp.json()["entry_methods"]
        if m["method"] == "permanent_address"
    )

    # --- registrar patient book (REAL API search -> create) ---------
    resp = pg_client.get(
        PATIENTS_PATH, params={"q": "+998501002001"}, headers=registrar_h
    )
    assert resp.status_code == 200, resp.text
    found = [p for p in resp.json() if (p.get("phone") or "").endswith(PHONE_MAIN)]
    if found:
        patient = found[0]
    else:
        resp = pg_client.post(
            PATIENTS_PATH,
            json={
                "last_name": "RQ29-SYNTHETIC",
                "first_name": "Виктор",
                "phone": "+998501002001",
            },
            headers=registrar_h,
        )
        assert resp.status_code in (200, 201), resp.text
        patient = resp.json()

    return {
        "admin": admin,
        "registrar": registrar,
        "doctor_user": doctor_user,
        "other_doctor_user": other_doctor_user,
        "lab_user": lab_user,
        "cashier": cashier,
        "service_ids": service_ids,
        "resource": resource,
        "profile": profile,
        "public_code": provisioned["public_code"],
        "permanent_supported_before_provision": permanent["supported"],
        "permanent_supported": permanent_after["supported"],
        "patient": patient,
        "admin_h": admin_h,
        "registrar_h": registrar_h,
    }


# === RQ-29 combined-path step helpers (the ONE continuous test at the
# bottom of the module calls them in order, passing state explicitly) ===


def _step1_admin_setup_and_direction_are_reachable(world):
    """Steps 1-2 of the combined path: the REAL admin API connected a
    doctor of an EXISTING catalog specialty (0051), a doctorless resource
    with the RQ-17 activation gate, and the NEW direction's permanent
    address; the direction offers the bookable entry methods."""
    # The permanent address became supported AFTER provisioning (the
    # world records both snapshots).
    assert world["permanent_supported"] is True
    assert world["public_code"]
    # The catalog gate accepted both doctors (asserted in world); the
    # resource is active with its registry cabinet.
    assert world["resource"]["active"] is True
    assert world["resource"]["default_cabinet"] == "204"


def _step2_admin_edits_service_and_registrar_finds_patient(
    pg_client, world
):
    """Steps 2-3 of the combined path: the admin RETURNS TO EDITING the
    service through the REAL services API (price fix), and the registrar
    finds the patient (empty search for an unknown phone, the created
    patient found by the synthetic name)."""
    admin_h = world["admin_h"]
    registrar_h = world["registrar_h"]
    consult_id = world["service_ids"]["consult"]

    # Admin edit through the REAL DTO: 50000 -> 60000.
    resp = pg_client.put(
        f"{SERVICES_PATH}/{consult_id}",
        json={"price": 60000.0},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    assert float(resp.json()["price"]) == 60000.0, resp.text

    # The registrar finds the patient: empty search first, then the hit.
    resp = pg_client.get(
        PATIENTS_PATH, params={"q": "+998501009999"}, headers=registrar_h
    )
    assert resp.status_code == 200, resp.text
    assert all(
        not (p.get("phone") or "").endswith("+998501009999") for p in resp.json()
    )
    resp = pg_client.get(
        PATIENTS_PATH, params={"q": "RQ29-SYNTHETIC"}, headers=registrar_h
    )
    assert resp.status_code == 200, resp.text
    matches = [
        p for p in resp.json() if (p.get("phone") or "").endswith(PHONE_MAIN)
    ]
    assert matches, "the registrar must find the synthetic patient by name"
    assert matches[0]["id"] == world["patient"]["id"]


def _step3_wizard_cart_refusal_then_confirmed_quote_success(
    pg_client, pg_session, world
):
    """Steps 2-3 of the combined path: the wizard cart refuses a
    requires_doctor service saved without a doctor (RQ-05.a gate — no
    partial state), the registrar fixes the required link, and the
    confirmed quote-backed save creates the invoice, both visits and the
    queue numbers on BOTH axes (doctor + resource)."""
    registrar_h = world["registrar_h"]
    consult_id = world["service_ids"]["consult"]
    labtest_id = world["service_ids"]["labtest"]
    today = datetime.now(UTC).date().isoformat()

    quote_payload = {
        "items": [
            {"service_id": consult_id, "quantity": 1},
            {"service_id": labtest_id, "quantity": 1},
        ],
        "discount_mode": "none",
        "all_free": False,
        "pricing_mode": "cart",
    }
    resp = pg_client.post(CART_QUOTE, json=quote_payload, headers=registrar_h)
    assert resp.status_code == 200, resp.text
    quote = resp.json()
    assert quote["quote_token"], "the quote must return a binding token"
    assert float(quote["total_amount"]) == 90000.0, quote

    visits = [
        {
            # The required-doctor link is MISSING on purpose (first try).
            "services": [{"service_id": consult_id, "quantity": 1}],
            "visit_date": today,
            "department": DOCTOR_SPECIALTY,
        },
        {
            "services": [{"service_id": labtest_id, "quantity": 1}],
            "visit_date": today,
            "department": LAB_TAG,
        },
    ]
    cart_payload = {
        "patient_id": world["patient"]["id"],
        "visits": visits,
        "discount_mode": "none",
        "payment_method": "cash",
        "quote_token": quote["quote_token"],
    }

    # DB-side partial-state proof (owner review P2): the "no partial
    # state" claim is asserted on the DATABASE, not only through the
    # HTTP status — the refused save must create no Invoice, no Visit
    # and no OnlineQueueEntry rows for this patient.
    from app.models.billing import Invoice
    from app.models.online_queue import OnlineQueueEntry
    from app.models.visit import Visit

    patient_id = world["patient"]["id"]

    def _partial_state_counts() -> dict[str, int]:
        return {
            "invoices": pg_session.query(Invoice)
            .filter(Invoice.patient_id == patient_id)
            .count(),
            "visits": pg_session.query(Visit)
            .filter(Visit.patient_id == patient_id)
            .count(),
            "queue_entries": pg_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.patient_id == patient_id)
            .count(),
        }

    before_refusal = _partial_state_counts()
    assert before_refusal == {"invoices": 0, "visits": 0, "queue_entries": 0}, (
        "the synthetic patient must be fresh before the refused save"
    )

    resp = pg_client.post(CART_PATH, json=cart_payload, headers=registrar_h)
    assert resp.status_code == 400, (
        f"requires_doctor service must refuse a doctorless save, "
        f"got {resp.status_code}: {resp.text[:300]}"
    )
    assert "требует выбора врача" in resp.text
    after_refusal = _partial_state_counts()
    assert after_refusal == before_refusal, (
        f"the refused requires_doctor save must not create partial state "
        f"(before={before_refusal}, after={after_refusal})"
    )

    # The registrar fixes the required link (doctor of the SAME
    # specialty, active — the eligibility contract).
    cardiology_doctor_id = world_doctor_id_resolved(pg_session, "rq29_doc")
    cart_payload["visits"] = [
        dict(visits[0], doctor_id=cardiology_doctor_id)
    ] + visits[1:]
    resp = pg_client.post(CART_PATH, json=cart_payload, headers=registrar_h)
    assert resp.status_code == 200, resp.text
    cart = resp.json()
    assert cart["success"] is True
    assert len(cart["visit_ids"]) == 2
    assert float(cart["total_amount"]) == 90000.0, cart
    assert cart["invoice_id"], "the cart must create the invoice"
    assert cart["queue_numbers"], "the cart must assign queue numbers"

    # Both axes materialized on REAL PostgreSQL: the doctor-owned queue
    # for the consultation and the RESOURCE-owned queue for the lab tag
    # (XOR owner — RQ-15 contract).
    from app.models.online_queue import DailyQueue

    doctor_queue = (
        pg_session.query(DailyQueue)
        .filter(
            DailyQueue.day == datetime.now(UTC).date(),
            DailyQueue.queue_tag == DOCTOR_SPECIALTY,
            DailyQueue.specialist_id.isnot(None),
        )
        .first()
    )
    assert doctor_queue is not None, "cart doctor visit must land on the doctor axis"
    resource_queue = (
        pg_session.query(DailyQueue)
        .filter(
            DailyQueue.day == datetime.now(UTC).date(),
            DailyQueue.queue_tag == LAB_TAG,
            DailyQueue.queue_resource_id.isnot(None),
            DailyQueue.specialist_id.is_(None),
        )
        .first()
    )
    assert resource_queue is not None, (
        "cart lab visit must land on the resource axis (XOR owner)"
    )
    assert resource_queue.specialist_id is None

    # Return the step artifacts to the continuous-path caller (explicit
    # state passing — owner review P1: no module-level carry).
    return {
        "cart": cart,
        "doctor_queue_id": doctor_queue.id,
        "resource_queue_id": resource_queue.id,
    }


def _step4_direction_qr_partial_join_repeat_and_probe(
    pg_client, pg_session, world
):
    """Step 4 + 7 of the combined path: the patient records through the
    direction's QR — the profile choice succeeds while ONE extra choice
    (a doctor of another specialty, not part of this direction) refuses;
    the partial result stays visible (1 ticket + 1 explicit error); the
    probe oracle classifies the attempt; the REPEATED command replays
    the saved result and creates no duplicate tickets."""
    # The direction's permanent address resolves its owners.
    resp = pg_client.post(
        PUBLIC_START.replace("{public_code}", world["public_code"])
    )
    assert resp.status_code == 200, resp.text
    start_body = resp.json()
    session_token = start_body["session_token"]
    profile_id = start_body["direction"]["profile_id"]

    from app.models.clinic import Doctor
    from app.models.user import User

    other_doctor = (
        pg_session.query(Doctor)
        .join(User, Doctor.user_id == User.id)
        .filter(User.username == "rq29_doc2")
        .first()
    )
    assert other_doctor is not None

    payload = {
        "session_token": session_token,
        "patient_name": "RQ29-SYNTHETIC Виктория",
        "phone": PHONE_WALKIN,
        "specialist_ids": [other_doctor.id, profile_id],
        "specialist_entity_types": ["doctor", "profile"],
    }
    resp = pg_client.post(JOIN_COMPLETE, json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # HONEST partial result: one ticket AND one explicit per-choice
    # error; success is NOT a silent 0/2 and NOT a masked 1/2.
    assert body["success"] is True
    assert len(body["entries"]) == 1, body
    assert body["errors"], "the refused extra choice must stay visible"
    assert body["errors"][0]["specialist_id"] == other_doctor.id
    assert body["errors"][0].get("error")
    ticket = body["entries"][0]["queue_number"]

    # Probe oracle (RQ-18 round-12): the saved verdict is decisive.
    probe = pg_client.post(JOIN_PROBE, json=payload)
    assert probe.status_code == 200, probe.text
    assert probe.json()["outcome"] == "joined_match"

    # REPEAT of the same command (lost response): the payload-bound
    # replay re-serves the SAVED result — no second business action.
    from app.models.online_queue import OnlineQueueEntry

    def _join_entry_count() -> int:
        return (
            pg_session.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.phone.like(f"%{PHONE_WALKIN[-4:]}"),
                OnlineQueueEntry.status.in_(("waiting", "called", "serving")),
            )
            .count()
        )

    before_repeat = _join_entry_count()
    resp = pg_client.post(JOIN_COMPLETE, json=payload)
    assert resp.status_code == 200, resp.text
    replay = resp.json()
    assert replay.get("replayed") is True, replay
    assert replay["entries"][0]["queue_number"] == ticket
    assert _join_entry_count() == before_repeat, (
        "the repeated command must not create duplicate tickets"
    )

    return {"direction_ticket": ticket, "direction_session_payload": payload}


def _step5_performer_scope_consistency_and_second_session(
    pg_client, pg_session, world, step3
):
    """Steps 5-6 of the combined path: the ticket reaches the RIGHT
    performer (the dermatology doctor sees nothing), numbers/cabinets
    agree across the registrar worklist, the lab panel and the public
    board (PHI-honest), and a SECOND SESSION (fresh reads, the backend
    equivalent of a page refresh) sees the same state."""
    # Doctor surface: own-scope ticket from the cart leg.
    resp = pg_client.get(
        DOCTOR_QUEUE_TODAY.replace("{specialty}", DOCTOR_SPECIALTY),
        headers=_auth_headers(world["doctor_user"]),
    )
    assert resp.status_code == 200, resp.text
    doctor_body = resp.json()
    assert doctor_body["queue_exists"] is True
    cart_numbers = {
        assignment["number"]
        for assignments in step3["cart"]["queue_numbers"].values()
        for assignment in assignments
        if assignment.get("queue_tag") == DOCTOR_SPECIALTY
    }
    doctor_numbers = {e["number"] for e in doctor_body["entries"]}
    assert cart_numbers & doctor_numbers, (
        "the cart consultation ticket must be on the cardiology doctor's queue"
    )

    # The OTHER doctor (dermatology) must not see the cardiology work.
    resp = pg_client.get(
        DOCTOR_QUEUE_TODAY.replace("{specialty}", OTHER_SPECIALTY),
        headers=_auth_headers(world["other_doctor_user"]),
    )
    assert resp.status_code == 200, resp.text
    other_body = resp.json()
    other_numbers = {e["number"] for e in (other_body.get("entries") or [])}
    assert not (cart_numbers & other_numbers), (
        "a doctor of another specialty must not receive the ticket"
    )

    # Lab panel: the direction walk-in (resource axis) is delivered.
    resp = pg_client.get(LAB_QUEUE_TODAY, headers=_auth_headers(world["lab_user"]))
    assert resp.status_code == 200, resp.text
    lab_body = resp.json()
    assert lab_body.get("entries"), "the lab panel must see the resource work"

    # Registrar worklist: both axes with the registry owner/cabinet.
    resp = pg_client.get(REGISTRAR_TODAY, headers=world["registrar_h"])
    assert resp.status_code == 200, resp.text
    buckets = {
        (q.get("specialty") or "").lower(): q for q in resp.json()["queues"]
    }
    doctor_bucket = buckets.get(DOCTOR_SPECIALTY)
    lab_bucket = buckets.get(LAB_TAG) or buckets.get("laboratory")
    assert doctor_bucket, f"registrar must see the doctor queue; got {list(buckets)}"
    assert lab_bucket, f"registrar must see the resource queue; got {list(buckets)}"
    assert lab_bucket.get("specialist_name") == "SYNTHETIC RQ-29 Lab Cabinet 204"
    assert lab_bucket.get("cabinet") == "204"

    # Public board (privacy 'none' first, like rq24b): no PHI, matching
    # numbers distinguishable by owner axis.
    boards = pg_client.get(
        "/api/v1/admin/display/boards", headers=world["admin_h"]
    )
    assert boards.status_code == 200, boards.text
    board = next(b for b in boards.json() if b.get("name") == "main_board")
    resp = pg_client.put(
        f"/api/v1/admin/display/boards/{board['id']}",
        json={"show_patient_names": "none"},
        headers=world["admin_h"],
    )
    assert resp.status_code == 200, resp.text
    state = _ws_state(pg_client, world["admin"])
    entries = state.get("queue_entries") or []
    assert entries, "the board must contain today's tickets"
    assert "RQ29-SYNTHETIC" not in str(state), (
        "the board leaked patient identity with show_patient_names=none"
    )
    by_number: dict[int, set[tuple]] = {}
    for e in entries:
        key = (e.get("specialist_name"), e.get("specialist_id"))
        by_number.setdefault(e.get("number"), set()).add(key)
    ones = by_number.get(1) or by_number.get("1")
    assert ones is not None and len(ones) >= 2, (
        f"matching number 1 across cabinets must be distinguishable, got {ones}"
    )

    # SECOND SESSION: fresh reads (the backend equivalent of a page
    # refresh / a second registrar session) see the same decisive state.
    resp = pg_client.get(REGISTRAR_TODAY, headers=world["registrar_h"])
    assert resp.status_code == 200, resp.text
    buckets2 = {
        (q.get("specialty") or "").lower(): q for q in resp.json()["queues"]
    }
    assert buckets2.get(DOCTOR_SPECIALTY), "second session lost the doctor queue"
    assert (
        buckets2.get(LAB_TAG) or buckets2.get("laboratory")
    ), "second session lost the resource queue"
    resp = pg_client.get(LAB_QUEUE_TODAY, headers=_auth_headers(world["lab_user"]))
    assert resp.status_code == 200, resp.text
    assert resp.json().get("entries"), "second session lost the lab work"

    return {"board_numbers": sorted(str(n) for n in by_number)}


def _step6_archive_closes_future_joins_preserves_today(
    pg_client, pg_session, world, step3
):
    """Step 8 of the combined path: archiving the direction (the REAL
    profile PUT, rq26b contract) refuses future public joins with the
    anonymous single refusal, while today's queue and history stay
    intact — no silent wipe of the live work."""
    from app.models.online_queue import OnlineQueueEntry

    admin_h = world["admin_h"]

    resp = pg_client.put(
        f"{PROFILES_PATH}/{DIRECTION_KEY}",
        json={"is_active": False},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text

    # Future joins refuse: the archived direction is unreachable through
    # its (still provisioned) permanent address — fail-closed anonymous
    # 404 with the merged refusal detail (S-15).
    resp = pg_client.post(
        PUBLIC_START.replace("{public_code}", world["public_code"])
    )
    assert resp.status_code == 404, (
        f"archived direction must refuse future joins, got {resp.status_code}"
    )
    assert DIRECTION_REFUSAL_DETAIL in resp.text

    # Today's tickets/history preserved on REAL PostgreSQL: the cart's
    # doctor-axis queue and the resource queue still hold their entries.
    doctor_queue = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == step3["doctor_queue_id"])
        .count()
    )
    assert doctor_queue >= 1, "archive must not wipe today's doctor-axis tickets"
    resource_count = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == step3["resource_queue_id"])
        .count()
    )
    assert resource_count >= 1, "archive must not wipe today's resource tickets"

    # The staff surfaces keep showing the live work.
    resp = pg_client.get(REGISTRAR_TODAY, headers=world["registrar_h"])
    assert resp.status_code == 200, resp.text
    buckets = {
        (q.get("specialty") or "").lower(): q for q in resp.json()["queues"]
    }
    assert buckets.get(DOCTOR_SPECIALTY), "archive must not hide the live doctor queue"


def _step7_partial_payment_then_partial_service_cancel(
    pg_client, pg_session, world, step3
):
    """Step 9 of the combined path: a supported PARTIAL payment (the
    allocation lands oldest-first, the remaining debt stays visible) and
    a supported partial service CANCELLATION (one service of a multi-
    service entry, audited, the other service intact) — no assignment
    and no other patient's work is lost."""
    from app.models.online_queue import OnlineQueueEntry
    from app.models.payment import Payment

    cashier_h = _auth_headers(world["cashier"])
    registrar_h = world["registrar_h"]

    # --- partial payment on the cart's invoice (60000 + 30000) ------
    resp = pg_client.get(CASHIER_PENDING, headers=cashier_h)
    assert resp.status_code == 200, resp.text
    rows = resp.json().get("items") or resp.json().get("payments") or []
    target = next(
        (r for r in rows if r.get("patient_id") == world["patient"]["id"]),
        None,
    )
    assert target is not None, "the cashier must see the cart patient's bill"
    visit_ids = target["visit_ids"]
    assert set(visit_ids) == set(step3["cart"]["visit_ids"])

    resp = pg_client.post(
        CASHIER_GROUPED,
        json={
            "visit_ids": visit_ids,
            "patient_id": world["patient"]["id"],
            "amount": 30000,
            "method": "cash",
        },
        headers=cashier_h,
    )
    assert resp.status_code in (200, 201), resp.text
    payment = resp.json()
    assert payment["allocations"] and payment["payments"]

    # The allocation landed on the OLDEST visit only (server-owned).
    # Owner review P2: the oldest-first claim must be PROVEN, not
    # implied by "one visit" — the cashier sorts allocation candidates
    # by (created_at, id); the test resolves the same identity from the
    # DB rows and pins it exactly.
    from app.models.visit import Visit

    cart_visits = pg_session.query(Visit).filter(Visit.id.in_(visit_ids)).all()
    assert len(cart_visits) == len(set(visit_ids)), "cart visits must exist"
    oldest_visit = min(cart_visits, key=lambda v: (v.created_at, v.id))
    paid_visit_ids = {a["visit_id"] for a in payment["allocations"]}
    assert paid_visit_ids == {oldest_visit.id}, (
        f"the allocation must land on the OLDEST visit "
        f"(id={oldest_visit.id}, created_at={oldest_visit.created_at}) of "
        f"{sorted(visit_ids)}, got {sorted(paid_visit_ids)}"
    )
    assert sum(float(a["amount"]) for a in payment["allocations"]) == 30000.0, (
        payment["allocations"]
    )
    resp = pg_client.get(CASHIER_PENDING, headers=cashier_h)
    assert resp.status_code == 200, resp.text
    rows2 = resp.json().get("items") or resp.json().get("payments") or []
    target2 = next(
        (r for r in rows2 if r.get("patient_id") == world["patient"]["id"]),
        None,
    )
    assert target2 is not None, (
        "the remaining 60000 debt must stay visible as pending"
    )

    # --- partial service cancel on a fresh multi-service walk-in -----
    resp = pg_client.post(
        QR_GENERATE,
        json={
            "specialist_id": world_doctor_id_resolved(pg_session, "rq29_doc"),
            "department": DOCTOR_SPECIALTY,
            "target_date": datetime.now(UTC).date().isoformat(),
        },
        headers=world["registrar_h"],
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    joined = _anonym_join(
        pg_client, token, "RQ29-SYNTHETIC Глеб", PHONE_CANCEL
    )
    assert joined["result"]["success"] is True
    entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.phone.like(f"%{PHONE_CANCEL[-4:]}"))
        .order_by(OnlineQueueEntry.id.desc())
        .first()
    )
    assert entry is not None

    resp = pg_client.put(
        ONLINE_ENTRY_FULL_UPDATE.replace("{entry_id}", str(entry.id)),
        json={
            "patient_data": {
                "patient_name": "RQ29-SYNTHETIC Глеб",
                "phone": PHONE_CANCEL,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [
                {"service_id": world["service_ids"]["consult"], "quantity": 1},
                {"service_id": world["service_ids"]["extended"], "quantity": 1},
            ],
        },
        headers=registrar_h,
    )
    assert resp.status_code == 200, resp.text

    # The merged full-update semantics (PHASE 2.2): the added services
    # become PER-SERVICE independent queue entries, each carrying its
    # own services JSON + total_amount; the original join entry stays
    # untouched. Locate the independent entry of the "extended" service.
    import json as _json

    pg_session.expire_all()
    walkin_entries = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.phone.like(f"%{PHONE_CANCEL[-4:]}"))
        .order_by(OnlineQueueEntry.id.asc())
        .all()
    )
    independent_extended = None
    independent_consult = None
    for row in walkin_entries:
        if not row.services:
            continue
        svc_ids = {
            s.get("service_id") for s in _json.loads(row.services)
        }
        if world["service_ids"]["extended"] in svc_ids:
            independent_extended = row
        if world["service_ids"]["consult"] in svc_ids:
            independent_consult = row
    assert independent_extended is not None, (
        "the full-update must create the independent entry for the added service"
    )
    assert independent_extended.total_amount == 40000, (
        f"the extended independent entry carries its own price, got "
        f"{independent_extended.total_amount}"
    )
    assert independent_consult is not None

    # Supported partial cancellation of ONE service (the extended one):
    # marked cancelled with audit fields, the entry total recalculated.
    resp = pg_client.post(
        ONLINE_ENTRY_CANCEL_SERVICE.replace(
            "{entry_id}", str(independent_extended.id)
        ),
        json={
            "service_id": world["service_ids"]["extended"],
            "cancel_reason": "SYNTHETIC RQ-29 partial cancel",
            "was_paid": False,
        },
        headers=registrar_h,
    )
    assert resp.status_code == 200, resp.text

    pg_session.expire_all()
    cancelled_entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == independent_extended.id)
        .first()
    )
    services_after = _json.loads(cancelled_entry.services)
    cancelled = next(
        s
        for s in services_after
        if s["service_id"] == world["service_ids"]["extended"]
    )
    assert cancelled.get("cancelled") is True
    assert cancelled.get("cancel_reason") == "SYNTHETIC RQ-29 partial cancel"
    assert cancelled.get("cancelled_by") is not None
    assert float(cancelled_entry.total_amount) == 0.0, (
        f"the entry total must be recalculated, got {cancelled_entry.total_amount}"
    )

    # The OTHER assignments are intact: the consult independent entry
    # keeps its service and its price; the join entry keeps its place in
    # the doctor queue; nothing else was cancelled.
    consult_entry = (
        pg_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == independent_consult.id)
        .first()
    )
    consult_svcs = _json.loads(consult_entry.services)
    assert any(
        s["service_id"] == world["service_ids"]["consult"]
        and not s.get("cancelled", False)
        for s in consult_svcs
    ), "the partial cancel must not touch the other service"
    assert float(consult_entry.total_amount) == 60000.0, (
        f"the consult entry total must be intact, got {consult_entry.total_amount}"
    )

    # No payment leaked onto other visits (the grouped allocation was
    # the only payment of this scenario).
    payments = pg_session.query(Payment).all()
    assert payments, "the partial payment must exist"
    for p in payments:
        assert p.visit_id in visit_ids, (
            "a payment must never land on a foreign visit"
        )


def world_doctor_id_resolved(pg_session, username: str) -> int:
    """Resolve the Doctor row created through the REAL admin API by the
    linked user's username (the world created it with user_id)."""
    from app.models.clinic import Doctor
    from app.models.user import User

    row = (
        pg_session.query(Doctor)
        .join(User, Doctor.user_id == User.id)
        .filter(User.username == username)
        .first()
    )
    assert row is not None, f"doctor for user {username} must exist"
    return row.id


# === RQ-29 combined path — the ONE continuous test ==================


def test_rq29_combined_path(pg_client, pg_session, world):
    """The whole combined path (ACCEPTANCE steps 1-9) as ONE continuous
    scenario: the admin setup, the wizard cart with the refused
    required-doctor save, the direction QR join with one refused extra
    choice, the performer-scope consistency, the archive gate, and the
    partial payment/cancellation legs — in file order, on one disposable
    PostgreSQL database.

    Owner review P1 fix: the artifacts of each step flow to the next
    step through explicit arguments and return values — there is no
    module-level ``_CARRIED`` carry and no cross-test state, so the
    module cannot depend on pytest collection order. There is exactly
    ONE test in this module: targeted execution (``pytest ... -k
    rq29_combined_path``) runs the same continuous path.
    """
    _step1_admin_setup_and_direction_are_reachable(world)
    _step2_admin_edits_service_and_registrar_finds_patient(pg_client, world)
    step3 = _step3_wizard_cart_refusal_then_confirmed_quote_success(
        pg_client, pg_session, world
    )
    _step4_direction_qr_partial_join_repeat_and_probe(
        pg_client, pg_session, world
    )
    _step5_performer_scope_consistency_and_second_session(
        pg_client, pg_session, world, step3
    )
    _step6_archive_closes_future_joins_preserves_today(
        pg_client, pg_session, world, step3
    )
    _step7_partial_payment_then_partial_service_cancel(
        pg_client, pg_session, world, step3
    )

