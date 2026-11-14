from __future__ import annotations

import logging
import ssl
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.v1.endpoints.notifications import (
    _assert_doctor_can_notify_patient_visit,
    send_appointment_reminder as send_appointment_reminder_route,
    send_notification,
    test_notifications as _test_notifications_route,
)
from app.models.lab import LabOrder, LabResult
from app.models.notification import (
    NotificationDelivery,
    NotificationEvent,
    NotificationHistory,
)
from app.models.user_profile import UserNotificationSettings, UserPreferences, UserProfile
from app.schemas.notification import SendNotificationRequest
from app.services.notification_platform_service import NotificationPlatformService
from app.services.notifications_pkg import NotificationSenderService


def _attach_notification_preferences(
    db_session,
    *,
    user_id: int,
    preferences_values: dict[str, object] | None = None,
    settings_values: dict[str, object] | None = None,
):
    profile = UserProfile(user_id=user_id)
    db_session.add(profile)
    db_session.flush()
    preferences = UserPreferences(user_id=user_id, profile_id=profile.id)
    settings = UserNotificationSettings(user_id=user_id, profile_id=profile.id)
    for field, value in (preferences_values or {}).items():
        setattr(preferences, field, value)
    for field, value in (settings_values or {}).items():
        setattr(settings, field, value)
    db_session.add_all([preferences, settings])
    db_session.flush()
    return preferences, settings


@pytest.mark.parametrize(
    "event_type",
    [
        "lab_results",
        "lab_new_study",
        "lab_result_sent_confirmation",
        "lab_critical_result",
    ],
)
def test_lab_and_other_system_push_events_honor_system_updates_opt_out(
    db_session, admin_user, event_type
):
    _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"push_notifications": True},
        settings_values={"push_system_updates": False},
    )
    db_session.commit()

    service = NotificationSenderService()
    assert service._channel_opted_in(
        db=db_session,
        user_id=admin_user.id,
        channel="push",
        event_type=event_type,
    ) is False


def test_unmapped_push_event_keeps_its_existing_default_behavior(
    db_session, admin_user
):
    _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"push_notifications": True},
        settings_values={"push_system_updates": False},
    )
    db_session.commit()

    service = NotificationSenderService()
    assert service._channel_opted_in(
        db=db_session,
        user_id=admin_user.id,
        channel="push",
        event_type="message_received",
    ) is True


def test_doctor_notification_scope_requires_the_assigned_visit(
    db_session, test_visit, test_patient, test_doctor, cardio_user, test_doctor_user
):
    _assert_doctor_can_notify_patient_visit(
        db=db_session,
        current_user=cardio_user,
        patient_id=test_patient.id,
        related_entity_type="visit",
        related_entity_id=test_visit.id,
    )

    with pytest.raises(HTTPException) as exc_info:
        _assert_doctor_can_notify_patient_visit(
            db=db_session,
            current_user=test_doctor_user,
            patient_id=test_patient.id,
            related_entity_type="visit",
            related_entity_id=test_visit.id,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_doctor_reminder_hides_patient_existence_without_assigned_visit(
    db_session, test_patient, monkeypatch
):
    import app.api.v1.endpoints.notifications as notifications_endpoint

    doctor_user = SimpleNamespace(
        role="Doctor",
        is_superuser=False,
        full_name="Synthetic Doctor",
        username="synthetic-doctor",
    )
    doctor = SimpleNamespace(id=2_000_000_000, specialty="cardiology")
    monkeypatch.setattr(
        notifications_endpoint,
        "_active_doctor_for_user",
        lambda _db, _user: doctor,
    )
    lookups = []

    def patient_lookup(_db, *, id):
        lookups.append(id)
        return None

    monkeypatch.setattr(notifications_endpoint.patient_crud, "get", patient_lookup)

    responses = []
    for patient_id in (test_patient.id, test_patient.id + 100_000_000):
        with pytest.raises(HTTPException) as exc_info:
            await send_appointment_reminder_route(
                BackgroundTasks(),
                patient_id=patient_id,
                appointment_date=datetime(2026, 11, 14, 10, 0),
                doctor_name="ignored",
                department="ignored",
                current_user=doctor_user,
                db=db_session,
            )
        assert exc_info.value.status_code == 404
        responses.append(exc_info.value.detail)

    assert responses[0] == responses[1]
    assert lookups == []


@pytest.mark.asyncio
async def test_lab_result_delivery_uses_inbox_and_honors_sms_opt_out(
    db_session, admin_user, test_patient, monkeypatch
):
    import app.services.lab_notification_service as lab_notification_module
    from app.services.lab_notification_service import LabNotificationService

    test_patient.user_id = admin_user.id
    _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"sms_notifications": False},
    )
    db_session.flush()

    lab_inbox = AsyncMock(return_value=True)
    telegram_event = AsyncMock(return_value=False)
    legacy_telegram = AsyncMock()
    sms = AsyncMock(return_value=True)
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_lab_event_notification",
        lab_inbox,
    )
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_patient_telegram_event_notification",
        telegram_event,
    )
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_telegram_message",
        legacy_telegram,
    )
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_sms",
        sms,
    )

    await LabNotificationService(db_session)._notify_patient_results_ready(
        SimpleNamespace(id=77, patient_id=test_patient.id)
    )

    assert [call.kwargs["event_type"] for call in lab_inbox.await_args_list] == [
        "lab_results",
        "lab_result_sent_confirmation",
    ]
    assert all(
        call.kwargs["recipient"] is admin_user for call in lab_inbox.await_args_list
    )
    telegram_event.assert_not_awaited()
    legacy_telegram.assert_not_awaited()
    sms.assert_not_awaited()


