"""
RQ-23.a (D-06 APPROVED E-039 / ACCEPTANCE S-20): server-side effective
queue settings REPORT — «администратор видит, какое значение применяется
и когда».

The report is a PURE read-model computation over existing rows (the
owner-approved D-06 design: «SSOT-функция — чистое вычисление над
существующими строками»). It must:

- attribute a SOURCE level to every managed setting (clinic → department
  → owner → day_snapshot), so no field is silently dead anymore;
- reuse the RQ-13.b SSOT helper ``effective_day_start_number`` for the
  start-number VALUE (anti-drift: the report displays what the engine
  actually freezes into new days);
- honestly flag fields the queue runtime never reads (the department
  settings block and the clinic ``auto_close_time`` — the close engine
  reads the ``DailyQueue.online_end_time`` SNAPSHOT, which originates
  from the never-persisted ``queue_end_hour`` key, not from
  ``auto_close_time``);
- prove the D-06 boundary: an active day keeps its frozen snapshot
  values after clinic settings change (no retroactive rewrite).

Read-only slice: NO runtime chain changes, NO migrations, NO frontend
changes (the UI «источник и время применения» reads this endpoint in the
follow-up RQ-23.ui slice).

Disposable PostgreSQL: the module provisions its own scratch database
(rq23a_check), runs `alembic upgrade head` against it and drops it at
the end. Skips (NOT_RUN, per plan P0) when no disposable PostgreSQL
server is reachable. SQLite is never a substitute here.
"""

from __future__ import annotations

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
SCRATCH_DB = "rq23a_check"

sys.path.insert(0, str(BACKEND_DIR))


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []

    explicit = os.getenv("RQ23A_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)

    # Legacy holder names kept for cross-slice reuse of the same server.
    legacy = os.getenv("RQ12B_PG_ADMIN_URL", "").strip()
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
        elif not u.host and (u.query.get("host") or "").startswith(("/", "./")):
            urls.append(env_url)

    return urls


def _scratch_url(admin_url: str) -> tuple[str, str]:
    """(psycopg conninfo, sqlalchemy URL) for the scratch database."""
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
            f"disposable PostgreSQL unavailable — RQ-23.a PG acceptance NOT_RUN "
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
        pg_session.query(User).filter(User.username == "rq23a_admin").first()
    )
    if user:
        return user
    user = User(
        username="rq23a_admin",
        email="rq23a-admin@example.com",
        full_name="RQ-23.a Admin",
        hashed_password=get_password_hash("rq23a-synthetic-pw"),
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


def _auth_headers(pg_admin_user) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(pg_admin_user)}"}


def _set_queue_setting(pg_session, key: str, value: Any) -> None:
    from app.models.clinic import ClinicSettings

    row = (
        pg_session.query(ClinicSettings).filter(ClinicSettings.key == key).first()
    )
    if row:
        row.value = value
        row.category = "queue"
    else:
        pg_session.add(
            ClinicSettings(key=key, value=value, category="queue")
        )
    pg_session.commit()


def _seed_department(pg_session, key: str) -> Any:
    from app.models.department import Department, DepartmentQueueSettings

    dept = (
        pg_session.query(Department).filter(Department.key == key).first()
    )
    if not dept:
        dept = Department(
            key=key,
            name_ru=f"RQ-23.a отделение {key}",
            display_order=900,
            active=True,
        )
        pg_session.add(dept)
        pg_session.flush()
        pg_session.add(
            DepartmentQueueSettings(
                department_id=dept.id,
                enabled=True,
                queue_type="mixed",
                queue_prefix="RQ",
                max_daily_queue=33,
                max_concurrent_queue=7,
                avg_wait_time=10,
                show_on_display=True,
                auto_close_time="12:00",
            )
        )
        pg_session.commit()
        pg_session.refresh(dept)
    return dept


def _seed_doctor(pg_session, dept, name: str, start_number: int) -> Any:
    from app.models.clinic import Doctor

    doctor = Doctor(
        department_id=dept.id,
        specialty="rq23a-spec",
        start_number_online=start_number,
        max_online_per_day=15,
        active=True,
    )
    pg_session.add(doctor)
    pg_session.flush()
    pg_session.commit()
    pg_session.refresh(doctor)
    assert doctor.id is not None, name
    return doctor


