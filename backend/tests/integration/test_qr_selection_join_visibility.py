"""RQ-09 backend slice: the PUBLIC clinic-wide QR selection must mirror
the join visibility/eligibility contract exactly.

Defect (F-08 / plan RQ-09 result «учитывает active/show_on_qr_page
согласованно; выключение всех направлений дает корректное пустое
состояние, а не дефолтные предложения; видимый выбор соответствует
допустимому join»):

``QRQueueService._get_clinic_wide_selectable_specialists`` — the SSOT
behind ``selectable_specialists`` in the public token info/start payload —
applies DIFFERENT constraints than the join it advertises:

1. a stale hard-coded ``hidden_profile_keys = {"ecg", "general"}`` set,
   although PR-28 moved QR visibility to ADMIN-controlled flags
   (``QueueProfile.is_active`` + ``show_on_qr_page``,
   ``QueueBusinessService.QR_HIDDEN_PROFILE_KEYS == set()``): an admin who
   explicitly shows the echokg («ЭКГ») direction is silently overridden —
   the direction stays hidden on the public page while the join accepts it;
2. a fallback to ``INITIAL_QUEUE_PROFILES`` when no profile row is
   visible: hiding EVERY direction still advertises default doctor
   suggestions the join then rejects («Специалист недоступен для
   QR-записи») — no correct empty state;
3. no owner-eligibility contract on the advertised doctors: the canonical
   booking contract (``services/appointment_eligibility.py``, decision
   #13 — «the QR/online queue join and the public ... listing exclude
   them») requires an active Doctor with a completed specialty whose owner
   account exists, is active and carries a doctor-family role. The
   selector applied only ``Doctor.active``, so deactivated-owner ghosts,
   incomplete «general» placeholders and the seeded RESOURCE synthetic
   doctors (0055: ``lab_resource`` role «Lab», ``ecg_resource» role
   «Nurse») surfaced as joinable doctor cards.

Scope of this slice: the SELECTION side only (first-touch
``backend/app/services/qr_queue/_specialists.py``). The join path
(``queue_svc/_operations.py``) is NOT modified here; two join-side gaps
found while tracing (legacy doctor-id join does not re-check the
owner-eligibility contract; ``specialist_id_override`` Doctor.id vs
QueueProfile.id ambiguity) are REGISTERED as child defects, not fixed
in passing.

Disposable PostgreSQL: the module provisions its own scratch database
(rq09_check), runs ``alembic upgrade head`` against it and drops it at
the end. Skips (NOT_RUN, per plan P0) when no disposable PostgreSQL
server is reachable. SQLite is never a substitute here. Only synthetic
data is used (synthetic names/phones), no PHI/PII.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import psycopg
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRATCH_DB = "rq09_check"

sys.path.insert(0, str(BACKEND_DIR))


def _clinic_day():
    """Join/start classifies the token day in the CLINIC timezone."""
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _candidate_admin_urls() -> list[str]:
    """Admin DSNs for scratch provisioning — LOCAL servers only."""
    urls: list[str] = []

    explicit = os.getenv("RQ09_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)

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

    return urls


def _scratch_url(admin_url: str) -> tuple[str, str]:
    """(psycopg conninfo, sqlalchemy URL) for the scratch database."""
    u = make_url(admin_url)
    return (
        str(u.set(drivername="postgresql", database=SCRATCH_DB)),
        str(u.set(drivername="postgresql+psycopg", database=SCRATCH_DB)),
    )


def _preprovisioned_local_url() -> str | None:
    """A pre-provisioned LOCAL disposable DATABASE_URL (CI pattern)."""
    env_url = os.getenv("DATABASE_URL", "").strip()
    u = make_url(env_url) if env_url else None
    if u is None:
        return None
    is_local = (u.host or "") in {"localhost", "127.0.0.1", "::1"} or (
        u.host is None and "host" in u.query
    )
    if not is_local:
        return None
    return env_url if env_url.startswith("postgresql+psycopg") else str(
        u.set(drivername="postgresql+psycopg")
    )


@pytest.fixture(scope="module")
def pg_engine():
    """Disposable PostgreSQL engine (or skip — NOT_RUN per plan P0).

    Source 1: ``RQ09_PG_ADMIN_URL`` — admin dsn on a local disposable
    server; the module provisions scratch rq09_check, applies
    ``alembic upgrade head`` and drops it afterwards. On any provisioning
    failure it FALLS BACK to source 2 instead of erroring.
    Source 2: pre-provisioned local ``DATABASE_URL`` already at alembic
    head (CI pattern — the fixture only ASSERTS the schema).
    """
    admin_url = None
    last_error: Exception | None = None
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            admin_url = candidate
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    sa_url: str | None = None
    if admin_url is not None:
        _conn, sa_url = _scratch_url(admin_url)
        try:
            with psycopg.connect(admin_url, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
                c.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

            env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
            import subprocess  # noqa: E402

            r = subprocess.run(
                [sys.executable, "-m", "alembic", "-c", "alembic.ini",
                 "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd=str(BACKEND_DIR),
                env=env,
            )
            if r.returncode != 0:
                print(
                    f"[rq09] scratch provisioning failed "
                    f"(rc={r.returncode}); falling back to pre-provisioned "
                    f"DATABASE_URL",
                    file=sys.stderr,
                )
                sa_url = None
        except Exception as exc:  # noqa: BLE001
            print(
                f"[rq09] scratch provisioning failed ({exc!r}); falling "
                f"back to pre-provisioned DATABASE_URL",
                file=sys.stderr,
            )
            sa_url = None

    if sa_url is None:
        sa_url = _preprovisioned_local_url()
        if sa_url is None:
            pytest.skip(
                "disposable PostgreSQL unavailable — RQ-09 PG acceptance "
                f"NOT_RUN (last error: {last_error})"
            )

    engine = create_engine(sa_url, future=True)
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
    if not version:
        pytest.skip(
            "DATABASE_URL points at a local PostgreSQL without an alembic "
            "schema — provision it with 'alembic upgrade head' first; the "
            "fixture never creates schemas on a pre-provisioned database"
        )

    yield engine

    engine.dispose()
    if admin_url is not None and sa_url.endswith(SCRATCH_DB):
        try:
            with psycopg.connect(admin_url, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        except Exception:  # noqa: BLE001
            pass


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


def _doctor_with_user(
    pg_session,
    *,
    specialty: str,
    label: str,
    user_active: bool = True,
    role: str = "Doctor",
    doctor_id: int | None = None,
):
    """Synthetic doctor with an owner account (linkage contract #13)."""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.user import User

    username = f"rq09_{label}"
    user = pg_session.query(User).filter(User.username == username).first()
    if user is None:
        user = User(
            username=username,
            email=f"rq09-{label}@synthetic.test",
            full_name=f"RQ-09 Synthetic {label}",
            hashed_password=get_password_hash("rq09-synthetic-pw"),
            role=role,
            is_active=user_active,
        )
        pg_session.add(user)
        pg_session.flush()
    else:
        user.is_active = user_active
        user.role = role
        pg_session.flush()

    doctor = Doctor(
        **({"id": doctor_id} if doctor_id is not None else {}),
        user_id=user.id,
        specialty=specialty,
        cabinet=f"RQ09-{label}",
        active=True,
    )
    pg_session.add(doctor)
    pg_session.commit()
    pg_session.refresh(user)
    pg_session.refresh(doctor)
    return user, doctor


def _clinic_wide_token(pg_session, value: str):
    from app.models.online_queue import QueueToken

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=value,
        day=_clinic_day(),
        specialist_id=None,
        department="clinic",
        is_clinic_wide=True,
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    pg_session.add(token)
    pg_session.commit()
    return token


def _visible_profile_keys(pg_session) -> dict[str, bool]:
    """key -> show_on_qr_page for every seeded profile row."""
    from app.models.queue_profile import QueueProfile

    return {
        key: show
        for key, show in pg_session.query(
            QueueProfile.key, QueueProfile.show_on_qr_page
        ).all()
    }


def _set_all_profiles_hidden(pg_session) -> dict[str, bool]:
    from app.models.queue_profile import QueueProfile

    original = _visible_profile_keys(pg_session)
    pg_session.query(QueueProfile).update({QueueProfile.show_on_qr_page: False})
    pg_session.commit()
    return original


def _restore_profile_visibility(pg_session, original: dict[str, bool]) -> None:
    from app.models.queue_profile import QueueProfile

    for key, show in original.items():
        pg_session.query(QueueProfile).filter(QueueProfile.key == key).update(
            {QueueProfile.show_on_qr_page: show}
        )
    pg_session.commit()


def _selectable(pg_client: TestClient, token_value: str) -> list[dict]:
    info_resp = pg_client.get(f"/api/v1/queue/qr-tokens/{token_value}/info")
    assert info_resp.status_code == 200, info_resp.text
    return info_resp.json().get("selectable_specialists") or []


# ---------------------------------------------------------------------------
# 1. All directions hidden -> correct EMPTY state, no default suggestions
# ---------------------------------------------------------------------------


@pytest.mark.queue
def test_all_profiles_hidden_yields_empty_selection(
    pg_client, pg_session, monkeypatch
):
    """S-07 (RQ-09): «выключение всех направлений дает корректное пустое
    состояние, а не дефолтные предложения»."""
    from app.services.queue_service import QueueBusinessService

    monkeypatch.setattr(
        QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )

    original = _set_all_profiles_hidden(pg_session)
    try:
        # A perfectly healthy cardiology doctor: the INITIAL_QUEUE_PROFILES
        # fallback used to advertise him even with every direction hidden.
        _doctor_with_user(pg_session, specialty="cardiology", label="cardio_ok")
        _clinic_wide_token(pg_session, "rq09-token-all-hidden")
        pg_session.expire_all()

        selectable = _selectable(pg_client, "rq09-token-all-hidden")
        assert selectable == [], (
            "hidden-everything must return an EMPTY selection, got "
            f"{selectable!r}"
        )

        # and the start payload (the one QueueJoin actually renders) too
        start_resp = pg_client.post(
            "/api/v1/queue/join/start",
            json={"token": "rq09-token-all-hidden"},
        )
        assert start_resp.status_code == 200, start_resp.text
        assert start_resp.json()["queue_info"]["selectable_specialists"] == []
    finally:
        _restore_profile_visibility(pg_session, original)


# ---------------------------------------------------------------------------
# 2. Admin-shown «ЭКГ» direction: selectable AND joinable (visible == join)
# ---------------------------------------------------------------------------


@pytest.mark.queue
def test_admin_shown_ecg_direction_is_selectable_and_joinable(
    pg_client, pg_session, monkeypatch
):
    """S-07 (RQ-09): admin-controlled visibility — an explicitly shown
    profile must surface on the public page and the advertised doctor must
    survive the join (visible selection == allowed join)."""
    from app.services.queue_service import QueueBusinessService

    monkeypatch.setattr(
        QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )

    # Seeded 0055 echokg profile (show_on_qr_page=true, queue_tags=["ecg"]).
    _user, doctor = _doctor_with_user(
        pg_session,
        specialty="ecg",
        label="ecg_real",
        role="Doctor",
        doctor_id=9201,
    )
    _clinic_wide_token(pg_session, "rq09-token-ecg-shown")
    pg_session.expire_all()

    selectable = _selectable(pg_client, "rq09-token-ecg-shown")
    entry = next((s for s in selectable if s["id"] == doctor.id), None)
    assert entry is not None, (
        "admin-shown echokg (ЭКГ) direction must surface its doctor; got "
        f"{selectable!r}"
    )
    assert entry["specialty"] == "echokg"
    assert entry["doctor_name"] == "RQ-09 Synthetic ecg_real"

    start_resp = pg_client.post(
        "/api/v1/queue/join/start", json={"token": "rq09-token-ecg-shown"}
    )
    assert start_resp.status_code == 200, start_resp.text
    session_token = start_resp.json()["session_token"]

    complete_resp = pg_client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "RQ09 Synthetic Patient",
            "phone": "+998900000901",
            "specialist_ids": [doctor.id],
        },
    )
    assert complete_resp.status_code == 200, complete_resp.text
    payload = complete_resp.json()
    assert payload["success"] is True
    assert payload["errors"] is None
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["queue_number"] >= 1
    assert payload["entries"][0]["specialist_id"] == doctor.id