@pytest.mark.asyncio
async def test_lab_result_sms_success_is_recorded_and_not_repeated(
    db_session, test_patient, monkeypatch
):
    import app.services.lab_notification_service as lab_notification_module
    from app.services.lab_notification_service import LabNotificationService

    sms = AsyncMock(return_value=True)
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_sms",
        sms,
    )
    service = LabNotificationService(db_session)
    order = SimpleNamespace(id=82, patient_id=test_patient.id)

    assert await service._notify_patient_results_ready(order) is True
    assert await service._notify_patient_results_ready(order) is False

    sms.assert_awaited_once()
    history = (
        db_session.query(NotificationHistory)
        .filter(
            NotificationHistory.recipient_id == test_patient.id,
            NotificationHistory.related_entity_type == "lab_order",
            NotificationHistory.related_entity_id == order.id,
            NotificationHistory.notification_type == "lab_results",
            NotificationHistory.channel == "sms",
            NotificationHistory.status == "sent",
        )
        .all()
    )
    assert len(history) == 1


@pytest.mark.asyncio
async def test_lab_ready_inbox_and_sms_deliveries_are_not_repeated(
    db_session, admin_user, test_patient, monkeypatch
):
    import app.services.lab_notification_service as lab_notification_module
    from app.services.lab_notification_service import LabNotificationService

    test_patient.user_id = admin_user.id
    db_session.flush()
    order = SimpleNamespace(id=83, patient_id=test_patient.id)
    created_event_types = []

    async def create_lab_delivery(**kwargs):
        event_type = kwargs["event_type"]
        created_event_types.append(event_type)
        event = NotificationEvent(
            event_type=event_type,
            dedup_key=f"test:{event_type}:{order.id}",
            source_module="lab",
            entity_type="lab_result",
            entity_id=str(order.id),
            severity="info",
            priority="high",
            title=kwargs["title"],
            message=kwargs["message"],
            payload_snapshot={"metadata": kwargs["metadata"]},
        )
        db_session.add(
            NotificationDelivery(
                event=event,
                recipient_type="user",
                recipient_id=kwargs["recipient"].id,
                role=kwargs["recipient"].role,
                channel="in_app_inbox",
                dedup_key=f"test-delivery:{event_type}:{order.id}",
                sequence_id=len(created_event_types),
                delivery_status="delivered",
            )
        )
        db_session.flush()
        return True

    inbox = AsyncMock(side_effect=create_lab_delivery)
    sms = AsyncMock(return_value=True)
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_lab_event_notification",
        inbox,
    )
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_sms",
        sms,
    )
    service = LabNotificationService(db_session)

    assert await service._notify_patient_results_ready(order) is True
    assert await service._notify_patient_results_ready(order) is False

    assert created_event_types == ["lab_results", "lab_result_sent_confirmation"]
    sms.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_lab_ready_delivery_is_not_counted_or_logged_as_success(
    db_session, admin_user, test_patient, monkeypatch, caplog
):
    import app.services.lab_notification_service as lab_notification_module
    from app.services.lab_notification_service import LabNotificationService

    test_patient.user_id = admin_user.id
    _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"sms_notifications": False},
    )
    order = LabOrder(
        patient_id=test_patient.id,
        status="completed",
    )
    db_session.add(order)
    db_session.flush()

    inbox_delivery = AsyncMock(return_value=False)
    sms = AsyncMock(return_value=True)
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_lab_event_notification",
        inbox_delivery,
    )
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_sms",
        sms,
    )

    with caplog.at_level(logging.INFO):
        result = await LabNotificationService(db_session).check_and_notify_ready_results()

    assert result == {"total_checked": 1, "notifications_sent": 0, "errors": []}
    inbox_delivery.assert_awaited_once()
    sms.assert_not_awaited()
    assert any(
        "lab_results canonical delivery failed" in record.message
        for record in caplog.records
    )
    assert not any(
        "Lab result notification delivered" in record.message
        or "Notification sent for order" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_critical_lab_alert_does_not_log_success_when_inbox_creation_fails(
    db_session, test_visit, test_patient, monkeypatch, caplog
):
    import app.services.lab_notification_service as lab_notification_module
    from app.services.lab_notification_service import LabNotificationService

    order = LabOrder(
        patient_id=test_patient.id,
        visit_id=test_visit.id,
        status="completed",
    )
    db_session.add(order)
    db_session.flush()
    result = LabResult(
        order_id=order.id,
        test_name="glucose",
        value="25",
    )
    db_session.add(result)
    db_session.flush()

    inbox_delivery = AsyncMock(return_value=False)
    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_lab_event_notification",
        inbox_delivery,
    )

    with caplog.at_level(logging.INFO):
        await LabNotificationService(db_session)._notify_doctor_critical_value(
            result,
            value=25,
            thresholds={"low": 3, "high": 20, "unit": "mmol/L"},
        )

    inbox_delivery.assert_awaited_once()
    assert any(
        "lab_critical_result canonical delivery failed" in record.message
        for record in caplog.records
    )
    assert not any(
        phrase in record.message
        for record in caplog.records
        for phrase in (
            "Critical value alert recorded in doctor inbox",
            "Critical value alert sent",
        )
    )