def _report(pg_client, headers: dict, **params) -> dict:
    resp = pg_client.get(
        "/api/v1/admin/queue/settings/effective",
        params=params or None,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------
# 1. Endpoint surface: admin-only + report shape
# ---------------------------------------------------------------


def test_endpoint_requires_auth(pg_client):
    resp = pg_client.get("/api/v1/admin/queue/settings/effective")
    assert resp.status_code in (401, 403), resp.text


def test_report_shape_and_chain(pg_client, pg_admin_user):
    headers = _auth_headers(pg_admin_user)
    report = _report(pg_client, headers)

    assert report["chain_order"] == [
        "clinic",
        "department",
        "owner",
        "day_snapshot",
    ]
    assert report["timezone"] == "Asia/Tashkent"
    assert report["clinic_today"], "clinic_today (tz SSOT) must be present"

    fields = {f["field"]: f for f in report["fields"]}
    for required in ("timezone", "queue_start_hour", "auto_close_time", "start_numbers", "max_per_day"):
        assert required in fields, f"missing clinic field entry: {required}"
    for entry in fields.values():
        assert set(entry) >= {"field", "level", "value", "live", "applied_when", "note"}, entry

    assert fields["timezone"]["level"] == "clinic"
    assert fields["timezone"]["live"] is True
    assert fields["queue_start_hour"]["level"] == "clinic"
    assert fields["queue_start_hour"]["live"] is True
    # dual semantics: live gate for online entry + frozen snapshot at day creation
    assert "day_creation_snapshot" in fields["queue_start_hour"]["applied_when"]
    assert fields["queue_start_hour"].get("snapshot_field") == "DailyQueue.online_start_time"


# ---------------------------------------------------------------
# 2. Start-number chain: owner > clinic; value = SSOT helper output
# ---------------------------------------------------------------


def test_start_number_owner_overrides_clinic(pg_client, pg_admin_user, pg_session):
    headers = _auth_headers(pg_admin_user)
    tag = "rq23a-sn"
    dept = _seed_department(pg_session, "rq23a-sn-dept")
    doctor_owner = _seed_doctor(pg_session, dept, "owner", start_number=8)
    doctor_default = _seed_doctor(pg_session, dept, "default", start_number=1)

    _set_queue_setting(pg_session, f"start_number_{tag}", 5)

    report = _report(pg_client, headers, department_id=dept.id, tag=tag)

    overrides = {o["doctor_id"]: o for o in report["department"]["owner_overrides"]}
    assert overrides[doctor_owner.id]["effective_start_number"] == 8
    assert overrides[doctor_owner.id]["source"] == "owner"
    assert overrides[doctor_default.id]["effective_start_number"] == 5
    assert overrides[doctor_default.id]["source"] == "clinic"

    # Anti-drift: the report must display exactly what the RQ-13.b SSOT
    # helper freezes into new days — no parallel re-derivation.
    from app.crud.queue_resource_routing import effective_day_start_number

    for doctor in (doctor_owner, doctor_default):
        ssot_value = effective_day_start_number(
            pg_session, doctor=doctor, queue_tag=tag
        )
        assert overrides[doctor.id]["effective_start_number"] == ssot_value


def test_resource_axis_registry_unconditional(pg_client, pg_admin_user, pg_session):
    from app.models.online_queue import QueueResource

    headers = _auth_headers(pg_admin_user)
    tag = "rq23a-res"
    resource = QueueResource(
        code="rq23a-res-1",
        queue_tag=tag,
        display_name="RQ-23.a resource",
        active=True,
        start_number_online=12,
        max_online_per_day=9,
    )
    pg_session.add(resource)
    pg_session.commit()
    pg_session.refresh(resource)

    _set_queue_setting(pg_session, f"start_number_{tag}", 5)
    report = _report(pg_client, headers, tag=tag)

    entries = {r["queue_resource_id"]: r for r in report["resources"]}
    assert entries[resource.id]["effective_start_number"] == 12
    assert entries[resource.id]["source"] == "registry"


# ---------------------------------------------------------------
# 3. Honest dead-field flags (nothing silently non-working)
# ---------------------------------------------------------------


def test_department_fields_live_flags(pg_client, pg_admin_user, pg_session):
    headers = _auth_headers(pg_admin_user)
    dept = _seed_department(pg_session, "rq23a-flags")

    report = _report(pg_client, headers, department_id=dept.id)
    qs = report["department"]["queue_settings"]

    assert qs["queue_prefix"]["live"] is True
    assert qs["queue_prefix"]["value"] == "RQ"

    for dead in (
        "enabled",
        "queue_type",
        "max_daily_queue",
        "max_concurrent_queue",
        "avg_wait_time",
        "show_on_display",
        "auto_close_time",
    ):
        assert dead in qs, f"missing department field entry: {dead}"
        assert qs[dead]["live"] is False, dead
        assert qs[dead]["note"], f"dead field must explain itself: {dead}"


def test_clinic_auto_close_time_is_display_only(pg_client, pg_admin_user, pg_session):
    headers = _auth_headers(pg_admin_user)
    _set_queue_setting(pg_session, "auto_close_time", "11:30")

    report = _report(pg_client, headers)
    fields = {f["field"]: f for f in report["fields"]}

    auto_close = fields["auto_close_time"]
    assert auto_close["value"] == "11:30"
    # The close ENGINE never reads this setting: it reads the
    # DailyQueue.online_end_time snapshot (from the never-persisted
    # queue_end_hour key → hardcoded 9). Display payloads do read it.
    assert auto_close["live"] is False
    assert "online_end_time" in auto_close["note"]


# ---------------------------------------------------------------
# 4. D-06 boundary: active day keeps its frozen snapshot
# ---------------------------------------------------------------


def test_active_day_snapshot_not_rewritten(pg_client, pg_admin_user, pg_session):
    from app.crud.clinic import clinic_today
    from app.models.online_queue import DailyQueue

    headers = _auth_headers(pg_admin_user)
    tag = "rq23a-day"
    dept = _seed_department(pg_session, "rq23a-day-dept")
    doctor = _seed_doctor(pg_session, dept, "day", start_number=1)

    _set_queue_setting(pg_session, f"start_number_{tag}", 5)
    _set_queue_setting(pg_session, "queue_start_hour", 7)

    today = clinic_today(pg_session)
    frozen = DailyQueue(
        day=today,
        specialist_id=doctor.id,
        queue_tag=tag,
        active=True,
        online_start_time="07:00",
        online_end_time="09:00",
        max_online_entries=15,
        start_number=5,
    )
    pg_session.add(frozen)
    pg_session.commit()
    pg_session.refresh(frozen)

    # Admin changes clinic settings AFTER the day is open.
    _set_queue_setting(pg_session, "queue_start_hour", 9)
    _set_queue_setting(pg_session, f"start_number_{tag}", 99)
    _set_queue_setting(pg_session, f"max_per_day_{tag}", 77)

    report = _report(pg_client, headers, department_id=dept.id, tag=tag)

    day_rows = [
        r
        for r in report["active_day"]
        if r["daily_queue_id"] == frozen.id
    ]
    assert day_rows, "today's frozen row must be reported"
    row = day_rows[0]
    assert row["source"] == "day_snapshot"
    assert row["start_number"] == 5
    assert row["online_start_time"] == "07:00"
    assert row["max_online_entries"] == 15

    # The DB row itself is untouched — D-06: «Новые настройки не меняют
    # выданные номера и историю текущего дня».
    pg_session.expire_all()
    reloaded = (
        pg_session.query(DailyQueue).filter(DailyQueue.id == frozen.id).first()
    )
    assert reloaded.start_number == 5
    assert reloaded.online_start_time == "07:00"
    assert reloaded.max_online_entries == 15

    # ...while the clinic level now reports the NEW values as the ones
    # future days will freeze.
    fields = {f["field"]: f for f in report["fields"]}
    assert fields["start_numbers"]["value"][tag] == 99
    assert fields["queue_start_hour"]["value"] == 9
