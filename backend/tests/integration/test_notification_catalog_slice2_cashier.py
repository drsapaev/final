from __future__ import annotations

from datetime import date

from app.core.security import get_password_hash
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit


def _payment_event_deliveries(db_session, *, recipient_id: int):
    return (
        db_session.query(NotificationDelivery, NotificationEvent)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "payment_notification",
            NotificationDelivery.recipient_id == recipient_id,
        )
        .order_by(NotificationDelivery.id.asc())
        .all()
    )


def test_cashier_create_payment_creates_canonical_payment_notification(
    client,
    db_session,
    auth_headers,
):
    patient_user = User(
        username="cashier_payment_patient",
        email="cashier_payment_patient@test.local",
        full_name="Cashier Payment Patient",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(patient_user)
    db_session.commit()
    db_session.refresh(patient_user)

    patient = Patient(
        first_name="Игорь",
        last_name="Платежный",
        phone="+998901000100",
        birth_date=date(1992, 3, 3),
        user_id=patient_user.id,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        status="waiting",
        discount_mode="none",
        approval_status="none",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    response = client.post(
        "/api/v1/cashier/payments",
        json={
            "visit_id": visit.id,
            "amount": 45000,
            "method": "cash",
            "note": "slice2 payment",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1

    delivery, event = deliveries[0]
    assert delivery.role == "patient"
    assert event.entity_type == "payment"
    assert event.source_module == "cashier"
    assert event.deep_link == "/patient"
    assert event.payload_snapshot["metadata"]["change_type"] == "paid"
    assert event.payload_snapshot["metadata"]["payment_status"] == "paid"
    assert event.payload_snapshot["metadata"]["visit_id"] == visit.id


def test_cashier_cancel_payment_creates_cancelled_payment_notification(
    client,
    db_session,
    auth_headers,
):
    patient_user = User(
        username="cashier_cancel_patient",
        email="cashier_cancel_patient@test.local",
        full_name="Cashier Cancel Patient",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(patient_user)
    db_session.commit()
    db_session.refresh(patient_user)

    patient = Patient(
        first_name="Анвар",
        last_name="Возвратов",
        phone="+998901000200",
        birth_date=date(1991, 6, 6),
        user_id=patient_user.id,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        status="waiting",
        discount_mode="none",
        approval_status="none",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    payment = Payment(
        visit_id=visit.id,
        amount=70000,
        method="cash",
        status="paid",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    response = client.post(
        f"/api/v1/cashier/payments/{payment.id}/cancel",
        json={"reason": "patient requested cancel"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1

    _, event = deliveries[0]
    assert event.payload_snapshot["metadata"]["change_type"] == "cancelled"
    assert event.payload_snapshot["metadata"]["payment_status"] == "cancelled"
    assert event.payload_snapshot["metadata"]["reason"] == "patient requested cancel"