@pytest.mark.asyncio
async def test_critical_lab_alert_reuses_existing_inbox_deliveries(
    db_session, test_visit, test_patient, cardio_user, monkeypatch
):
    import app.services.lab_notification_service as lab_notification_module
    from app.services.lab_notification_service import LabNotificationService

    order = LabOrder(
        patient_id=test_patient.id,
        visit_id=test_visit.id,
        status="completed",
    )
    db_session.add(order)
    db_session.flush()
    result = LabResult(
        order_id=order.id,
        test_name="glucose",
        value="25",
    )
    db_session.add(result)
    db_session.flush()

    created_event_types = []

    async def create_lab_delivery(**kwargs):
        event_type = kwargs["event_type"]
        created_event_types.append(event_type)
        event = NotificationEvent(
            event_type=event_type,
            dedup_key=f"test:{event_type}:{result.id}",
            source_module="lab",
            entity_type="lab_result",
            entity_id=str(result.id),
            severity="critical" if event_type == "lab_critical_result" else "info",
            priority="urgent" if event_type == "lab_critical_result" else "normal",
            title=kwargs["title"],
            message=kwargs["message"],
            payload_snapshot={"metadata": kwargs["metadata"]},
        )
        db_session.add(
            NotificationDelivery(
                event=event,
                recipient_type="user",
                recipient_id=kwargs["recipient"].id,
                role="Doctor",
                channel="in_app_inbox",
                dedup_key=f"test-delivery:{event_type}:{result.id}",
                sequence_id=len(created_event_types),
                delivery_status="delivered",
            )
        )
        db_session.flush()
        return True

    monkeypatch.setattr(
        lab_notification_module.notification_sender_service,
        "send_lab_event_notification",
        AsyncMock(side_effect=create_lab_delivery),
    )
    service = LabNotificationService(db_session)
    thresholds = {"low": 3, "high": 20, "unit": "mmol/L"}

    await service._notify_doctor_critical_value(result, 25, thresholds)
    await service._notify_doctor_critical_value(result, 25, thresholds)

    assert created_event_types == ["lab_critical_result", "lab_critical_finding"]


