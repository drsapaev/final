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
its own UNIQUE scratch database (``rq26b_check_<hex>`` — a fixed name
with a pre-drop let two parallel pytest/agent runs on one server drop
each other's database), runs ``alembic upgrade head`` and drops it at
the end; skips (NOT_RUN, plan P0) when no disposable PostgreSQL server
is reachable. ``DATABASE_URL`` is accepted for automatic provisioning
only for local servers — an explicit loopback host, a hostless
unix-socket DSN, or a ``?host=`` that is a socket-directory path or a
loopback name; hidden address sources (``?hostaddr=``, a remote
``?host=`` entry — including inside a comma-separated fallback list —
an address-overriding ``PGHOSTADDR``/remote-``PGHOST`` environment, or
a ``?service=``/``PGSERVICE`` reference, which lets pg_service.conf
supply the actually dialed address) are rejected, so a remote admin
DSN must be passed explicitly via the test-owned
``RQ26B_PG_ADMIN_URL``. SQLite is never a substitute here.

Determinism: the anonymous start-session leg goes through the queue
time gate (``ONLINE_QUEUE_START_TIME`` 07:00 Asia/Tashkent), so the
module pins the gate open with the same autouse ``_no_time_gate``
fixture as test_rq16d_public_direction_runtime.py — otherwise a nightly
run before 07:00 local time fails with no code change.

SYNTHETIC data only (``rq26b-``/``RQ26B-`` markers); per AGENTS.md PII
rules no plaintext ``email``/``phone``/``patients.*`` values are
committed — synthetic users carry ``email=None`` (no PHI/PII).

Modeled on tests/integration/test_rq16d_public_direction_runtime.py and
test_rq24b_cross_panel_s21_pg.py (merged real-PG harness precedents).

Run::

    cd backend && RQ26B_PG_ADMIN_URL='postgresql://postgres:@/postgres?host=/path/to/sock' \\
        pytest tests/integration/test_rq26b_csv_lifecycle_contract_pg.py -q
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import time
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Unique per run (review P2 — scratch-DB isolation): cleanup drops ONLY
# the database this run created, so parallel runs cannot destroy each
# other's scratch state (same class fix as the schedule-lock harness).
SCRATCH_DB = f"rq26b_check_{uuid.uuid4().hex[:12]}"

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
    """Plain-psycopg admin DSNs — LOCAL servers only for auto-detection.

    ``DATABASE_URL`` in CI is a SQLAlchemy URL
    (``postgresql+psycopg://``); psycopg.connect rejects the driver
    suffix, so the scheme is normalized for the admin connection
    (RQ-24.b lesson: without the normalization the module would silently
    SKIP in CI).

    The scratch database must never be provisioned — or dropped — on a
    remote server reachable through a plain ``DATABASE_URL`` (review P2):
    auto-detected candidates are accepted only for LOCAL servers, judged
    by the address libpq actually dials, not by the URL spelling. A
    ``?host=`` query parameter overrides the authority host, so a remote
    value there (``postgresql://u:p@/postgres?host=db.internal``,
    review P1) is rejected even though the authority is empty — including
    remote entries inside a comma-separated fallback list; the
    address-altering ``?hostaddr=`` is rejected outright (round-2 review
    P1), as is an address-overriding ``PGHOSTADDR``/remote-``PGHOST``
    environment (round-3 review P1), and any ``?service=``/``PGSERVICE``
    reference (round-4 review P1): libpq resolves a service name from
    pg_service.conf into host/port/etc. at connect time, so a
    service-referencing candidate cannot be proven to dial the same
    local address its scratch DSN reproduces. A remote admin DSN must
    be passed explicitly via the test-owned ``RQ26B_PG_ADMIN_URL``.
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

    explicit = os.getenv("RQ26B_PG_ADMIN_URL", "").strip()
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
            f"disposable PostgreSQL unavailable — RQ-26.b PG verification NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    # No pre-drop: the name is unique per run, so a leftover database can
    # never be silently reused — a name collision fails loudly instead.
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    # try/finally (review P2): alembic, engine creation, or an assertion
    # may fail BEFORE the yield — pytest does not run the post-yield
    # teardown then, and with run-unique names the leaked scratch
    # database would never be cleaned by any later run. Everything after
    # the successful CREATE DATABASE must therefore drop it
    # unconditionally.
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
            "RQ-26.b proof requires real PostgreSQL"
        )

        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        with psycopg.connect(admin_url, autocommit=True) as c:
            try:
                c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
            except Exception:  # noqa: BLE001 — pre-PG13 fallback
                c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')


@pytest.fixture
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    yield session
    session.rollback()
    session.close()


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


@pytest.fixture(autouse=True)
def _no_time_gate(monkeypatch):
    """Pin the queue time gate open (same fixture as test_rq16d).

    The permanent-address start-session leg goes through
    ``start_join_session()`` → ``_check_online_time_restrictions()``,
    which refuses before 07:00 Asia/Tashkent. Without this fixture a
    nightly CI run inside that window fails with no code change (review
    P1); with the gate pinned to 00:00 the module is deterministic at
    any wall-clock time.
    """
    from app.services.queue_svc import QueueBusinessService
    from app.services.queue_svc._base import QueueBusinessServiceMixinBase

    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    monkeypatch.setattr(
        QueueBusinessServiceMixinBase, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )


def _get_or_create_user(session, username: str, role: str):
    """Idempotent synthetic user (the scratch DB persists across tests)."""
    from app.core.security import get_password_hash
    from app.models.user import User

    user = session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        # AGENTS.md PII rules: email must never appear in plaintext in
        # committed test fixtures — synthetic users carry no email at all.
        email=None,
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
    SUPPORTED creation surface now enforces the same pattern: this profile
    POST and the admin department create (RQ-26.b follow-up unified
    DepartmentCreate with QueueProfileCreate — the department-integration
    path turns department.key into a profile key), so real CSV exports
    always re-import (the round-trip tests use valid keys)."""
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


# ------------------------------------------------------------------
# 7. Full round-trip: admin department create → CSV export → fresh import
# ------------------------------------------------------------------


def test_admin_department_create_key_enters_csv_round_trip(
    pg_client, pg_admin_user, pg_session
):
    """RQ-26.b review follow-up (P2): the department-integration path
    (``_ensure_department_integrations``) turns ``department.key`` into a
    ``QueueProfile.key`` — the OTHER supported creation surface the CSV
    export reads. The round-trip closes only if that key also satisfies
    the strict import schema:

    - a department create with a foreign key style is refused 422 BEFORE
      any state change (DepartmentCreate now enforces the same pattern as
      QueueProfileCreate), so a supported-flow export can never carry a
      key the fresh import would reject;
    - a department create with a conforming key auto-provisions the
      profile (PR-16), the admin list exposes it (the CSV export source),
      and the CSV-shaped payload re-imports cleanly into a fresh state
      (the auto-created row is removed first to simulate a fresh install).
    """
    headers = _auth_headers(pg_admin_user)

    refused = pg_client.post(
        "/api/v1/admin/departments",
        json={"key": "rq26b-invalid-key", "name_ru": "RQ-26.b отказ (синтетик)"},
        headers=headers,
    )
    assert refused.status_code == 422, refused.text
    listing = pg_client.get(
        PROFILES_PATH, params={"active_only": "false"}, headers=headers
    )
    assert listing.status_code == 200
    assert all(
        p["key"] != "rq26b-invalid-key" for p in listing.json()["profiles"]
    ), "a refused department key must leave no queue profile behind"

    created = pg_client.post(
        "/api/v1/admin/departments",
        json={
            "key": "rq26b_rt",
            "name_ru": "RQ-26.b round-trip (синтетик)",
            # Explicit short service_code: the auto-derived f"{key}_consult"
            # exceeds the legacy services VARCHAR(10) for longer keys — a
            # pre-existing quirk out of RQ-26.b scope; the round-trip target
            # here is the profile key, not the service code.
            "integration": {"service_code": "RQ26BRT"},
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["integration"]["queue_profile_created"] is True, (
        "the auto-provisioned registrar tab (PR-16) is the export source"
    )

    export = pg_client.get(
        PROFILES_PATH, params={"active_only": "false"}, headers=headers
    )
    assert export.status_code == 200
    source = {p["key"]: p for p in export.json()["profiles"]}["rq26b_rt"]
    assert set(source.keys()) == CSV_SOURCE_PROFILE_KEYS

    # CSV payload shape: typed values, `order` → display_order, omitted
    # empty cells — exactly what queueProfilesCsv.ts builds for import.
    payload = {
        "key": source["key"],
        "title": source["title"],
        "title_ru": source["title_ru"],
        "queue_tags": source["queue_tags"],
        "department_key": source["department_key"],
        "icon": source["icon"],
        "color": source["color"],
        "display_order": source["order"],
        "is_active": source["is_active"],
        "show_on_qr_page": source["show_on_qr_page"],
    }

    # Fresh-install simulation: remove the auto-created row, then import.
    from app.models.queue_profile import QueueProfile

    auto_created = (
        pg_session.query(QueueProfile).filter(QueueProfile.key == "rq26b_rt").one()
    )
    pg_session.delete(auto_created)
    pg_session.commit()

    reimported = pg_client.post(PROFILES_PATH, json=payload, headers=headers)
    assert reimported.status_code == 200, reimported.text
    assert reimported.json()["success"] is True
    body = reimported.json()["profile"]
    assert body["key"] == "rq26b_rt"
    assert body["order"] == source["order"]
    assert body["queue_tags"] == source["queue_tags"]
    assert body["department_key"] == source["department_key"]
    assert body["is_active"] == source["is_active"]
    assert body["show_on_qr_page"] == source["show_on_qr_page"]


# ------------------------------------------------------------------
# Review-round pins (rounds 1-4): the candidate-DSN guard and the
# scratch-DSN address forms are pure functions of their inputs — these
# pins run WITHOUT a PostgreSQL server and must stay green everywhere.
# ------------------------------------------------------------------


def _harness_env(monkeypatch, database_url: str | None) -> None:
    """Isolate the guard from the host environment."""
    monkeypatch.delenv("RQ26B_PG_ADMIN_URL", raising=False)
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
        "RQ26B_PG_ADMIN_URL", "postgresql://u:p@db.internal:5432/postgres"
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
