"""
RQ-16.b — contract/API: the server EXPLICITLY enumerates the supported
QR-entry methods of a direction (DIRECTION_CONTRACT.md §6.2, derived
from D-01/D-03 APPROVED, E-039).

Contract pinned RED-first by this module:

1. ``GET /api/v1/queue/directions/{profile_key}/entry-methods`` exists in
   the real OpenAPI schema with an explicit response model whose methods
   space is exactly {session_qr, permanent_address, view_only}.
2. A QR-visible active direction (is_active AND show_on_qr_page) answers
   200 with ALL THREE methods present (explicit enumeration — the client
   never guesses an absent method) and honest flags: session_qr=True
   (short-lived protected session path; RQ-11 TTL honesty),
   permanent_address=False for a direction WITHOUT a provisioned
   address (since RQ-16.d the flag is dynamic per-direction, E-055 §8 —
   the provisioned flip is pinned by the RQ-16.d runtime suite),
   view_only=True (D-01 §4: an overview never creates its own
   numbering).
3. Archived (is_active=False), hidden (show_on_qr_page=False) and unknown
   keys refuse 404 with the SAME anonymous detail — archived directions
   block new joins and must not leak existence (S-15).
4. §6.1: the endpoint CONSUMES the queue_svc QR-visibility semantics —
   the alias table (QR_SPECIALTY_ALIASES, e.g. "dentist" -> "stomatology")
   resolves to the canonical direction; no duplicated normalization.
5. Fail-closed: this surface inherits NO fallback — the built-in profile
   catalog (/queues/profiles/public fabricates it on an empty DB) must
   never resurrect a DB-archived direction: archiving the seeded
   "cardiology" row flips the answer to the anonymous 404 even though
   the catalog still lists the key.

No existing surface behavior changes. No migrations (read-only over
queue_profiles). Disposable PostgreSQL: the module provisions its own
scratch database (rq16b_check), runs ``alembic upgrade head`` against it
and drops it at the end. Skips (NOT_RUN, per plan P0) when no disposable
PostgreSQL server is reachable. SQLite is never a substitute here.
SYNTHETIC data only.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB_PREFIX = "rq16b_check"
SCRATCH_DB = f"{SCRATCH_DB_PREFIX}_{uuid.uuid4().hex[:12]}"

sys.path.insert(0, str(BACKEND_DIR))

pytestmark = pytest.mark.integration

METHODS_PATH = "/api/v1/queue/directions/{profile_key}/entry-methods"
REFUSAL_DETAIL = "Направление недоступно"
ALL_METHODS = ("session_qr", "permanent_address", "view_only")


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []
    explicit = os.getenv("RQ16B_PG_ADMIN_URL", "").strip()
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
    """Parse a TCP or unix-socket DSN (pgserver emits ?host=<socket dir>)."""
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
    """(psycopg DSN, SQLAlchemy URL) for the scratch database."""
    parts = _dsn_parts(admin_url)
    if parts["sockdir"]:
        base_p = f"postgresql://{parts['user']}:{parts['password']}@/"
        base_s = f"postgresql+psycopg://{parts['user']}:{parts['password']}@/"
        return (
            f"{base_p}{SCRATCH_DB}?host={parts['sockdir']}",
            f"{base_s}{SCRATCH_DB}?host={parts['sockdir']}",
        )
    base = f"postgresql://{parts['user']}:{parts['password']}@{parts['host']}:{parts['port']}"
    return (
        f"{base}/{SCRATCH_DB}",
        f"postgresql+psycopg://{parts['user']}:{parts['password']}@{parts['host']}:{parts['port']}/{SCRATCH_DB}",
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
            f"disposable PostgreSQL unavailable — RQ-16.b PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as c:
        # No pre-drop: the run-unique name cannot pre-exist (a collision would
        # take 2**48 parallel runs), and dropping a fixed name unconditionally
        # is exactly the cross-run hazard this fixture used to carry.
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
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
    assert "PostgreSQL" in (dialect or ""), "RQ-16.b proof requires real PostgreSQL"

    yield engine

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


@pytest.fixture
def seeded_directions(pg_session):
    """Three SYNTHETIC directions covering the visibility matrix.

    - canonical visible: key "stomatology" (a QR_SPECIALTY_ALIASES target —
      pins §6.1 reuse of the service normalization);
    - archived: is_active=False (S-15 refusal);
    - hidden: show_on_qr_page=False (S-15 refusal).
    The alembic catalog seed (cardiology etc.) stays untouched here —
    the fail-closed test archives one catalog row to prove the built-in
    catalog cannot resurrect it.
    """
    from app.models.queue_profile import QueueProfile

    # Module-scoped scratch DB persists across tests — re-seeding must be
    # idempotent (the lifecycle module's delete-if-exists precedent).
    stale = (
        pg_session.query(QueueProfile)
        .filter(
            QueueProfile.key.in_(
                ["stomatology", "rq16b-archived", "rq16b-hidden"]
            )
        )
        .all()
    )
    if stale:
        for profile in stale:
            pg_session.delete(profile)
        pg_session.commit()

    visible = QueueProfile(
        key="stomatology",
        title="Стоматология",
        title_ru="Стоматология (синтетик)",
        queue_tags=["stomatology"],
        display_order=1,
        is_active=True,
        show_on_qr_page=True,
    )
    archived = QueueProfile(
        key="rq16b-archived",
        title="Архивный (синтетик)",
        queue_tags=["rq16b-archived"],
        display_order=2,
        is_active=False,
        show_on_qr_page=True,
    )
    hidden = QueueProfile(
        key="rq16b-hidden",
        title="Скрытый (синтетик)",
        queue_tags=["rq16b-hidden"],
        display_order=3,
        is_active=True,
        show_on_qr_page=False,
    )
    pg_session.add_all([visible, archived, hidden])
    pg_session.commit()
    pg_session.refresh(visible)
    return {"visible_id": visible.id}


def _methods_url(key: str) -> str:
    return METHODS_PATH.replace("{profile_key}", key)


def test_openapi_schema_contains_entry_methods_contract(pg_client):
    schema = pg_client.get("/openapi.json")
    assert schema.status_code == 200
    spec = schema.json()
    assert METHODS_PATH in spec["paths"], "RQ-16.b contract route missing from OpenAPI"
    operation = spec["paths"][METHODS_PATH]["get"]
    assert operation.get("responses"), "entry-methods operation must declare responses"

    ref = (
        operation.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref")
    )
    assert ref, "entry-methods 200 must reference an explicit response model"
    model_name = ref.split("/")[-1]
    model = spec["components"]["schemas"][model_name]
    listed = [prop for prop in model["properties"] if prop != "entry_methods"]
    assert "direction_key" in model["properties"]
    assert "profile_id" in model["properties"]
    assert "title" in model["properties"]
    assert listed == ["direction_key", "profile_id", "title"]

    method_ref = model["properties"]["entry_methods"]["items"]["$ref"]
    item_model = spec["components"]["schemas"][method_ref.split("/")[-1]]
    assert set(item_model["properties"]) == {"method", "supported"}
    enum_ref = item_model["properties"]["method"]["$ref"]
    enum_schema = spec["components"]["schemas"][enum_ref.split("/")[-1]]
    assert sorted(enum_schema["enum"]) == sorted(ALL_METHODS), (
        "the methods space must be explicitly enumerated in the schema"
    )


def test_qr_visible_direction_lists_all_three_methods(pg_client, seeded_directions):
    response = pg_client.get(_methods_url("stomatology"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["direction_key"] == "stomatology"
    assert body["profile_id"] == seeded_directions["visible_id"]
    assert body["title"] == "Стоматология (синтетик)"

    listed = body["entry_methods"]
    assert isinstance(listed, list) and len(listed) == len(ALL_METHODS)
    flags = {item["method"]: item["supported"] for item in listed}
    assert set(flags) == set(ALL_METHODS), (
        "every contract method must be present explicitly — the client "
        "must not infer an absent method"
    )
    assert flags["session_qr"] is True
    assert flags["permanent_address"] is False, (
        "this direction has NO provisioned public address — the dynamic "
        "RQ-16.d flag must stay False (no backfill, E-055 §3); the "
        "provisioned flip is pinned by the RQ-16.d runtime suite"
    )
    assert flags["view_only"] is True


def test_archived_direction_refuses_anonymously(pg_client, seeded_directions):
    response = pg_client.get(_methods_url("rq16b-archived"))
    assert response.status_code == 404
    assert response.json() == {"detail": REFUSAL_DETAIL}


def test_hidden_direction_refuses_anonymously(pg_client, seeded_directions):
    response = pg_client.get(_methods_url("rq16b-hidden"))
    assert response.status_code == 404
    assert response.json() == {"detail": REFUSAL_DETAIL}


def test_unknown_direction_refuses_without_existence_leak(pg_client, seeded_directions):
    unknown = pg_client.get(_methods_url("rq16b-never-seeded"))
    archived = pg_client.get(_methods_url("rq16b-archived"))
    hidden = pg_client.get(_methods_url("rq16b-hidden"))
    for response in (unknown, archived, hidden):
        assert response.status_code == 404
        assert response.json() == {"detail": REFUSAL_DETAIL}
    # The three refusals are byte-identical: no response distinguishes an
    # archived/hidden direction from a non-existent one (S-15 no-leak).
    assert unknown.json() == archived.json() == hidden.json()


def test_alias_key_resolves_via_service_normalization(pg_client, seeded_directions):
    response = pg_client.get(_methods_url("dentist"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["direction_key"] == "stomatology", (
        "QR_SPECIALTY_ALIASES must resolve through the queue_svc "
        "normalization (§6.1 consume, do not duplicate)"
    )
    flags = {item["method"]: item["supported"] for item in body["entry_methods"]}
    assert set(flags) == set(ALL_METHODS)


def test_archived_catalog_key_is_not_resurrected_from_fallback(pg_client, pg_session):
    """Fail-closed: alembic seeds the profile catalog into the scratch DB,
    so a built-in key like "cardiology" exists as a REAL row here. The
    fallback failure mode this pins: /queues/profiles/public fabricates
    catalog directions when the DB is empty — the same fallback in THIS
    surface would RESURRECT a DB-archived direction from the built-in
    catalog. Archiving the row must flip the answer to the anonymous 404
    (S-15: archived blocks new joins), never a catalog-backed 200."""
    from app.models.queue_profile import QueueProfile

    row = (
        pg_session.query(QueueProfile)
        .filter(QueueProfile.key == "cardiology")
        .first()
    )
    assert row is not None, "catalog seed must be present after alembic head"
    assert pg_client.get(_methods_url("cardiology")).status_code == 200

    row.is_active = False
    pg_session.commit()

    response = pg_client.get(_methods_url("cardiology"))
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": REFUSAL_DETAIL}

    row.is_active = True
    pg_session.commit()
    assert pg_client.get(_methods_url("cardiology")).status_code == 200
