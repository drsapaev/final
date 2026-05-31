from datetime import date

from app.api.v1.endpoints import admin_doctors
from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.user import User


def test_admin_doctors_stats_route_dispatches_before_doctor_id(
    client,
    auth_headers,
    monkeypatch,
):
    class FakeAdminDoctorsStatsService:
        def __init__(self, db):
            self.db = db

        def get_doctors_stats(self):
            return {
                "total": 2,
                "active": 1,
                "inactive": 1,
                "by_specialty": {"cardiology": 1},
            }

    monkeypatch.setattr(
        admin_doctors,
        "AdminDoctorsStatsService",
        FakeAdminDoctorsStatsService,
    )

    response = client.get("/api/v1/admin/doctors/stats", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["by_specialty"] == {"cardiology": 1}


def test_available_doctor_users_excludes_already_linked_accounts(
    client,
    db_session,
    auth_headers,
):
    linked_user = User(
        username="linked_doc",
        email="linked@test.com",
        full_name="Linked Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    free_user = User(
        username="free_doc",
        email="free@test.com",
        full_name="Free Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add_all([linked_user, free_user])
    db_session.commit()
    db_session.refresh(linked_user)
    db_session.refresh(free_user)

    doctor = Doctor(
        user_id=linked_user.id,
        specialty="cardiology",
        cabinet="101",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    response = client.get("/api/v1/admin/doctors/available-users", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    returned_ids = {item["id"] for item in payload}
    assert free_user.id in returned_ids
    assert linked_user.id not in returned_ids

    response = client.get(
        f"/api/v1/admin/doctors/available-users?doctor_id={doctor.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    returned_ids = {item["id"] for item in payload}
    assert linked_user.id in returned_ids
    assert free_user.id in returned_ids


def test_admin_appointments_returns_enriched_doctor_and_effective_cabinet(
    client,
    db_session,
    auth_headers,
    test_patient,
):
    doctor_user = User(
        username="enriched_doc",
        email="enriched@test.com",
        full_name="Enriched Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(doctor_user)
    db_session.commit()
    db_session.refresh(doctor_user)

    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="cardiology",
        cabinet="201",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="cardiology",
        cabinet_number="202",
        active=True,
    )
    db_session.add(queue)

    appointment = Appointment(
        patient_id=test_patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today(),
        appointment_time="09:30",
        notes="Контрольный визит",
        status="pending",
    )
    db_session.add(appointment)
    db_session.commit()

    response = client.get("/api/v1/admin/appointments", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload

    item = next((row for row in payload if row["id"] == appointment.id), None)
    assert item is not None
    assert item["doctorName"] == "Enriched Doctor"
    assert item["doctorSpecialization"] == "cardiology"
    assert item["doctorCabinet"] == "201"
    assert item["queueCabinet"] == "202"
    assert item["effectiveCabinet"] == "202"
    assert item["hasIntegrityWarnings"] is True
    assert "queue_cabinet_stale" in item["integrityWarnings"]


def test_queue_cabinet_info_reports_sync_status_and_rejects_manual_canonical_changes(
    client,
    db_session,
    auth_headers,
):
    doctor_user = User(
        username="queue_doc",
        email="queue@test.com",
        full_name="Queue Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(doctor_user)
    db_session.commit()
    db_session.refresh(doctor_user)

    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="dermatology",
        cabinet="305",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="dermatology",
        cabinet_number="399",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    response = client.get("/api/v1/admin/queues/cabinet-info", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    item = next((row for row in payload if row["id"] == queue.id), None)
    assert item is not None
    assert item["doctor_cabinet"] == "305"
    assert item["effective_cabinet"] == "399"
    assert item["sync_status"] == "stale"

    response = client.put(
        f"/api/v1/admin/queues/{queue.id}/cabinet-info",
        json={"cabinet_number": "777"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Канонический номер кабинета" in response.json()["detail"]

    response = client.post(
        "/api/v1/admin/queues/sync-cabinet-info",
        headers=auth_headers,
    )
    assert response.status_code == 200

    db_session.refresh(queue)
    assert queue.cabinet_number == "305"
