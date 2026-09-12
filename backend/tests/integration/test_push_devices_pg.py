"""PR-6: push_devices RLS — disposable PostgreSQL migration probe (gate_d).

The owner requirement is explicit: "RLS включается в той же создающей
миграции; никакого create_all; disposable PostgreSQL upgrade head должен
подтвердить relrowsecurity=true". The CI `alembic upgrade head` jobs
prove the migration APPLIES; this probe proves the RLS CONTRACT on a
disposable database created for the purpose:

1. CREATE DATABASE probe_<rand> on the job's postgres service;
2. `alembic upgrade head` against the probe database (no create_all);
3. assert pg_class.relrowsecurity = true for push_devices;
4. assert deny-all posture: ZERO policies (0046 convention);
5. assert the partial unique index reached PostgreSQL with its WHERE
   clause, and the CHECK enums actually enforce;
6. alembic downgrade -1 → table gone; re-upgrade → RLS on again;
7. DROP DATABASE.

Self-contained: sets its own environment defaults BEFORE importing app
modules (same pattern as test_reminder_pipeline_pg.py), never touches the
repo conftest. Marked ``gate_d`` — excluded from the default suite by
pytest.ini addopts and executed in CI by a dedicated backend step whose
DATABASE_URL points at the job's postgres service.

Run locally (needs a reachable PostgreSQL):
    cd backend && DATABASE_URL=postgresql+psycopg://clinic:pw@localhost:5432/clinicdb \
        pytest tests/integration/test_push_devices_pg.py -m gate_d --noconftest
"""

from __future__ import annotations

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # backend/

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://clinic:clinic_ci_only_password@localhost:5432/clinicdb",
)
# Environment contract for the isolated (--noconftest) CI step: ENV=dev keeps
# the production-only config gates from firing, and TESTING=1 is deliberately
# NOT set — the config validator forbids it outside explicit dev values.
os.environ.setdefault("ENV", "dev")
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-push-devices-rls-probe-32-chars"
)
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "0")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine.url import make_url  # noqa: E402

pytestmark = pytest.mark.gate_d

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_probe_database() -> tuple[str, str]:
    """Create a disposable database and return (probe_url, probe_name)."""
    base_url = make_url(os.environ["DATABASE_URL"])
    probe_name = f"push_devices_rls_{uuid.uuid4().hex[:10]}"
    admin_url = base_url.set(database="postgres")

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{probe_name}"'))
    admin_engine.dispose()
    # render_as_string(hide_password=False): str(URL) MASKS the password in
    # SQLAlchemy 2.x — a masked URL would authenticate with an empty
    # password and fail as "password authentication failed for user".
    probe_url = base_url.set(database=probe_name).render_as_string(
        hide_password=False
    )
    return probe_url, probe_name


def _drop_probe_database(probe_name: str) -> None:
    base_url = make_url(os.environ["DATABASE_URL"])
    admin_url = base_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{probe_name}"'))
    admin_engine.dispose()


def _alembic_upgrade(url: str, revision: str) -> None:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    os.environ["DATABASE_URL"] = url
    command.upgrade(alembic_cfg, revision)


def _probe_connection(url: str):
    engine = create_engine(url)
    return engine.connect()


def test_push_devices_rls_contract_on_disposable_pg():
    probe_url, probe_name = _make_probe_database()
    try:
        # --- upgrade head: the ONLY schema path (no create_all) ---------
        _alembic_upgrade(probe_url, "head")

        with _probe_connection(probe_url) as conn:
            # relrowsecurity=true — the owner-mandated confirmation
            relro = conn.execute(
                text(
                    "SELECT relrowsecurity FROM pg_class "
                    "WHERE relname = 'push_devices'"
                )
            ).scalar()
            assert relro is True, (
                "push_devices must have relrowsecurity=true after "
                "alembic upgrade head (RLS in the creating migration)"
            )

            # Deny-all posture (0046 convention): no policies at all.
            policies = conn.execute(
                text(
                    "SELECT count(*) FROM pg_policies "
                    "WHERE tablename = 'push_devices'"
                )
            ).scalar()
            assert policies == 0

            # Partial unique index reached PostgreSQL with its WHERE clause.
            indexdef = conn.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE indexname = 'uq_push_devices_active_credential'"
                )
            ).scalar()
            assert indexdef is not None
            assert "invalidated_at IS NULL" in indexdef
            assert "UNIQUE" in indexdef

            # CHECK enums actually enforce.
            conn.execute(
                text(
                    "INSERT INTO users (username, hashed_password, role, "
                    "is_active, is_superuser) VALUES "
                    "('push_rls_probe', 'x', 'Patient', true, false)"
                )
            )
            import sqlalchemy as sa

            def _register(token: str, provider: str = "fcm") -> None:
                trans = conn.begin()
                try:
                    conn.execute(
                        sa.text(
                            "INSERT INTO push_devices (user_id, provider, "
                            "platform, token, enabled) VALUES "
                            "((SELECT id FROM users WHERE username = "
                            "'push_rls_probe'), :provider, 'android', "
                            ":token, true)"
                        ),
                        {"provider": provider, "token": token},
                    )
                    trans.commit()
                except Exception:
                    trans.rollback()
                    raise

            _register("tok-probe-1")
            # Duplicate ACTIVE credential → partial unique index fires.
            with pytest.raises(Exception):
                _register("tok-probe-1")
            # Dead row frees the slot (partial index ignores it).
            conn.execute(
                sa.text(
                    "UPDATE push_devices SET invalidated_at = now() "
                    "WHERE token = 'tok-probe-1'"
                )
            )
            _register("tok-probe-1")
            # Closed enums enforce.
            with pytest.raises(Exception):
                _register("tok-probe-2", provider="apns")

        # --- downgrade removes the table, re-upgrade restores RLS -------
        _alembic_upgrade(probe_url, "-1")
        with _probe_connection(probe_url) as conn:
            exists = conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_name = 'push_devices'"
                )
            ).scalar()
            assert exists == 0

        _alembic_upgrade(probe_url, "head")
        with _probe_connection(probe_url) as conn:
            relro = conn.execute(
                text(
                    "SELECT relrowsecurity FROM pg_class "
                    "WHERE relname = 'push_devices'"
                )
            ).scalar()
            assert relro is True
    finally:
        _drop_probe_database(probe_name)
