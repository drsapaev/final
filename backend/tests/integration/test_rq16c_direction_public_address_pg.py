"""RQ-16.c — MODEL slice: public-address registry for queue directions.

Owner decision 2026-09-17 (E-055, DECISION_PROPOSALS.md §«Решение владельца
по открытой точке RQ-16.c», trace 1a0ae53e51ec7769) — the permanent public
address of a direction is ``/q/<public_code>`` with an OPAQUE RANDOM
server-generated code. This module pins the registry CONTRACT on a real
PostgreSQL schema (E-055 §12 PG acceptance matrix):

1. clean upgrade: one actual Alembic head — the chain head
   (``0069_sentinel_pair_retirement``, chained above the
   ``0068_direction_public_address`` registry revision by the RQ-15.d
   repair, owner directive trace 1a0aef280204950d)
   and the registry table exists;
2. an address row can be created for a QueueProfile; generated codes
   satisfy the approved shape (12 chars, canonical lowercase, approved
   alphabet);
3. ``public_code`` is globally UNIQUE forever — duplicates are rejected,
   including reuse of a RETIRED code (no reassignment, ever);
4. at most ONE active (``retired_at IS NULL``) address per profile —
   partial unique index; after retiring one, another active row for the
   same profile is allowed (rotation groundwork only; rotation itself is
   an explicitly separate future workstream, E-055 §6);
5. different profiles hold different codes;
6. rename of the profile does not change the address;
7. archive (``is_active=False``) does not delete or retire the address —
   reactivating the SAME profile restores the SAME address;
8. hard delete of the profile leaves a tombstone (``queue_profile_id``
   NULL) and the burned code can never be reused; a new similar profile
   gets a NEW code;
9. canonical-form CHECKs: wrong length and non-lowercase codes rejected;
10. downgrade drops the table cleanly, re-upgrade leaves no partial
    registry rows (repo migration policy allows module-level downgrade
    proofs — precedent ``test_doctor_user_unique_invariant.py``).

Scope guard (E-055 §13): this slice is MODEL ONLY — no ``/q`` route, no
resolve/start endpoint, no session issuance, no ``permanent_address``
flip (that is RQ-16.d). Deliberately NO backfill: provisioning existing
profiles is a later, separately authorized step; the Alembic-seeded
profile catalog must NOT receive addresses here.

Disposable PostgreSQL: the module provisions its own scratch database
(``rq16c_check``), runs ``alembic upgrade head`` against it and drops it
at the end. Skips (NOT_RUN) when no disposable PostgreSQL server is
reachable. SQLite is never a substitute here. SYNTHETIC data only; no
PII/secret values anywhere (the registry holds only codes/timestamps/FK).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq16c_check"
# The head pin advances with the chain (established pattern: #3306
# advanced the 0067-era pins; the RQ-15.d repair chains 0069 above the
# 0068 registry revision — owner directive trace 1a0aef280204950d).
EXPECTED_HEAD = "0069_sentinel_pair_retirement"

sys.path.insert(0, str(BACKEND_DIR))

pytestmark = pytest.mark.integration


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []
    explicit = os.getenv("RQ16C_PG_ADMIN_URL", "").strip()
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


def _run_alembic(sa_url: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
        timeout=300,
    )


@pytest.fixture(scope="module")
def pg_env():
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
            f"disposable PostgreSQL unavailable — RQ-16.c PG acceptance NOT_RUN "
            f"(last error: {last_error})"
        )

    psycopg_dsn, sa_url = _scratch_urls(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

    r = _run_alembic(sa_url, "upgrade", "head")
    assert r.returncode == 0, r.stderr[-1500:]

    yield sa_url, psycopg_dsn

    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')


@pytest.fixture(scope="module")
def pg_engine(pg_env):
    sa_url, psycopg_dsn = pg_env
    with psycopg.connect(psycopg_dsn) as conn:
        # native psycopg3: fetch rows explicitly (no .scalar() on Cursor)
        version = conn.execute("select version_num from alembic_version").fetchone()[0]
        dialect = conn.execute("select version()").fetchone()[0]
    assert version, "alembic_version must be present after upgrade"
    assert "PostgreSQL" in (dialect or ""), "RQ-16.c proof requires real PostgreSQL"
    engine = create_engine(sa_url, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, future=True)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_profile(session, key: str):
    """SYNTHETIC QueueProfile (does not touch the seeded catalog)."""
    from app.models.queue_profile import QueueProfile

    profile = QueueProfile(
        key=key,
        title=f"Synthetic {key}",
        queue_tags=[f"tag_{key}"],
        display_order=999,
        is_active=True,
        show_on_qr_page=True,
    )
    session.add(profile)
    session.flush()
    return profile


def _make_address(session, profile_id, code: str):
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress

    row = QueueDirectionPublicAddress(queue_profile_id=profile_id, public_code=code)
    session.add(row)
    session.flush()
    return row


# -----------------------------------------------------------------
# 1. Clean upgrade: single actual head + table exists (E-055 §12)
# -----------------------------------------------------------------


def test_clean_upgrade_single_head_and_table(pg_env):
    sa_url, psycopg_dsn = pg_env
    with psycopg.connect(psycopg_dsn) as conn:
        rows = conn.execute("select version_num from alembic_version").fetchall()
        assert len(rows) == 1, f"exactly one alembic head expected, got {rows}"
        assert rows[0][0] == EXPECTED_HEAD
        present = conn.execute(
            "select to_regclass('public.queue_direction_public_addresses')"
        ).fetchone()[0]
        assert present == "queue_direction_public_addresses"


# -----------------------------------------------------------------
# 2. Create row; generator shape is the approved one (E-055 §2/§3)
# -----------------------------------------------------------------


def test_create_address_row_with_generated_code(pg_session):
    from app.models.queue_direction_public_address import (
        PUBLIC_CODE_ALPHABET,
        PUBLIC_CODE_LENGTH,
        generate_public_code,
    )

    profile = _make_profile(pg_session, "rq16c_gen")
    code = generate_public_code()
    assert len(code) == PUBLIC_CODE_LENGTH == 12
    assert all(ch in PUBLIC_CODE_ALPHABET for ch in code)
    assert code == code.lower()

    row = _make_address(pg_session, profile.id, code)
    pg_session.flush()
    assert row.id is not None
    assert row.retired_at is None, "fresh address is active (not retired)"
    assert row.created_at is not None


# -----------------------------------------------------------------
# 3. Global uniqueness forever, including retired rows (E-055 §5)
# -----------------------------------------------------------------


def test_global_uniqueness_rejects_duplicate_active(pg_session):
    from sqlalchemy.exc import IntegrityError

    from app.models.queue_direction_public_address import generate_public_code

    p1 = _make_profile(pg_session, "rq16c_u1")
    p2 = _make_profile(pg_session, "rq16c_u2")
    code = generate_public_code()
    _make_address(pg_session, p1.id, code)
    with pytest.raises(IntegrityError):
        _make_address(pg_session, p2.id, code)
    pg_session.rollback()


def test_retired_code_is_still_not_reusable(pg_session):
    from datetime import UTC, datetime

    from sqlalchemy.exc import IntegrityError

    from app.models.queue_direction_public_address import generate_public_code

    p1 = _make_profile(pg_session, "rq16c_u3")
    p2 = _make_profile(pg_session, "rq16c_u4")
    code = generate_public_code()
    row = _make_address(pg_session, p1.id, code)
    row.retired_at = datetime.now(UTC)
    pg_session.flush()
    with pytest.raises(IntegrityError):
        _make_address(pg_session, p2.id, code)
    pg_session.rollback()


# -----------------------------------------------------------------
# 4. One ACTIVE address per profile (partial unique, E-055 §5)
# -----------------------------------------------------------------


def test_one_active_address_per_profile(pg_session):
    from datetime import UTC, datetime

    from sqlalchemy.exc import IntegrityError

    from app.models.queue_direction_public_address import generate_public_code

    profile = _make_profile(pg_session, "rq16c_one")
    first = generate_public_code()
    second = generate_public_code()
    while second == first:  # deterministic distinctness for the pin
        second = generate_public_code()
    _make_address(pg_session, profile.id, first)
    with pytest.raises(IntegrityError):
        _make_address(pg_session, profile.id, second)
    pg_session.rollback()  # wipes profile+row: rebuild the scenario below

    profile = _make_profile(pg_session, "rq16c_one")
    row = _make_address(pg_session, profile.id, first)
    row.retired_at = datetime.now(UTC)
    pg_session.flush()
    # After retiring the first, a second ACTIVE row is permitted again
    # (groundwork only — actual rotation is a separate future workstream).
    _make_address(pg_session, profile.id, second)
    pg_session.flush()


# -----------------------------------------------------------------
# 5. Different profiles hold different codes (E-055 §12)
# -----------------------------------------------------------------


def test_different_profiles_hold_different_codes(pg_session):
    from app.models.queue_direction_public_address import generate_public_code

    codes: set[str] = set()
    for n in range(5):
        profile = _make_profile(pg_session, f"rq16c_dist_{n}")
        code = generate_public_code()
        while code in codes:
            code = generate_public_code()
        _make_address(pg_session, profile.id, code)
        codes.add(code)
    assert len(codes) == 5


# -----------------------------------------------------------------
# 6/7. Rename keeps address; archive/reactivate semantics (E-055 §7)
# -----------------------------------------------------------------


def test_rename_profile_keeps_code(pg_session):
    from app.models.queue_direction_public_address import generate_public_code

    profile = _make_profile(pg_session, "rq16c_rename")
    code = generate_public_code()
    row = _make_address(pg_session, profile.id, code)

    profile.title = "Renamed synthetic direction"
    profile.queue_tags = ["renamed_tag"]
    pg_session.flush()
    pg_session.refresh(row)
    assert row.public_code == code
    assert row.queue_profile_id == profile.id


def test_archive_and_reactivate_keep_same_address(pg_session):
    from app.models.queue_direction_public_address import generate_public_code

    profile = _make_profile(pg_session, "rq16c_arch")
    code = generate_public_code()
    row = _make_address(pg_session, profile.id, code)

    profile.is_active = False  # archive = existing D-02 transition
    pg_session.flush()
    pg_session.refresh(row)
    assert row.retired_at is None, "archive does NOT retire the address record"
    assert row.public_code == code

    profile.is_active = True  # reactivate SAME profile
    pg_session.flush()
    pg_session.refresh(row)
    assert row.queue_profile_id == profile.id
    assert row.public_code == code, "same profile -> same address again"


# -----------------------------------------------------------------
# 8. Hard delete: tombstone, burned code never reusable (E-055 §5)
# -----------------------------------------------------------------


def test_hard_delete_tombstone_and_burned_code(pg_session):
    from sqlalchemy.exc import IntegrityError

    from app.models.queue_direction_public_address import (
        QueueDirectionPublicAddress,
        generate_public_code,
    )

    profile = _make_profile(pg_session, "rq16c_del")
    code = generate_public_code()
    row = _make_address(pg_session, profile.id, code)

    pg_session.delete(profile)
    pg_session.flush()
    pg_session.expire_all()  # drop the identity-map snapshot (stale FK value)

    survivors = (
        pg_session.query(QueueDirectionPublicAddress)
        .filter(QueueDirectionPublicAddress.public_code == code)
        .all()
    )
    assert len(survivors) == 1, "address row survives profile hard delete (tombstone)"
    assert survivors[0].queue_profile_id is None, "FK ON DELETE SET NULL tombstone"

    fresh = _make_profile(pg_session, "rq16c_del_new")
    with pytest.raises(IntegrityError):
        _make_address(pg_session, fresh.id, code)  # burned code never reusable
    pg_session.rollback()


# -----------------------------------------------------------------
# 9. Canonical-form CHECKs (E-055 §11)
# -----------------------------------------------------------------


def test_wrong_length_code_rejected(pg_session):
    from sqlalchemy.exc import IntegrityError

    profile = _make_profile(pg_session, "rq16c_len")
    with pytest.raises(IntegrityError):
        _make_address(pg_session, profile.id, "2")
    pg_session.rollback()


def test_non_lowercase_code_rejected(pg_session):
    from sqlalchemy.exc import IntegrityError

    profile = _make_profile(pg_session, "rq16c_case")
    with pytest.raises(IntegrityError):
        _make_address(pg_session, profile.id, "A2345678BCDE")
    pg_session.rollback()


# -----------------------------------------------------------------
# 10. Downgrade/re-upgrade clean (repo policy allows the proof)
# -----------------------------------------------------------------


def test_downgrade_reupgrade_leaves_no_partial_registry(pg_env):
    sa_url, psycopg_dsn = pg_env

    r_down = _run_alembic(sa_url, "downgrade", "-1")
    assert r_down.returncode == 0, r_down.stderr[-1500:]
    with psycopg.connect(psycopg_dsn) as conn:
        version = conn.execute("select version_num from alembic_version").fetchone()[0]
        # -1 from the 0069 chain head lands on the registry revision 0068:
        # the retirement downgrade must leave NO partial registry rows.
        assert version == "0068_direction_public_address"
        present = conn.execute(
            "select to_regclass('public.queue_direction_public_addresses')"
        ).fetchone()[0]
        assert present is not None, "0068 keeps the registry table"
        leftover = conn.execute(
            "select count(*) from queue_direction_public_addresses"
        ).fetchone()[0]
        assert leftover == 0, "0069 downgrade leaves no partial registry"

    # one more step: 0068's own downgrade drops the registry table
    # (the original pre-repair assertion, now one level below the head)
    r_down2 = _run_alembic(sa_url, "downgrade", "-1")
    assert r_down2.returncode == 0, r_down2.stderr[-1500:]
    with psycopg.connect(psycopg_dsn) as conn:
        version = conn.execute("select version_num from alembic_version").fetchone()[0]
        assert version == "0067_daily_queue_start_number"
        gone = conn.execute(
            "select to_regclass('public.queue_direction_public_addresses')"
        ).fetchone()[0]
        assert gone is None, "downgrade drops the registry table"

    r_up = _run_alembic(sa_url, "upgrade", "head")
    assert r_up.returncode == 0, r_up.stderr[-1500:]
    with psycopg.connect(psycopg_dsn) as conn:
        version = conn.execute("select version_num from alembic_version").fetchone()[0]
        assert version == EXPECTED_HEAD
        count = conn.execute(
            "select count(*) from queue_direction_public_addresses"
        ).fetchone()[0]
        assert count == 0, "re-upgrade leaves NO partial registry rows"
        # No backfill: the Alembic-seeded profile catalog stays address-less.
        seeded = conn.execute(
            "select count(*) from queue_profiles qp "
            "where exists (select 1 from queue_direction_public_addresses a "
            "where a.queue_profile_id = qp.id)"
        ).fetchone()[0]
        assert seeded == 0, "no backfill: no seeded/synthetic profile got an address"


# -----------------------------------------------------------------
# Scope guard: registry stays write-free for existing surfaces
# -----------------------------------------------------------------


def test_seeded_catalog_untouched_and_no_endpoint(pg_session):
    """MODEL slice boundary: the seeded catalog still exists unchanged and
    the OpenAPI schema knows NO permanent-address endpoint (RQ-16.d)."""
    from app.models.queue_profile import QueueProfile

    cardiology = pg_session.query(QueueProfile).filter(QueueProfile.key == "cardiology").one()
    assert cardiology.is_active is True

    from app.main import app

    spec = app.openapi()
    paths = [p for p in spec["paths"] if "permanent" in p or p.rstrip("/").endswith("/q")]
    assert paths == [], (
        f"no /q or permanent-address endpoint may exist in RQ-16.c "
        f"(that is RQ-16.d): {paths}"
    )