# ---------------------------------------------------------------------------
# 3. Ghost / incomplete / resource-synthetic owners are NOT advertised
# ---------------------------------------------------------------------------


@pytest.mark.queue
def test_ghost_incomplete_and_resource_owners_not_selectable(
    pg_client, pg_session, monkeypatch
):
    """S-07 (RQ-09): «неактивный врач/пользователь», incomplete «general»
    placeholder and the seeded 0055 resource synthetics must not appear as
    joinable doctor cards (canonical owner-eligibility contract)."""
    from app.models.clinic import Doctor
    from app.models.queue_profile import QueueProfile
    from app.services.queue_service import QueueBusinessService

    monkeypatch.setattr(
        QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0)
    )

    # (a) owner-deactivated ghost: Doctor row active, owner account off.
    _user, ghost = _doctor_with_user(
        pg_session,
        specialty="cardiology",
        label="ghost_owner",
        user_active=False,
        doctor_id=9202,
    )

    # (b) incomplete «general» placeholder behind an admin-shown profile:
    # even when a visible profile tags "general", the placeholder must not
    # surface (join rejects it in BOTH paths).
    general_profile = QueueProfile(
        key="rq09_general_check",
        title="General check",
        title_ru="Общая проверка",
        queue_tags=["general"],
        display_order=90,
        is_active=True,
        show_on_qr_page=True,
    )
    pg_session.add(general_profile)
    _user2, incomplete = _doctor_with_user(
        pg_session,
        specialty="general",
        label="incomplete",
        role="Doctor",
        doctor_id=9203,
    )
    pg_session.commit()

    # (c) the seeded 0055 resource synthetics: lab_resource (owner role
    # «Lab») — Doctor rows active with active owners, but not doctor-family
    # roles; they belong to the RESOURCE surface, not doctor cards.
    lab_resource = (
        pg_session.query(Doctor)
        .filter(Doctor.specialty == "lab", Doctor.active == True)  # noqa: E712
        .first()
    )
    assert lab_resource is not None, "seeded lab_resource doctor expected"

    _clinic_wide_token(pg_session, "rq09-token-ghosts")
    pg_session.expire_all()

    selectable = _selectable(pg_client, "rq09-token-ghosts")
    ids = {s["id"] for s in selectable}

    assert ghost.id not in ids, (
        "owner-deactivated doctor must not be advertised on the public page"
    )
    assert incomplete.id not in ids, (
        "incomplete «general» placeholder must not be advertised"
    )
    assert lab_resource.id not in ids, (
        "resource synthetic (owner role Lab) must not be advertised as a "
        "doctor card"
    )