@pytest.mark.asyncio
async def test_notification_endpoint_rejects_unsupported_and_scheduled_requests(
    db_session, admin_user
):
    base = dict(
        recipient_id=1,
        notification_type="payment_notification",
        channels=["email"],
    )

    with pytest.raises(HTTPException) as scheduled:
        await send_notification(
            BackgroundTasks(),
            SendNotificationRequest(
                recipient_type="patient",
                scheduled_at=datetime.now(UTC) + timedelta(hours=1),
                **base,
            ),
            current_user=admin_user,
            db=db_session,
        )
    assert scheduled.value.status_code == 422

    with pytest.raises(HTTPException) as unsupported:
        await send_notification(
            BackgroundTasks(),
            SendNotificationRequest(recipient_type="doctor", **base),
            current_user=admin_user,
            db=db_session,
        )
    assert unsupported.value.status_code == 422


@pytest.mark.asyncio
async def test_direct_visit_confirmation_honors_global_and_event_opt_outs(
    db_session, admin_user, test_patient
):
    test_patient.user_id = admin_user.id
    preferences, settings = _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"sms_notifications": True},
        settings_values={"sms_appointment_confirmation": False},
    )
    db_session.commit()

    service = NotificationSenderService()
    service.send_email = AsyncMock(return_value=True)
    service.send_sms = AsyncMock(return_value=True)
    service.send_push = AsyncMock(return_value=True)
    service.send_patient_telegram_event_notification = AsyncMock(return_value=False)

    await service.send_visit_confirmation(
        patient_email="patient@example.test",
        patient_phone="+998901234567",
        visit_date=datetime(2026, 11, 13, 9, 30),
        doctor_name="Doctor",
        department="Cardiology",
        db=db_session,
        patient_id=test_patient.id,
    )

    service.send_email.assert_awaited_once()
    service.send_sms.assert_not_awaited()

    settings.sms_appointment_confirmation = True
    preferences.sms_notifications = False
    db_session.flush()
    await service.send_visit_confirmation(
        patient_email="patient@example.test",
        patient_phone="+998901234567",
        visit_date=datetime(2026, 11, 13, 9, 30),
        doctor_name="Doctor",
        department="Cardiology",
        db=db_session,
        patient_id=test_patient.id,
    )
    service.send_sms.assert_not_awaited()


@pytest.mark.asyncio
async def test_templated_sender_skips_opted_out_channel_before_creating_history(
    db_session, admin_user, test_patient
):
    test_patient.user_id = admin_user.id
    _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"sms_notifications": False},
    )
    db_session.commit()

    service = NotificationSenderService()
    service.send_sms = AsyncMock(return_value=True)
    result = await service.send_templated_notification(
        db=db_session,
        notification_type="payment_notification",
        channel="sms",
        recipient_contact="+998901234567",
        template_data={"message": "Payment received"},
        recipient_type="patient",
        recipient_id=test_patient.id,
    )

    assert result is None
    service.send_sms.assert_not_awaited()
    assert db_session.query(NotificationDelivery).count() == 0


