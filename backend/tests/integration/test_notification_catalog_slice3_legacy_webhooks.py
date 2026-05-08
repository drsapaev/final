from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.core.security import get_password_hash
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.user import User


from tests.auth_test_credentials import (
    PATIENT_PASSWORD,
)

def _payment_event_deliveries(db_session, *, recipient_id: int):
    return (
        db_session.query(NotificationDelivery, NotificationEvent)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "payment_notification",
            NotificationDelivery.recipient_id == recipient_id,
            NotificationEvent.source_module == "payments_webhook_legacy",
        )
        .order_by(NotificationDelivery.id.asc())
        .all()
    )


def _create_patient_user(db_session, *, username: str):
    user = User(
        username=username,
        email=f"{username}@test.local",
        full_name=f"{username} full name",
        hashed_password=get_password_hash(PATIENT_PASSWORD),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        first_name="Легаси",
        last_name="Пациент",
        phone="+998901556677",
        birth_date=date(1992, 8, 8),
        user_id=user.id,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def test_legacy_click_webhook_emits_canonical_payment_notification(
    client,
    db_session,
    monkeypatch,
):
    patient_user, patient = _create_patient_user(
        db_session, username="legacy_webhook_click_patient"
    )

    fake_webhook = SimpleNamespace(
        id=501,
        provider="click",
        status="processed",
        transaction_id="legacy-click-501",
        patient_id=patient.id,
        visit_id=None,
        raw_data={"patient_id": patient.id},
    )

    def _fake_process_click_webhook(self, data):
        return True, "Webhook processed successfully", fake_webhook

    monkeypatch.setattr(
        "app.services.payment_webhook_endpoint_service.PaymentWebhookApiRepository.process_click_webhook",
        _fake_process_click_webhook,
    )

    response = client.post(
        "/api/v1/webhooks/payment/click",
        data={"merchant_trans_id": "legacy-click-order"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "ok": True,
        "message": "Webhook processed successfully",
        "webhook_id": 501,
    }

    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1
    _, event = deliveries[0]
    assert event.payload_snapshot["metadata"]["provider"] == "click"
    assert event.payload_snapshot["metadata"]["payment_status"] == "paid"
    assert event.payload_snapshot["metadata"]["change_type"] == "paid"
    assert event.payload_snapshot["metadata"]["legacy_webhook_path"] is True


def test_legacy_payme_webhook_emits_failed_payment_notification(
    client,
    db_session,
    monkeypatch,
):
    patient_user, patient = _create_patient_user(
        db_session, username="legacy_webhook_payme_patient"
    )

    fake_webhook = SimpleNamespace(
        id=701,
        provider="payme",
        status="failed",
        transaction_id="legacy-payme-701",
        patient_id=patient.id,
        visit_id=None,
        raw_data={"params": {"account": {"patient_id": patient.id}}},
    )

    def _fake_process_payme_webhook(self, data, signature):
        return False, "provider failure", fake_webhook

    monkeypatch.setattr(
        "app.services.payment_webhook_endpoint_service.PaymentWebhookApiRepository.process_payme_webhook",
        _fake_process_payme_webhook,
    )

    response = client.post(
        "/api/v1/webhooks/payment/payme",
        json={"id": "legacy-payme-rpc-id"},
        headers={"X-Payme-Signature": "test-signature"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "ok": False,
        "message": "provider failure",
        "webhook_id": 701,
    }

    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1
    _, event = deliveries[0]
    assert event.payload_snapshot["metadata"]["provider"] == "payme"
    assert event.payload_snapshot["metadata"]["payment_status"] == "failed"
    assert event.payload_snapshot["metadata"]["change_type"] == "failed"
    assert event.payload_snapshot["metadata"]["legacy_webhook_path"] is True


def test_legacy_click_webhook_duplicate_callback_does_not_create_duplicate_delivery(
    client,
    db_session,
    monkeypatch,
):
    patient_user, patient = _create_patient_user(
        db_session, username="legacy_webhook_click_duplicate_patient"
    )

    fake_webhook = SimpleNamespace(
        id=901,
        provider="click",
        status="processed",
        transaction_id="legacy-click-901",
        patient_id=patient.id,
        visit_id=None,
        raw_data={"patient_id": patient.id},
    )

    call_counter = {"value": 0}

    def _fake_process_click_webhook(self, data):
        call_counter["value"] += 1
        if call_counter["value"] == 1:
            return True, "Webhook processed successfully", fake_webhook
        return False, "Webhook already processed", fake_webhook

    monkeypatch.setattr(
        "app.services.payment_webhook_endpoint_service.PaymentWebhookApiRepository.process_click_webhook",
        _fake_process_click_webhook,
    )

    first_response = client.post(
        "/api/v1/webhooks/payment/click",
        data={"merchant_trans_id": "legacy-click-duplicate"},
    )
    second_response = client.post(
        "/api/v1/webhooks/payment/click",
        data={"merchant_trans_id": "legacy-click-duplicate"},
    )

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert first_response.json()["webhook_id"] == 901
    assert second_response.json()["webhook_id"] == 901

    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1


def test_legacy_payme_webhook_duplicate_callback_does_not_create_duplicate_delivery(
    client,
    db_session,
    monkeypatch,
):
    patient_user, patient = _create_patient_user(
        db_session, username="legacy_webhook_payme_duplicate_patient"
    )

    fake_webhook = SimpleNamespace(
        id=902,
        provider="payme",
        status="failed",
        transaction_id="legacy-payme-902",
        patient_id=patient.id,
        visit_id=None,
        raw_data={"params": {"account": {"patient_id": patient.id}}},
    )

    call_counter = {"value": 0}

    def _fake_process_payme_webhook(self, data, signature):
        call_counter["value"] += 1
        if call_counter["value"] == 1:
            return False, "provider failure", fake_webhook
        return False, "Webhook already processed", fake_webhook

    monkeypatch.setattr(
        "app.services.payment_webhook_endpoint_service.PaymentWebhookApiRepository.process_payme_webhook",
        _fake_process_payme_webhook,
    )

    first_response = client.post(
        "/api/v1/webhooks/payment/payme",
        json={"id": "legacy-payme-duplicate"},
        headers={"X-Payme-Signature": "test-signature"},
    )
    second_response = client.post(
        "/api/v1/webhooks/payment/payme",
        json={"id": "legacy-payme-duplicate"},
        headers={"X-Payme-Signature": "test-signature"},
    )

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert first_response.json()["webhook_id"] == 902
    assert second_response.json()["webhook_id"] == 902

    deliveries = _payment_event_deliveries(db_session, recipient_id=patient_user.id)
    assert len(deliveries) == 1
