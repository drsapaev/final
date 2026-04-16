from __future__ import annotations

from datetime import date

from app.core.security import get_password_hash
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _event_deliveries(db_session, event_type: str):
    return (
        db_session.query(NotificationDelivery, NotificationEvent)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(NotificationEvent.event_type == event_type)
        .all()
    )


def test_registrar_cart_creates_all_free_request_notification(
    client,
    db_session,
    registrar_auth_headers,
    registrar_user,
    admin_user,
    test_patient,
    test_doctor,
    test_service,
):
    _ = registrar_user
    _ = admin_user

    payload = {
        "patient_id": test_patient.id,
        "discount_mode": "all_free",
        "all_free": True,
        "payment_method": "cash",
        "visits": [
            {
                "doctor_id": test_doctor.id,
                "visit_date": date.today().isoformat(),
                "visit_time": "10:30",
                "department": "cardiology",
                "services": [
                    {
                        "service_id": test_service.id,
                        "quantity": 1,
                    }
                ],
            }
        ],
    }

    response = client.post(
        "/api/v1/registrar/cart",
        json=payload,
        headers=registrar_auth_headers,
    )

    assert response.status_code == 200, response.text
    deliveries = _event_deliveries(db_session, "all_free_requested")
    assert len(deliveries) == 1

    delivery, event = deliveries[0]
    assert delivery.recipient_id == admin_user.id
    assert delivery.role == "admin"
    assert event.entity_type == "visit"
    assert event.payload_snapshot["metadata"]["approval_status"] == "pending"
    assert event.payload_snapshot["metadata"]["requested_by"] == registrar_user.id


def test_admin_all_free_approval_creates_registrar_and_patient_notifications(
    client,
    db_session,
    auth_headers,
    admin_user,
    registrar_user,
    test_doctor,
):
    patient_user = User(
        username="all_free_patient_user",
        email="all_free_patient@test.local",
        full_name="All Free Patient User",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(patient_user)
    db_session.commit()
    db_session.refresh(patient_user)

    patient = Patient(
        first_name="Петр",
        last_name="Пациентов",
        phone="+998901112233",
        birth_date=date(1991, 2, 2),
        user_id=patient_user.id,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="11:00",
        status="confirmed",
        discount_mode="all_free",
        approval_status="pending",
        department="cardiology",
        confirmed_by=f"registrar_{registrar_user.id}",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    response = client.post(
        "/api/v1/admin/all-free-approve",
        json={"visit_id": visit.id, "action": "approve"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    deliveries = _event_deliveries(db_session, "all_free_approved")
    recipient_ids = {delivery.recipient_id for delivery, _ in deliveries}

    assert recipient_ids == {registrar_user.id, patient_user.id}
    for _, event in deliveries:
        assert event.entity_type == "visit"
        assert event.actor_id == admin_user.id
        assert event.payload_snapshot["metadata"]["approval_status"] == "approved"
