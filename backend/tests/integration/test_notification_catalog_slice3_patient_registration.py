from __future__ import annotations

from datetime import date

from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient


def _patient_registered_deliveries(db_session):
    return (
        db_session.query(NotificationDelivery, NotificationEvent)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(NotificationEvent.event_type == "patient_registered")
        .order_by(NotificationDelivery.id.asc())
        .all()
    )


def test_create_patient_emits_patient_registered_to_admin_and_registrar(
    client,
    db_session,
    auth_headers,
    admin_user,
    registrar_user,
):
    _ = admin_user
    _ = registrar_user

    response = client.post(
        "/api/v1/patients/",
        headers=auth_headers,
        json={
            "last_name": "Нотиф",
            "first_name": "Пациент",
            "birth_date": "1993-05-11",
            "phone": "+998901345678",
            "address": "Tashkent",
        },
    )

    assert response.status_code == 200, response.text
    patient_id = response.json()["id"]

    deliveries = _patient_registered_deliveries(db_session)
    recipient_ids = {delivery.recipient_id for delivery, _ in deliveries}
    assert recipient_ids == {admin_user.id, registrar_user.id}

    for _, event in deliveries:
        assert event.source_module == "patients"
        assert event.entity_type == "patient"
        assert int(event.entity_id) == patient_id
        assert event.payload_snapshot["metadata"]["patient_id"] == patient_id
        assert (
            event.payload_snapshot["metadata"]["registration_source"]
            == "registrar_panel"
        )


def test_update_patient_does_not_emit_patient_registered_event(
    client,
    db_session,
    auth_headers,
):
    patient = Patient(
        first_name="Старый",
        last_name="Пациент",
        phone="+998907777700",
        birth_date=date(1990, 2, 2),
        address="Old address",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    response = client.put(
        f"/api/v1/patients/{patient.id}",
        headers=auth_headers,
        json={
            "first_name": "Обновленный",
            "last_name": patient.last_name,
            "phone": "+998907777701",
            "address": "New address",
        },
    )

    assert response.status_code == 200, response.text
    deliveries = _patient_registered_deliveries(db_session)
    assert len(deliveries) == 0