@pytest.mark.asyncio
async def test_templated_sender_honors_matching_event_preference_field(
    db_session, admin_user, test_patient
):
    test_patient.user_id = admin_user.id
    _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"email_notifications": True},
        settings_values={"email_payment_reminder": False},
    )
    db_session.commit()

    service = NotificationSenderService()
    service.send_email = AsyncMock(return_value=True)
    result = await service.send_templated_notification(
        db=db_session,
        notification_type="payment_reminder",
        channel="email",
        recipient_contact="patient@example.test",
        template_data={"message": "Payment reminder"},
        recipient_type="patient",
        recipient_id=test_patient.id,
    )

    assert result is None
    service.send_email.assert_not_awaited()
    assert db_session.query(NotificationDelivery).count() == 0


@pytest.mark.asyncio
async def test_pwa_invitation_does_not_send_sms_after_global_opt_out(
    db_session, admin_user, test_patient
):
    test_patient.user_id = admin_user.id
    _attach_notification_preferences(
        db_session,
        user_id=admin_user.id,
        preferences_values={"sms_notifications": False},
    )
    db_session.commit()

    service = NotificationSenderService()
    service.send_sms = AsyncMock(return_value=True)
    result = await service._send_pwa_invitation(
        test_patient,
        {"confirmation_token": "synthetic-token", "visit_date": "13.11.2026"},
        db=db_session,
    )

    assert result["success"] is False
    service.send_sms.assert_not_awaited()


@pytest.mark.asyncio
async def test_templated_inbox_state_is_separate_from_external_provider_status(
    db_session, admin_user, test_patient
):
    test_patient.user_id = admin_user.id
    db_session.commit()

    platform = NotificationPlatformService(db_session)
    platform.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    service = NotificationSenderService()
    service._platform_service = lambda _db: platform
    service.send_email = AsyncMock(return_value=False)

    history = await service.send_templated_notification(
        db=db_session,
        notification_type="payment_notification",
        channel="email",
        recipient_contact="patient@example.test",
        template_data={"message": "Payment received"},
        recipient_type="patient",
        recipient_id=test_patient.id,
        priority="urgent",
    )

    delivery = db_session.query(NotificationDelivery).one()
    event = db_session.query(NotificationEvent).one()
    assert history.status == "failed"
    assert delivery.channel == "in_app_inbox"
    assert delivery.delivery_status == "delivered"
    assert event.priority == "urgent"
    assert event.severity == "critical"


