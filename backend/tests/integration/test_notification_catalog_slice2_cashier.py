from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit, VisitService


def _create_patient_visit(db_session, *, suffix: str) -> tuple[Patient, Visit]:
    patient_user = User(
        username=f"cashier_actions_patient_{suffix}",
        email=f"cashier_actions_patient_{suffix}@test.local",
        full_name=f"Cashier Actions Patient {suffix}",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(patient_user)
    db_session.commit()
    db_session.refresh(patient_user)

    patient = Patient(
        first_name=f"Action{suffix}",
        last_name="Patient",
        phone=f"+99890120{suffix.zfill(4)[-4:]}",
        birth_date=date(1990, 1, 1),
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

    return patient, visit


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


def _add_visit_service(db_session, visit: Visit, *, price: str, service_id: int) -> VisitService:
    service = VisitService(
        visit_id=visit.id,
        service_id=service_id,
        code=f"CASH-{service_id}",
        name=f"Cashier Service {service_id}",
        qty=1,
        price=Decimal(price),
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


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

    # Add a billable service so remaining_debt > 0 — the cashier endpoint now
    # rejects payments when all services are already paid (no overpayment
    # without an explicit advance agreement).
    _add_visit_service(db_session, visit, price="50000", service_id=301)

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


def test_cashier_create_payment_rejects_mismatched_visit_and_appointment(
    client,
    db_session,
    auth_headers,
):
    patient, appointment_visit = _create_patient_visit(db_session, suffix="0102")
    other_patient, other_visit = _create_patient_visit(db_session, suffix="0103")
    appointment_visit.visit_date = date.today()
    other_visit.visit_date = date.today()
    db_session.add_all([appointment_visit, other_visit])
    db_session.commit()

    appointment = Appointment(
        patient_id=patient.id,
        appointment_date=appointment_visit.visit_date,
        appointment_time=None,
        doctor_id=None,
        status="scheduled",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    db_session.refresh(other_visit)
    original_status = other_visit.status

    response = client.post(
        "/api/v1/cashier/payments",
        json={
            "visit_id": other_visit.id,
            "appointment_id": appointment.id,
            "amount": 45000,
            "method": "cash",
            "note": "mixed-id cashier payment",
        },
        headers=auth_headers,
    )

    assert response.status_code == 409
    db_session.refresh(other_visit)
    assert other_visit.status == original_status
    assert (
        db_session.query(Payment)
        .filter(Payment.visit_id == other_visit.id)
        .count()
        == 0
    )
    assert _payment_event_deliveries(
        db_session,
        recipient_id=other_patient.user_id,
    ) == []


def test_cashier_create_payment_rejects_mismatched_patient_and_visit(
    client,
    db_session,
    auth_headers,
):
    patient, _own_visit = _create_patient_visit(db_session, suffix="0104")
    other_patient, other_visit = _create_patient_visit(db_session, suffix="0105")

    response = client.post(
        "/api/v1/cashier/payments",
        json={
            "patient_id": patient.id,
            "visit_id": other_visit.id,
            "amount": 45000,
            "method": "cash",
            "note": "mixed patient visit cashier payment",
        },
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Cashier payment patient_id does not match visit ownership"
    )
    assert (
        db_session.query(Payment)
        .filter(Payment.visit_id == other_visit.id)
        .count()
        == 0
    )
    assert _payment_event_deliveries(
        db_session,
        recipient_id=other_patient.user_id,
    ) == []


def test_cashier_grouped_payment_allocates_by_backend_remaining_debt(
    client,
    db_session,
    auth_headers,
):
    patient, first_visit = _create_patient_visit(db_session, suffix="0101")
    second_visit = Visit(
        patient_id=patient.id,
        status="waiting",
        discount_mode="none",
        approval_status="none",
        source="desk",
    )
    db_session.add(second_visit)
    db_session.commit()
    db_session.refresh(second_visit)

    _add_visit_service(db_session, first_visit, price="100000", service_id=101)
    _add_visit_service(db_session, second_visit, price="50000", service_id=102)
    existing_payment = Payment(
        visit_id=first_visit.id,
        amount=Decimal("40000"),
        method="cash",
        status="paid",
    )
    db_session.add(existing_payment)
    db_session.commit()

    response = client.post(
        "/api/v1/cashier/payments/grouped",
        json={
            "patient_id": patient.id,
            "visit_ids": [first_visit.id, second_visit.id],
            "amount": 80000,
            "method": "cash",
            "note": "backend grouped allocation",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["patient_id"] == patient.id
    assert payload["amount"] == "80000"
    assert [item["visit_id"] for item in payload["allocations"]] == [
        first_visit.id,
        second_visit.id,
    ]
    assert [item["amount"] for item in payload["allocations"]] == ["60000.00", "20000.00"]
    assert [item["remaining_after"] for item in payload["allocations"]] == ["0.00", "30000.00"]

    payments = (
        db_session.query(Payment)
        .filter(Payment.visit_id.in_([first_visit.id, second_visit.id]))
        .order_by(Payment.id.asc())
        .all()
    )
    assert [(payment.visit_id, payment.amount, payment.status) for payment in payments] == [
        (first_visit.id, Decimal("40000.00"), "paid"),
        (first_visit.id, Decimal("60000.00"), "paid"),
        (second_visit.id, Decimal("20000.00"), "paid"),
    ]


def test_cashier_grouped_payment_rejects_overpay_without_mutation(
    client,
    db_session,
    auth_headers,
):
    patient, first_visit = _create_patient_visit(db_session, suffix="0102")
    second_visit = Visit(
        patient_id=patient.id,
        status="waiting",
        discount_mode="none",
        approval_status="none",
        source="desk",
    )
    db_session.add(second_visit)
    db_session.commit()
    db_session.refresh(second_visit)

    _add_visit_service(db_session, first_visit, price="10000", service_id=201)
    _add_visit_service(db_session, second_visit, price="15000", service_id=202)

    response = client.post(
        "/api/v1/cashier/payments/grouped",
        json={
            "patient_id": patient.id,
            "visit_ids": [first_visit.id, second_visit.id],
            "amount": 30000,
            "method": "cash",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    assert "exceeds backend-calculated remaining debt" in response.json()["detail"]
    assert (
        db_session.query(Payment)
        .filter(Payment.visit_id.in_([first_visit.id, second_visit.id]))
        .count()
    ) == 0


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


def test_cashier_payment_history_exposes_backend_owned_actions(
    client,
    db_session,
    auth_headers,
):
    _, visit = _create_patient_visit(db_session, suffix="0001")
    pending_payment = Payment(
        visit_id=visit.id,
        amount=Decimal("30000"),
        method="cash",
        status="pending",
    )
    paid_payment = Payment(
        visit_id=visit.id,
        amount=Decimal("50000"),
        method="cash",
        status="paid",
    )
    refunded_payment = Payment(
        visit_id=visit.id,
        amount=Decimal("70000"),
        method="cash",
        status="refunded",
        refunded_amount=Decimal("70000"),
    )
    db_session.add_all([pending_payment, paid_payment, refunded_payment])
    db_session.commit()

    response = client.get("/api/v1/cashier/payments?size=10", headers=auth_headers)

    assert response.status_code == 200, response.text
    rows = {item["id"]: item for item in response.json()["items"]}

    pending_row = rows[pending_payment.id]
    assert pending_row["can_confirm"] is True
    assert pending_row["can_cancel"] is True
    assert pending_row["can_refund"] is False
    assert pending_row["can_print_receipt"] is True
    assert set(pending_row["available_actions"]) == {"confirm", "cancel", "print_receipt"}

    paid_row = rows[paid_payment.id]
    assert paid_row["can_confirm"] is False
    assert paid_row["can_cancel"] is True
    assert paid_row["can_refund"] is True
    assert paid_row["can_print_receipt"] is True
    assert set(paid_row["available_actions"]) == {"cancel", "refund", "print_receipt"}

    refunded_row = rows[refunded_payment.id]
    assert refunded_row["can_confirm"] is False
    assert refunded_row["can_cancel"] is False
    assert refunded_row["can_refund"] is False
    assert refunded_row["can_print_receipt"] is True
    assert refunded_row["available_actions"] == ["print_receipt"]


def test_cashier_confirm_refunded_payment_is_rejected_without_mutation(
    client,
    db_session,
    auth_headers,
):
    _, visit = _create_patient_visit(db_session, suffix="0002")
    payment = Payment(
        visit_id=visit.id,
        amount=Decimal("40000"),
        method="cash",
        status="refunded",
        refunded_amount=Decimal("40000"),
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    response = client.post(
        f"/api/v1/cashier/payments/{payment.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    db_session.refresh(payment)
    assert payment.status == "refunded"


def test_cashier_confirm_completed_payment_does_not_downgrade_status(
    client,
    db_session,
    auth_headers,
):
    _, visit = _create_patient_visit(db_session, suffix="0003")
    payment = Payment(
        visit_id=visit.id,
        amount=Decimal("45000"),
        method="cash",
        status="completed",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    response = client.post(
        f"/api/v1/cashier/payments/{payment.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    db_session.refresh(payment)
    assert payment.status == "completed"
