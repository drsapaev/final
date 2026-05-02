from __future__ import annotations

from datetime import date
from types import SimpleNamespace

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


def _create_patient_visit_with_user(db_session, *, username: str):
    patient_user = User(
        username=username,
        email=f"{username}@test.local",
        full_name=f"{username} full name",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(patient_user)
    db_session.commit()
    db_session.refresh(patient_user)

    patient = Patient(
        first_name="Тест",
        last_name="Пациент",
        phone="+998901234500",
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

    return patient_user, patient, visit


def test_click_webhook_creates_payment_notification_and_hides_internal_fields(
    client,
    db_session,
    monkeypatch,
):
    patient_user, patient, visit = _create_patient_visit_with_user(
        db_session, username="slice2_webhook_patient"
    )

    payment = Payment(
        visit_id=visit.id,
        amount=120000,
        currency="UZS",
        method="online",
        status="pending",
        provider="click",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    def _fake_click_webhook(self, webhook_data):
        return {
            "click_trans_id": webhook_data.get("click_trans_id", 111),
            "merchant_trans_id": webhook_data.get("merchant_trans_id", "test-order"),
            "merchant_prepare_id": 123,
            "error": 0,
            "error_note": "",
            "payment_id": payment.id,
            "payment_status": "paid",
            "payment_provider": "click",
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_webhooks.ProviderWebhookService.process_click_webhook",
        _fake_click_webhook,
    )

    response = client.post(
        "/api/v1/payments/webhook/click",
        json={
            "click_trans_id": 777,
            "merchant_trans_id": "demo-merchant-777",
        },
    )

    assert response.status_code == 200, response.text
    response_data = response.json()
    assert "payment_id" not in response_data
    assert "payment_status" not in response_data
    assert "payment_provider" not in response_data

    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1

    _, event = deliveries[0]
    assert event.source_module == "payments_webhook"
    assert event.entity_type == "payment"
    assert event.payload_snapshot["metadata"]["payment_id"] == payment.id
    assert event.payload_snapshot["metadata"]["visit_id"] == visit.id
    assert event.payload_snapshot["metadata"]["patient_id"] == patient.id
    assert event.payload_snapshot["metadata"]["payment_status"] == "paid"
    assert event.payload_snapshot["metadata"]["change_type"] == "paid"
    assert event.payload_snapshot["metadata"]["provider"] == "click"
    assert event.payload_snapshot["metadata"]["webhook_kind"] == "click"


def test_payment_init_failed_creates_payment_notification(
    client,
    db_session,
    auth_headers,
    monkeypatch,
):
    patient_user, _, visit = _create_patient_visit_with_user(
        db_session, username="slice2_init_failure_patient"
    )

    class _FakePaymentManager:
        def get_providers_for_currency(self, currency):
            return ["click"]

        def create_payment(
            self,
            *,
            provider_name,
            amount,
            currency,
            order_id,
            description,
            return_url,
            cancel_url,
        ):
            return SimpleNamespace(
                success=False,
                payment_id=None,
                payment_url=None,
                status="failed",
                error_message="provider temporarily unavailable",
                provider_data={"debug": "forced-failure"},
            )

    monkeypatch.setattr(
        "app.api.v1.endpoints.payments.get_payment_manager",
        lambda: _FakePaymentManager(),
    )

    response = client.post(
        "/api/v1/payments/init",
        headers=auth_headers,
        json={
            "visit_id": visit.id,
            "provider": "click",
            "amount": 95000,
            "currency": "UZS",
            "description": "slice2 init fail",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False
    assert body["payment_id"] is not None

    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1

    _, event = deliveries[0]
    assert event.source_module == "payments"
    assert event.entity_type == "payment"
    assert event.payload_snapshot["metadata"]["visit_id"] == visit.id
    assert event.payload_snapshot["metadata"]["payment_status"] == "failed"
    assert event.payload_snapshot["metadata"]["change_type"] == "failed_init"
    assert event.payload_snapshot["metadata"]["provider"] == "click"
    assert event.payload_snapshot["metadata"]["reason"] == "provider temporarily unavailable"
