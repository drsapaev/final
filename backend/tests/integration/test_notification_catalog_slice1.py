from __future__ import annotations

from datetime import date

import pytest

from app.core.security import get_password_hash
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import (
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
)
from app.models.visit import Visit
from app.services.notification_platform_service import NotificationPlatformService


def _event_deliveries(db_session, event_type: str):
    return (
        db_session.query(NotificationDelivery, NotificationEvent)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(NotificationEvent.event_type == event_type)
        .all()
    )


def _ensure_notification_policy_settings(
    db_session,
    *,
    user: User,
    desktop_notifications: bool,
    push_system_updates: bool,
) -> None:
    profile = (
        db_session.query(UserProfile)
        .filter(UserProfile.user_id == user.id)
        .first()
    )
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

    preferences = (
        db_session.query(UserPreferences)
        .filter(UserPreferences.user_id == user.id)
        .first()
    )
    if preferences is None:
        preferences = UserPreferences(
            user_id=user.id,
            profile_id=profile.id,
        )
        db_session.add(preferences)
    preferences.desktop_notifications = desktop_notifications

    settings = (
        db_session.query(UserNotificationSettings)
        .filter(UserNotificationSettings.user_id == user.id)
        .first()
    )
    if settings is None:
        settings = UserNotificationSettings(
            user_id=user.id,
            profile_id=profile.id,
        )
        db_session.add(settings)
    settings.push_system_updates = push_system_updates
    settings.weekend_notifications = True
    settings.quiet_hours_start = "00:00"
    settings.quiet_hours_end = "00:00"

    db_session.commit()


class _FakeNotificationWsManager:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload, user_id):  # type: ignore[no-untyped-def]
        self.sent.append({"user_id": user_id, "payload": payload})


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


def test_admin_all_free_reject_creates_rejected_notifications_with_reason(
    client,
    db_session,
    auth_headers,
    admin_user,
    registrar_user,
    test_doctor,
):
    patient_user = User(
        username="all_free_patient_reject_user",
        email="all_free_patient_reject@test.local",
        full_name="All Free Patient Reject User",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(patient_user)
    db_session.commit()
    db_session.refresh(patient_user)

    patient = Patient(
        first_name="Елена",
        last_name="Отклонова",
        phone="+998901112244",
        birth_date=date(1991, 4, 4),
        user_id=patient_user.id,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="11:30",
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
        json={
            "visit_id": visit.id,
            "action": "reject",
            "rejection_reason": "missing eligibility documents",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    deliveries = _event_deliveries(db_session, "all_free_rejected")
    recipient_ids = {delivery.recipient_id for delivery, _ in deliveries}

    assert recipient_ids == {registrar_user.id, patient_user.id}
    for _, event in deliveries:
        assert event.entity_type == "visit"
        assert event.actor_id == admin_user.id
        assert event.payload_snapshot["metadata"]["approval_status"] == "rejected"
        assert (
            event.payload_snapshot["metadata"]["rejection_reason"]
            == "missing eligibility documents"
        )


def test_all_free_requested_updates_inbox_and_unread_when_realtime_suppressed(
    client,
    db_session,
    monkeypatch,
    registrar_auth_headers,
    auth_headers,
    registrar_user,
    admin_user,
    test_patient,
    test_doctor,
    test_service,
):
    _ = registrar_user
    _ensure_notification_policy_settings(
        db_session,
        user=admin_user,
        desktop_notifications=True,
        push_system_updates=False,
    )

    fake_ws_manager = _FakeNotificationWsManager()
    monkeypatch.setattr(
        "app.services.notification_platform_service.get_notification_ws_manager",
        lambda: fake_ws_manager,
    )

    payload = {
        "patient_id": test_patient.id,
        "discount_mode": "all_free",
        "all_free": True,
        "payment_method": "cash",
        "visits": [
            {
                "doctor_id": test_doctor.id,
                "visit_date": date.today().isoformat(),
                "visit_time": "12:15",
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
    delivery, _event = deliveries[0]
    assert delivery.recipient_id == admin_user.id
    assert fake_ws_manager.sent == []

    inbox_response = client.get(
        "/api/v1/notifications/inbox",
        params={
            "event_type": "all_free_requested",
            "recipient_id": admin_user.id,
            "limit": 20,
        },
        headers=auth_headers,
    )
    assert inbox_response.status_code == 200, inbox_response.text
    inbox_payload = inbox_response.json()
    assert inbox_payload["total"] >= 1
    assert inbox_payload["unread_count"] >= 1
    assert any(
        item["event_type"] == "all_free_requested"
        and item["recipient_id"] == admin_user.id
        for item in inbox_payload["items"]
    )

    unread_response = client.get(
        "/api/v1/notifications/unread-count",
        params={"recipient_id": admin_user.id},
        headers=auth_headers,
    )
    assert unread_response.status_code == 200, unread_response.text
    unread_payload = unread_response.json()
    assert unread_payload["total"] >= 1

    sync_response = client.get(
        "/api/v1/notifications/sync",
        params={
            "event_type": "all_free_requested",
            "recipient_id": admin_user.id,
            "limit": 20,
        },
        headers=auth_headers,
    )
    assert sync_response.status_code == 200, sync_response.text
    sync_payload = sync_response.json()
    assert sync_payload["total"] >= 1
    assert any(
        item["event_type"] == "all_free_requested"
        and item["recipient_id"] == admin_user.id
        for item in sync_payload["items"]
    )


@pytest.mark.asyncio
async def test_security_alert_breaks_through_realtime_even_when_policy_disabled(
    client,
    db_session,
    monkeypatch,
    auth_headers,
    admin_user,
):
    _ensure_notification_policy_settings(
        db_session,
        user=admin_user,
        desktop_notifications=False,
        push_system_updates=False,
    )
    settings = (
        db_session.query(UserNotificationSettings)
        .filter(UserNotificationSettings.user_id == admin_user.id)
        .first()
    )
    assert settings is not None
    settings.push_security_alerts = False
    db_session.commit()

    fake_ws_manager = _FakeNotificationWsManager()
    monkeypatch.setattr(
        "app.services.notification_platform_service.get_notification_ws_manager",
        lambda: fake_ws_manager,
    )
    platform_service = NotificationPlatformService(db_session)

    delivery = await platform_service.record_delivery_for_user(
        user=admin_user,
        event_type="security_alert",
        title="Security alert",
        message="Suspicious activity detected",
        source_module="security",
        severity="warning",
        priority="normal",
    )
    assert delivery.recipient_id == admin_user.id
    assert len(fake_ws_manager.sent) == 1
    assert fake_ws_manager.sent[0]["user_id"] == admin_user.id
    assert (
        fake_ws_manager.sent[0]["payload"]["event_type"]
        == "security_alert"
    )

    inbox_response = client.get(
        "/api/v1/notifications/inbox",
        params={
            "event_type": "security_alert",
            "recipient_id": admin_user.id,
            "limit": 20,
        },
        headers=auth_headers,
    )
    assert inbox_response.status_code == 200, inbox_response.text
    inbox_payload = inbox_response.json()
    assert inbox_payload["total"] >= 1
    assert inbox_payload["unread_count"] >= 1
    assert any(
        item["event_type"] == "security_alert"
        and item["recipient_id"] == admin_user.id
        for item in inbox_payload["items"]
    )
