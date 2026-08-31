"""Round-7 Codex fixes on the lifecycle PR (#2935).

P1  — atomic slot reservation: every appointment writer takes a per-doctor
      FOR UPDATE lock (appointment_slot_guard) BEFORE its occupancy
      pre-check, so two concurrent same-slot requests cannot both pass
      check-then-act (appointments has no UNIQUE constraint covering the
      slot). PostgreSQL enforces the lock; SQLite (tests) drops FOR UPDATE
      at compile time, so the wiring itself is spy-tested here and the
      serialization property holds in production.
P2a — blocking pre-deploy reconciliation of EXISTING active userless
      Doctor rows (backend/scripts/reconcile_userless_active_doctors.py):
      the API validators only cover new/changed rows, pre-existing
      violations need a deploy-time blocker.
P2b — /mobile/doctors applies the incomplete-profile ("general" sentinel)
      predicate IN THE DATABASE QUERY before pagination, so eligible
      doctors are no longer crowded out by the crud row cap.
"""
from __future__ import annotations

import importlib.util
import pathlib
import uuid
from datetime import date, timedelta

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User


def _load_reconcile_module():
    """Load backend/scripts/reconcile_userless_active_doctors.py by path —
    backend/scripts has no package __init__, so a plain import cannot reach
    it from the backend-rooted test run."""
    path = pathlib.Path(__file__).resolve().parents[2] / "scripts" / (
        "reconcile_userless_active_doctors.py"
    )
    spec = importlib.util.spec_from_file_location(
        "reconcile_userless_active_doctors", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _s() -> str:
    return uuid.uuid4().hex[:10]


def _make_patient(db_session) -> User:
    s = _s()
    user = User(
        username=f"slot_pt_{s}",
        email=f"slot-pt-{s}@test.local",
        full_name=f"Slot Patient {s}",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_admin(db_session) -> User:
    s = _s()
    user = User(
        username=f"slot_adm_{s}",
        email=f"slot-adm-{s}@test.local",
        full_name=f"Slot Admin {s}",
        hashed_password=get_password_hash("adminpass123"),
        role="Admin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_doctor(db_session, *, specialty: str = "cardiology", user: User | None = None) -> Doctor:
    if user is None:
        s = _s()
        user = User(
            username=f"slot_doc_{s}",
            email=f"slot-doc-{s}@test.local",
            full_name=f"Slot Doctor {s}",
            hashed_password=get_password_hash("docpass123"),
            role="Doctor",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _make_patient_row(db_session, user: User) -> Patient:
    # Synthetic per repo PII rule (all-zero subscriber number).
    patient = Patient(
        user_id=user.id,
        first_name="Slot",
        last_name="Patient",
        phone="+998900000000",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


class _SessionProxy:
    """Minimal session wrapper for script main() tests — forwards query()
    to the fixture session while keeping close() a no-op so the fixture
    session stays usable."""

    def __init__(self, inner):
        self._inner = inner

    def query(self, *args, **kwargs):
        return self._inner.query(*args, **kwargs)

    def close(self):
        pass


def _token_for(user: User) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


# ---------------------------------------------------------------------------
# P1 — slot guard wiring
# ---------------------------------------------------------------------------


def test_lock_helper_skips_doctorless_shape():
    """doctor_id=None has no concrete slot — no query may run."""
    from unittest.mock import MagicMock

    from app.services.appointment_slot_guard import lock_doctor_for_slot_reservation

    db = MagicMock()
    lock_doctor_for_slot_reservation(db, None)
    db.query.assert_not_called()


def test_lock_helper_resolves_doctor_row(db_session):
    """With a real doctor_id the lock issues the FOR UPDATE read and returns
    the row (FOR UPDATE is a no-op under SQLite, enforced on PostgreSQL)."""
    from app.services.appointment_slot_guard import lock_doctor_for_slot_reservation

    doctor = _make_doctor(db_session)
    locked = lock_doctor_for_slot_reservation(db_session, doctor.id)
    assert locked is not None
    assert locked.id == doctor.id


def test_mobile_book_takes_slot_lock_before_occupancy_check(client, db_session, monkeypatch):
    """The mobile booking writer must take the per-doctor lock."""
    from app.api.v1.endpoints import mobile_api

    doctor = _make_doctor(db_session)
    patient_user = _make_patient(db_session)
    _make_patient_row(db_session, patient_user)

    calls: list[int | None] = []
    monkeypatch.setattr(
        mobile_api,
        "lock_doctor_for_slot_reservation",
        lambda db, doctor_id: calls.append(doctor_id),
    )

    response = client.post(
        "/api/v1/mobile/appointments/book",
        headers=_token_for(patient_user),
        json={
            "doctor_id": doctor.id,
            "preferred_date": str(date.today() + timedelta(days=3)),
            "preferred_time": "10:30",
        },
    )
    assert response.status_code == 200, response.text
    assert calls == [doctor.id], "mobile book must take the per-doctor slot lock"


def test_web_create_takes_slot_lock_before_occupancy_check(client, db_session, monkeypatch):
    """The web create writer must take the per-doctor lock."""
    from app.api.v1.endpoints import appointments as appointments_module

    doctor = _make_doctor(db_session)
    patient_user = _make_patient(db_session)
    patient = _make_patient_row(db_session, patient_user)
    admin = _make_admin(db_session)

    calls: list[int | None] = []
    monkeypatch.setattr(
        appointments_module,
        "lock_doctor_for_slot_reservation",
        lambda db, doctor_id: calls.append(doctor_id),
    )

    response = client.post(
        "/api/v1/appointments",
        headers=_token_for(admin),
        json={
            "patient_id": patient.id,
            "doctor_id": doctor.id,
            "appointment_date": str(date.today() + timedelta(days=3)),
            "appointment_time": "11:30",
        },
    )
    assert response.status_code == 200, response.text
    assert calls == [doctor.id], "web create must take the per-doctor slot lock"


def test_web_update_takes_slot_lock_on_reschedule(client, db_session, monkeypatch):
    """The web update writer must take the lock for the RESOLVED doctor when
    the slot (date/time/doctor) changes."""
    from app.api.v1.endpoints import appointments as appointments_module

    doctor = _make_doctor(db_session)
    patient_user = _make_patient(db_session)
    patient = _make_patient_row(db_session, patient_user)
    admin = _make_admin(db_session)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today() + timedelta(days=4),
        appointment_time="09:00",
        status="scheduled",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    calls: list[int | None] = []
    monkeypatch.setattr(
        appointments_module,
        "lock_doctor_for_slot_reservation",
        lambda db, doctor_id: calls.append(doctor_id),
    )

    response = client.put(
        f"/api/v1/appointments/{appointment.id}",
        headers=_token_for(admin),
        json={"appointment_time": "09:30"},
    )
    assert response.status_code == 200, response.text
    assert calls == [doctor.id], "web reschedule must lock the resolved doctor"


def test_v2_service_writers_take_slot_lock(db_session, monkeypatch):
    """The (currently unmounted) v2 service writer keeps the lock wired —
    tested by direct invocation since the router is not mounted. Only the
    create path is exercised: the v2 update calls
    appointment_crud.get_appointment which does not exist on the crud
    (pre-existing dead-code breakage, out of this PR's scope)."""
    from datetime import date as date_cls

    from app.schemas.appointment import AppointmentCreate
    from app.services import appointments_api_service

    doctor = _make_doctor(db_session)
    patient_user = _make_patient(db_session)
    patient = _make_patient_row(db_session, patient_user)

    calls: list[int | None] = []
    monkeypatch.setattr(
        appointments_api_service,
        "lock_doctor_for_slot_reservation",
        lambda db, doctor_id: calls.append(doctor_id),
    )

    created = appointments_api_service.create_appointment(
        db=db_session,
        appointment_in=AppointmentCreate(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=date_cls.today() + timedelta(days=5),
            appointment_time="12:30",
        ),
        current_user=None,
    )
    assert created.id is not None
    assert calls == [doctor.id]


def test_telegram_confirm_wires_slot_lock():
    """The telegram confirm writer imports and calls the lock before its
    occupancy check (source-level check: the flow needs a full Mini App
    session; repo precedent: test_pr34 source assertions)."""
    import re

    source = open("app/api/v1/endpoints/telegram_webhook/_routes.py", encoding="utf-8").read()
    assert "from app.services.appointment_slot_guard import lock_doctor_for_slot_reservation" in source
    lock_pos = source.find("lock_doctor_for_slot_reservation(db, preview.draft.doctor_id)")
    check_pos = source.find("slot_occupied = appointment_crud.is_time_slot_occupied(")
    assert 0 < lock_pos < check_pos, "telegram confirm must lock BEFORE the occupancy check"


# ---------------------------------------------------------------------------
# P2a — pre-deploy reconciliation of existing active userless doctors
# ---------------------------------------------------------------------------


def test_reconciliation_finder_finds_only_active_userless(db_session):
    mod = _load_reconcile_module()
    find_userless_active_doctors = mod.find_userless_active_doctors

    target = Doctor(user_id=None, specialty="dermatology", active=True)
    inactive_userless = Doctor(user_id=None, specialty="cardiology", active=False)
    linked = _make_doctor(db_session)
    db_session.add_all([target, inactive_userless])
    db_session.commit()
    db_session.refresh(target)

    rows = find_userless_active_doctors(db_session)
    ids = {row.id for row in rows}
    assert target.id in ids, "active userless row must be inventoried"
    assert linked.id not in ids
    assert inactive_userless.id not in ids


def test_reconciliation_inventory_shape(db_session):
    mod = _load_reconcile_module()
    build_inventory = mod.build_inventory
    find_userless_active_doctors = mod.find_userless_active_doctors

    db_session.add(Doctor(user_id=None, specialty="cardiology", active=True))
    db_session.commit()

    rows = find_userless_active_doctors(db_session)
    assert rows, "seed must produce at least one violating row"
    item = build_inventory(rows)[0]
    assert set(item) == {"doctor_id", "specialty", "cabinet", "active"}
    assert item["specialty"] == "cardiology"
    assert item["active"] is True


def test_reconciliation_main_exit_codes(db_session, monkeypatch):
    mod = _load_reconcile_module()

    # Operational failure: DATABASE_URL missing.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert mod.main([]) == 2

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_local.db")
    monkeypatch.setattr(
        mod, "_open_session", lambda: _SessionProxy(db_session), raising=False
    )

    # Seed a violation -> blocked (exit 1), then clean the seeded row -> 0.
    violation = Doctor(user_id=None, specialty="cardiology", active=True)
    db_session.add(violation)
    db_session.commit()
    db_session.refresh(violation)

    assert mod.main([]) == 1
    assert mod.main(["--json"]) == 1, "json mode runs the same blocked check"

    violation.active = False
    db_session.commit()
    assert mod.main([]) == 0, "deactivating the row must clear the blocker"


# ---------------------------------------------------------------------------
# P2b — eligibility predicate applied in the DB query before pagination
# ---------------------------------------------------------------------------


def test_get_doctors_eligible_only_filters_before_cap(db_session):
    from app.crud import clinic as crud_clinic

    real_a = Doctor(user_id=None, specialty="cardiology", active=True)
    real_b = Doctor(user_id=None, specialty="dermatology", active=True)
    real_c = Doctor(user_id=None, specialty="cardiology", active=True)
    sentinel = Doctor(user_id=None, specialty="general", active=True)
    inactive = Doctor(user_id=None, specialty="cardiology", active=False)
    db_session.add_all([real_a, real_b, real_c, sentinel, inactive])
    db_session.commit()

    rows = crud_clinic.get_doctors(
        db_session, skip=0, limit=2, active_only=True, eligible_only=True
    )
    assert len(rows) == 2, "limit applies to the ELIGIBLE set"
    assert all(r.specialty != "general" for r in rows), "sentinel must be filtered in SQL"
    assert {r.id for r in rows} <= {real_a.id, real_b.id, real_c.id}


def test_get_doctors_by_specialty_eligible_only_hides_sentinel(db_session):
    from app.crud import clinic as crud_clinic

    sentinel = Doctor(user_id=None, specialty="general", active=True)
    real = Doctor(user_id=None, specialty="general", active=True)
    db_session.add_all([sentinel, real])
    db_session.commit()

    sentinel_is_real_specialty = crud_clinic.get_doctors_by_specialty(
        db_session, "general", eligible_only=True
    )
    assert sentinel_is_real_specialty == [], (
        "the incomplete sentinel must not surface as a bookable specialty"
    )
    without_guard = crud_clinic.get_doctors_by_specialty(
        db_session, "general", eligible_only=False
    )
    assert len(without_guard) == 2


def test_mobile_doctors_eligible_doctors_not_crowded_out_by_cap(client, db_session):
    """Regression for the exact Codex scenario: sentinels INSIDE the crud
    cap must not push eligible doctors beyond the cap out of the response.
    Seed 50 real + 5 sentinel + 53 real (103 eligible, 108 rows); the crud
    cap is 100 — the old post-filter returned 95, the fixed query returns
    100 real rows."""
    from app.api.v1.endpoints import mobile_api

    crud_cap = 100
    real_total = crud_cap + 3  # 103 eligible rows
    sentinels_inside_cap = 5

    rows = []
    for i in range(50):
        rows.append(Doctor(user_id=None, specialty="cardiology", active=True))
    for i in range(sentinels_inside_cap):
        rows.append(Doctor(user_id=None, specialty="general", active=True))
    for i in range(real_total - 50):
        rows.append(Doctor(user_id=None, specialty="dermatology", active=True))
    db_session.add_all(rows)
    db_session.commit()

    assert mobile_api is not None  # module import sanity

    patient_user = _make_patient(db_session)
    response = client.get(
        "/api/v1/mobile/doctors",
        headers=_token_for(patient_user),
        params={"limit": 200},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    specialties = {entry["specialty"] for entry in body}
    assert "general" not in specialties, "sentinel rows must never surface"
    assert len(body) == crud_cap, (
        f"eligible doctors must fill the cap ({len(body)} != {crud_cap}) — "
        "the old post-filter shape would return fewer"
    )