@pytest.mark.asyncio
async def test_inbox_cursor_uses_an_extra_row_to_report_more_items(
    db_session, admin_user
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    for index in range(2):
        await service.record_delivery_for_user(
            user=admin_user,
            event_type="lab_results",
            title=f"Result {index}",
            message=f"Result message {index}",
            source_module="lab",
        )

    first_page = service.get_inbox(current_user=admin_user, limit=1)
    assert first_page["total"] == 2
    assert first_page["has_more"] is True
    assert first_page["next_cursor"] == str(first_page["items"][0]["sequence_id"])

    second_page = service.get_inbox(
        current_user=admin_user,
        limit=1,
        cursor=int(first_page["next_cursor"]),
    )
    assert len(second_page["items"]) == 1
    assert second_page["has_more"] is False
    assert second_page["next_cursor"] is None


@pytest.mark.asyncio
async def test_expired_notification_is_absent_from_inbox_counts_and_realtime(
    db_session, admin_user
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    await service.record_delivery_for_user(
        user=admin_user,
        event_type="lab_results",
        title="Expired result",
        message="This notification has expired",
        source_module="lab",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    inbox = service.get_inbox(current_user=admin_user)
    counts = service.get_unread_counts(current_user=admin_user)
    assert inbox["total"] == 0
    assert inbox["unread_count"] == 0
    assert counts["total"] == 0
    assert counts["by_severity"] == {}
    assert service.repository.list_recent_deliveries(limit=10) == []
    service.ws_manager.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_state_mutation_broadcast_uses_update_transport_without_new_event(
    db_session, admin_user
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    delivery = await service.record_delivery_for_user(
        user=admin_user,
        event_type="lab_results",
        title="Result",
        message="New result",
        source_module="lab",
    )
    service.ws_manager.send_json.reset_mock()

    await service.mark_read(current_user=admin_user, delivery_id=delivery.delivery_id)

    payload = service.ws_manager.send_json.await_args.args[0]
    assert payload["type"] == "notification_update"
    assert payload["delivery_id"] == delivery.delivery_id
    assert payload["is_read"] is True


@pytest.mark.asyncio
async def test_queue_burst_guard_keeps_a_different_event_type_for_same_visit(
    db_session, admin_user, monkeypatch
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_is_within_quiet_hours", lambda **_: False)

    first = await service.record_delivery_for_user(
        user=admin_user,
        event_type="queue_update",
        title="Queue update",
        message="Wait time changed",
        source_module="queue",
        entity_type="visit",
        entity_id="visit-42",
    )
    second = await service.record_delivery_for_user(
        user=admin_user,
        event_type="queue_position",
        title="Queue position",
        message="Your position is now 2",
        source_module="queue",
        entity_type="visit",
        entity_id="visit-42",
    )

    assert first.delivery_id != second.delivery_id
    assert service.ws_manager.send_json.await_count == 2


@pytest.mark.asyncio
async def test_bulk_sender_deduplicates_recipient_and_channels_and_keeps_priority(
    db_session,
):
    service = NotificationSenderService()
    service.send_templated_notification = AsyncMock(return_value=None)
    recipient = {
        "id": 41,
        "type": "patient",
        "email": "patient@example.test",
        "phone": "+998901234567",
        "telegram": "987654321",
    }

    await service.send_bulk_notification(
        db=db_session,
        notification_type="payment_notification",
        channels=["email", "email"],
        recipients=[recipient, recipient.copy()],
        template_data={"message": "Payment received"},
        priority="urgent",
    )

    service.send_templated_notification.assert_awaited_once()
    assert service.send_templated_notification.await_args.kwargs["priority"] == "urgent"


@pytest.mark.asyncio
async def test_telegram_sender_never_falls_back_to_global_chat(monkeypatch, caplog):
    service = NotificationSenderService()
    service.telegram_bot_token = "test-secret-token"
    post_calls = []

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, **kwargs):
            post_calls.append((url, kwargs))
            request = httpx.Request("POST", url)
            response = httpx.Response(403, request=request)
            raise httpx.HTTPStatusError(
                "forbidden", request=request, response=response
            )

    monkeypatch.setattr(
        "app.services.notifications_pkg._channels.httpx.AsyncClient",
        FakeAsyncClient,
    )

    with caplog.at_level(logging.WARNING):
        assert await service.send_telegram("safe message") is False
        assert post_calls == []
        assert await service.send_telegram("safe message", chat_id="linked-chat") is False
        legacy = await service.send_telegram_message("987654321", "safe message")

    assert len(post_calls) == 1
    assert legacy["success"] is False
    assert "test-secret-token" not in caplog.text
    assert "api.telegram.org/bot" not in caplog.text


def test_smtp_starttls_uses_a_verifying_default_context(monkeypatch):
    import app.services.notifications_pkg._channels as channels_module

    captured = {}

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def starttls(self, *, context):
            captured["context"] = context

        def login(self, *_args):
            pass

        def send_message(self, _message):
            pass

        def quit(self):
            pass

    monkeypatch.setattr(channels_module.smtplib, "SMTP", FakeSMTP)
    service = NotificationSenderService()
    service.smtp_username = "synthetic-user"
    service.smtp_password = "synthetic-password"
    service.smtp_from = "clinic@example.test"

    assert service._send_email_sync(
        "patient@example.test", "Synthetic subject", "Synthetic body"
    ) is True
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert captured["context"].check_hostname is True


@pytest.mark.asyncio
async def test_admin_notification_diagnostic_endpoint_schedules_no_sends(admin_user):
    response = await _test_notifications_route(current_user=admin_user)

    assert response["queued"] == 0
    assert response["external_delivery"] is False


def test_notification_template_rendering_uses_sandboxed_jinja():
    service = NotificationSenderService()
    output = service.render_template("{{ ''.__class__.__mro__ }}", {})

    assert "object" not in output
    assert "tuple" not in output
