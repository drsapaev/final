"""FU-1 + FU-2 (D-4/D-5): department schedule guard + no cross-doctor fallback.

FU-1: GET /appointments/department/{department}/schedule — mirrors the
PR4 doctor-schedule ownership contract:
- Admin/Registrar (+superuser): any department;
- doctor-capable roles: only their OWN department (Doctor.department_id);
- Patient and every other role: denied.
The legacy implementation compared the `department` RELATIONSHIP to a
raw string and read a non-existent `apt.reason` column — 500 for every
non-empty schedule (same defect class PR4 repaired on the doctor twin).

FU-2: GET /doctor/{specialty}/queue/today — the legacy fallback silently
resolved ANY OTHER active doctor of the specialty when the caller has no
Doctor row (audit F4, security-adjacent). Decision D-5: no substitution
— 403.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.department import Department
from app.models.patient import Patient
from app.models.user import User


# ===================== fixtures/helpers =====================


def _department(db_session, key: str = "cardio") -> Department:
    dep = db_session.query(Department).filter(Department.key == key).first()
    if dep:
        return dep
    dep = Department(key=key, name_ru=f"Отделение {key}", active=True)
    db_session.add(dep)
    db_session.commit()
    db_session.refresh(dep)
    return dep


def _doctor_with_user(
    db_session, *, specialty: str, department: Department | None, label: str
) -> tuple[User, Doctor]:
    user = User(
        username=f"fu2_{label}",
        email=f"fu2-{label}@test.com",
        full_name=f"FU2 {label}",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
        department_id=department.id if department else None,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _headers_for(user: User) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _patient(db_session) -> Patient:
    patient = Patient(
        first_name="Dept",
        last_name="Sched",
        phone="+998900000001",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _appointment(
    db_session, doctor: Doctor, patient: Patient, department: Department
) -> Appointment:
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=department.id,
        appointment_date=date.today() + timedelta(days=1),
        appointment_time="11:00",
        status="scheduled",
        notes="department schedule row",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


# ===================== FU-1: department schedule guard =====================


def test_department_schedule_admin_reads_any(client, db_session):
    dep = _department(db_session, "cardio")
    user, doctor = _doctor_with_user(
        db_session, specialty="cardiology", department=dep, label="adm"
    )
    patient = _patient(db_session)
    appointment = _appointment(db_session, doctor, patient, dep)

    response = client.get(
        f"/api/v1/appointments/department/{dep.key}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(_admin(db_session)),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["department"] == dep.key
    ids = [entry["id"] for entry in body["appointments"]]
    assert appointment.id in ids
    # repaired serializer: notes present, no 500
    row = next(e for e in body["appointments"] if e["id"] == appointment.id)
    assert row["notes"] == "department schedule row"
    assert row["department_id"] == dep.id


def _admin(db_session) -> User:
    from app.models.user import User as UserModel

    admin = (
        db_session.query(UserModel).filter(UserModel.role == "Admin").first()
    )
    if admin is None:
        admin = UserModel(
            username="fu2_admin",
            email="fu2-admin@test.com",
            full_name="FU2 Admin",
            hashed_password=get_password_hash("secret123"),
            role="Admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
    return admin


def test_department_schedule_doctor_of_same_department_allowed(client, db_session):
    dep = _department(db_session, "cardio")
    user, doctor = _doctor_with_user(
        db_session, specialty="cardiology", department=dep, label="own"
    )
    patient = _patient(db_session)
    _appointment(db_session, doctor, patient, dep)

    response = client.get(
        f"/api/v1/appointments/department/{dep.key}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user),
    )
    assert response.status_code == 200, response.text


def test_department_schedule_doctor_of_other_department_denied(client, db_session):
    own_dep = _department(db_session, "cardio")
    other_dep = _department(db_session, "dental")
    user, _doctor = _doctor_with_user(
        db_session, specialty="cardiology", department=own_dep, label="other"
    )
    # doctor_b owns the other department's schedule
    _user_b, _doctor_b = _doctor_with_user(
        db_session, specialty="dentistry", department=other_dep, label="other_b"
    )
    patient = _patient(db_session)
    _appointment(db_session, _doctor_b, patient, other_dep)

    response = client.get(
        f"/api/v1/appointments/department/{other_dep.key}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user),
    )
    assert response.status_code == 403, response.text


def test_department_schedule_doctor_without_department_denied(client, db_session):
    _dep = _department(db_session, "cardio")
    user, _doctor = _doctor_with_user(
        db_session, specialty="cardiology", department=None, label="nodep"
    )

    response = client.get(
        "/api/v1/appointments/department/cardio/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user),
    )
    assert response.status_code == 403, response.text


def test_department_schedule_patient_denied(client, db_session):
    dep = _department(db_session, "cardio")

    patient_user = User(
        username="fu2_patient",
        email="fu2-patient@test.com",
        full_name="FU2 Patient User",
        hashed_password=get_password_hash("secret123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(patient_user)
    db_session.commit()
    db_session.refresh(patient_user)

    response = client.get(
        f"/api/v1/appointments/department/{dep.key}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(patient_user),
    )
    assert response.status_code == 403, response.text


def test_department_schedule_unknown_department_404(client, db_session):
    response = client.get(
        "/api/v1/appointments/department/no-such-department/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(_admin(db_session)),
    )
    assert response.status_code == 404, response.text


# ===================== FU-2: no cross-doctor fallback =====================


def test_doctor_queue_today_own_doctor_still_works(client, db_session, test_patient):
    """A doctor-capable caller WITH an own active Doctor row keeps working."""
    dep = None
    user, doctor = _doctor_with_user(
        db_session, specialty="cardiology", department=dep, label="ownq"
    )

    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="cardiology",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    db_session.add(
        OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="waiting",
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(user),
    )
    assert response.status_code == 200, response.text


def test_doctor_queue_today_no_doctor_row_gets_403_not_someone_else(
    client, db_session, test_doctor_user, test_patient
    ):
    """D-5: a doctor-capable user WITHOUT an own Doctor row must get 403 —
    the legacy fallback substituted ANY other active doctor of the
    specialty (cross-doctor exposure)."""
    # a colleague's queue with real entries
    colleague = Doctor(user_id=None, specialty="cardiology", active=True)
    db_session.add(colleague)
    db_session.commit()
    db_session.refresh(colleague)

    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    queue = DailyQueue(
        day=date.today(),
        specialist_id=colleague.id,
        queue_tag="cardiology",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    db_session.add(
        OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="registrar",
            status="waiting",
        )
    )
    db_session.commit()

    # test_doctor_user has no Doctor row in this test's database state
    response = client.get(
        "/api/v1/doctor/cardiology/queue/today",
        headers=_headers_for(test_doctor_user),
    )
    assert response.status_code == 403, response.text
    body = response.json()
    entries = body.get("entries") or body.get("data", {}).get("entries")
    assert not entries, "no colleague data may leak"
