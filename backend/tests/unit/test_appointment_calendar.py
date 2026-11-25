from datetime import date, timedelta

from app.models.appointment import Appointment
from app.models.online_queue import OnlineQueueEntry
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.visit import Visit

_PATH = "/api/v1/appointments/rescheduled-visits"


def test_move_without_time_appears_on_new_day_and_is_audited(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    today = date.today()
    moved_day = today + timedelta(days=3)
    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        status="confirmed",
        visit_date=today,
    )
    db_session.add(visit)
    db_session.commit()
    visit_id = visit.id
    response = client.post(
        f"/api/v1/visits/visits/{visit_id}/reschedule",
        params={"new_date": moved_day.isoformat()},
        headers=registrar_auth_headers,
    )
    assert response.status_code == 200
    db_session.refresh(visit)
    assert visit.visit_date == moved_day
    assert visit.visit_time is None
    assert visit.calendar_rescheduled is True

    old_day = client.get(_PATH, params={"day": today}, headers=registrar_auth_headers)
    new_day = client.get(
        _PATH, params={"day": moved_day}, headers=registrar_auth_headers
    )
    assert old_day.status_code == new_day.status_code == 200
    assert old_day.json() == []
    assert len(new_day.json()) == 1
    row = new_day.json()[0]
    assert row["visit_id"] == visit_id
    assert row["scheduled_time"] is None
    assert set(row) == {
        "visit_id",
        "patient_name",
        "doctor_name",
        "scheduled_time",
        "status",
    }
    assert db_session.query(Appointment).count() == 0
    audit = db_session.query(PatientAccessAuditLog).filter_by(
        subject_patient_id=test_patient.id,
        resource_type="visit",
        resource_id=str(visit_id),
    )
    assert audit.count() == 1


def test_legacy_move_is_visible_but_history_walkins_and_matched_rows_are_not_copied(
    client, db_session, auth_headers, test_patient, test_doctor, test_daily_queue
):
    day = date.today() + timedelta(days=3)

    def seed(**fields):
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=day,
            **fields,
        )
        db_session.add(visit)
        db_session.flush()
        return visit

    legacy = seed(status="open")
    seed(visit_time="09:30", status="closed", calendar_rescheduled=True)
    seed(visit_time="11:45", status="canceled", calendar_rescheduled=True)
    seed(visit_time="10:15", status="open")
    seed(visit_time="11:00", status="confirmed", calendar_rescheduled=True)
    db_session.add_all(
        [
            OnlineQueueEntry(
                visit_id=legacy.id,
                patient_id=test_patient.id,
                queue_id=test_daily_queue.id,
                number=98,
                status="rescheduled",
            ),
            Appointment(
                patient_id=test_patient.id,
                doctor_id=test_doctor.id,
                appointment_date=day,
                appointment_time="11:00:00",
                status="scheduled",
            ),
        ]
    )
    db_session.commit()
    response = client.get(_PATH, params={"day": day}, headers=auth_headers)
    assert response.status_code == 200
    assert [row["visit_id"] for row in response.json()] == [legacy.id]
    ordinary = client.get(
        "/api/v1/appointments/",
        params={"date_from": day, "date_to": day},
        headers=auth_headers,
    )
    assert ordinary.status_code == 200
    assert len(ordinary.json()) == 1


def test_calendar_requires_doctor_own_scope_and_auth(
    client, db_session, test_visit, test_doctor, cardio_auth_headers
):
    test_visit.calendar_rescheduled = True
    db_session.commit()
    day = test_visit.visit_date
    assert client.get(_PATH, params={"day": day}).status_code == 401
    assert (
        client.get(_PATH, params={"day": day}, headers=cardio_auth_headers).status_code
        == 403
    )
    assert (
        client.get(
            _PATH, params={"day": day, "doctor_id": 999999}, headers=cardio_auth_headers
        ).status_code
        == 403
    )
    allowed = client.get(
        _PATH,
        params={"day": day, "doctor_id": test_doctor.id},
        headers=cardio_auth_headers,
    )
    assert allowed.status_code == 200
    assert [row["visit_id"] for row in allowed.json()] == [test_visit.id]
