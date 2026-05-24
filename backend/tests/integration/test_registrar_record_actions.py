from __future__ import annotations

from datetime import date

import pytest

from app.models.appointment import Appointment


@pytest.mark.integration
def test_registrar_record_action_can_cancel_online_queue_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_queue_entry,
):
    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=registrar_auth_headers,
        json={
            "action": "cancel",
            "records": [
                {
                    "record_kind": "online_queue",
                    "record_id": test_queue_entry.id,
                }
            ],
            "reason": "contract test",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["action"] == "cancel"
    assert payload["success"] is True
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["results"][0]["record_kind"] == "online_queue"
    assert payload["results"][0]["record_id"] == test_queue_entry.id

    db_session.refresh(test_queue_entry)
    assert test_queue_entry.status == "canceled"


@pytest.mark.integration
def test_registrar_record_action_rejects_doctor_mark_paid(
    client,
    cardio_auth_headers,
    test_visit,
):
    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=cardio_auth_headers,
        json={
            "action": "mark_paid",
            "record_kind": "visit",
            "record_id": test_visit.id,
        },
    )

    assert response.status_code == 403


@pytest.mark.integration
def test_registrar_record_action_starts_appointment_when_ids_collide_with_queue_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_queue_entry,
    test_patient,
    test_doctor,
):
    appointment = Appointment(
        id=test_queue_entry.id,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        appointment_date=date.today(),
        appointment_time="11:00",
        status="paid",
        visit_type="paid",
        payment_type="cash",
        services=["consultation"],
    )
    db_session.add(appointment)
    db_session.commit()

    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=registrar_auth_headers,
        json={
            "action": "start_visit",
            "record_kind": "appointment",
            "record_id": appointment.id,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["results"][0]["record_kind"] == "appointment"
    assert payload["results"][0]["record_id"] == appointment.id

    db_session.refresh(appointment)
    db_session.refresh(test_queue_entry)
    assert appointment.status == "in_visit"
    assert test_queue_entry.status == "waiting"


@pytest.mark.integration
def test_legacy_queue_start_endpoint_does_not_fallback_to_appointment_id(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    appointment = Appointment(
        id=987654,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        appointment_date=date.today(),
        appointment_time="11:30",
        status="paid",
        visit_type="paid",
        payment_type="cash",
        services=["consultation"],
    )
    db_session.add(appointment)
    db_session.commit()

    response = client.post(
        f"/api/v1/registrar/queue/{appointment.id}/start-visit",
        headers=registrar_auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Queue entry not found"

    db_session.refresh(appointment)
    assert appointment.status == "paid"

