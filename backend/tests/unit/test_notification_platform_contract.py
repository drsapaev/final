from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
import pytest

from app.api.v1.endpoints.notifications import _validate_recipient_scope
from app.models.notification import NotificationDelivery, NotificationEvent
from app.services.notification_platform_service import NotificationPlatformService


@pytest.mark.asyncio
async def test_notification_platform_service_creates_persistent_delivery_and_deduplicates(
    db_session,
    admin_user,
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))

    payload = {
        "title": "Очередь обновлена",
        "message": "Пациент вызван к врачу",
        "metadata": {"source": "queue"},
    }

    delivery = await service.record_delivery_for_user(
        user=admin_user,
        event_type="queue_update",
        title=payload["title"],
        message=payload["message"],
        source_module="queue",
        actor_id=admin_user.id,
        actor_role=admin_user.role,
        entity_type="visit",
        entity_id="visit-123",
        payload_snapshot=payload,
        deep_link="/queue",
    )

    persisted_delivery = (
        db_session.query(NotificationDelivery)
        .filter(NotificationDelivery.delivery_id == delivery.delivery_id)
        .one()
    )
    persisted_event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == persisted_delivery.event_id)
        .one()
    )

    assert persisted_event.event_type == "queue_update"
    assert persisted_delivery.delivery_status == "delivered"
    assert persisted_delivery.role == "admin"
    assert persisted_delivery.sequence_id == 1
    assert persisted_delivery.payload_snapshot["metadata"]["source"] == "queue"
    assert service.ws_manager.send_json.await_count == 1

    duplicate_delivery = await service.record_delivery_for_user(
        user=admin_user,
        event_type="queue_update",
        title=payload["title"],
        message=payload["message"],
        source_module="queue",
        actor_id=admin_user.id,
        actor_role=admin_user.role,
        entity_type="visit",
        entity_id="visit-123",
        payload_snapshot=payload,
        deep_link="/queue",
    )

    assert duplicate_delivery.delivery_id == delivery.delivery_id
    assert db_session.query(NotificationDelivery).count() == 1
    assert db_session.query(NotificationEvent).count() == 1
    assert service.ws_manager.send_json.await_count == 2

    inbox = service.get_inbox(current_user=admin_user, status="all", limit=10)
    assert inbox["total"] == 1
    assert inbox["unread_count"] == 1
    assert inbox["items"][0]["id"] == delivery.delivery_id
    assert inbox["items"][0]["event_type"] == "queue_update"

    seen_delivery = await service.mark_seen(current_user=admin_user, delivery_id=delivery.delivery_id)
    assert seen_delivery.seen_at is not None
    assert seen_delivery.delivery_status == "seen"

    read_delivery = await service.mark_read(current_user=admin_user, delivery_id=delivery.delivery_id)
    assert read_delivery.read_at is not None
    assert read_delivery.delivery_status == "read"

    archived_delivery = await service.archive(
        current_user=admin_user,
        delivery_id=delivery.delivery_id,
    )
    assert archived_delivery.archived_at is not None
    assert archived_delivery.delivery_status == "archived"

    unread_counts = service.get_unread_counts(current_user=admin_user)
    assert unread_counts["total"] == 0

    archived_inbox = service.get_inbox(
        current_user=admin_user,
        status="archived",
        limit=10,
    )
    assert archived_inbox["total"] == 1
    assert archived_inbox["items"][0]["delivery_status"] == "archived"


def test_notification_history_scope_rejects_cross_recipient_requests(
    db_session,
    admin_user,
):
    service = NotificationPlatformService(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _validate_recipient_scope(
            platform_service=service,
            current_user=admin_user,
            recipient_id=admin_user.id + 1,
            recipient_type='admin',
        )

    assert exc_info.value.status_code == 403


def test_notification_history_scope_allows_same_recipient_even_if_type_differs(
    db_session,
    admin_user,
):
    service = NotificationPlatformService(db_session)

    _validate_recipient_scope(
        platform_service=service,
        current_user=admin_user,
        recipient_id=admin_user.id,
        recipient_type='doctor',
    )


def test_realtime_policy_suppresses_when_desktop_notifications_disabled(db_session):
    service = NotificationPlatformService(db_session)
    user = SimpleNamespace(
        preferences=SimpleNamespace(desktop_notifications=False, timezone="Asia/Tashkent"),
        profile=SimpleNamespace(timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )

    allowed, reason = service._should_broadcast_realtime(
        user=user,
        event_type="queue_update",
        severity="info",
        priority="normal",
    )

    assert allowed is False
    assert reason == "desktop_notifications_disabled"


def test_realtime_policy_allows_critical_breakthrough_even_when_desktop_disabled(db_session):
    service = NotificationPlatformService(db_session)
    user = SimpleNamespace(
        preferences=SimpleNamespace(desktop_notifications=False, timezone="Asia/Tashkent"),
        profile=SimpleNamespace(timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=False,
        ),
    )

    allowed, reason = service._should_broadcast_realtime(
        user=user,
        event_type="security_alert",
        severity="warning",
        priority="normal",
    )

    assert allowed is True
    assert reason == "critical_breakthrough"


def test_realtime_policy_suppresses_queue_events_during_quiet_hours(monkeypatch, db_session):
    service = NotificationPlatformService(db_session)
    user = SimpleNamespace(
        preferences=SimpleNamespace(desktop_notifications=True, timezone="Asia/Tashkent"),
        profile=SimpleNamespace(timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )
    monkeypatch.setattr(service, "_is_within_quiet_hours", lambda **_: True)

    allowed, reason = service._should_broadcast_realtime(
        user=user,
        event_type="queue_position",
        severity="info",
        priority="normal",
    )

    assert allowed is False
    assert reason == "quiet_hours_queue_suppression"


def test_realtime_policy_respects_event_push_setting_mapping(db_session):
    service = NotificationPlatformService(db_session)
    user = SimpleNamespace(
        preferences=SimpleNamespace(desktop_notifications=True, timezone="Asia/Tashkent"),
        profile=SimpleNamespace(timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            push_system_updates=False,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )

    allowed, reason = service._should_broadcast_realtime(
        user=user,
        event_type="queue_update",
        severity="info",
        priority="normal",
    )

    assert allowed is False
    assert reason == "setting_disabled:push_system_updates"


@pytest.mark.asyncio
async def test_queue_burst_realtime_is_suppressed_but_inbox_persistence_remains(
    db_session,
    monkeypatch,
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_is_within_quiet_hours", lambda **_: False)

    user = SimpleNamespace(
        id=93001,
        role="patient",
        is_superuser=False,
        profile=SimpleNamespace(department=None, timezone="Asia/Tashkent"),
        preferences=SimpleNamespace(desktop_notifications=True, timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            push_system_updates=True,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )

    first_delivery = await service.record_delivery_for_user(
        user=user,
        event_type="queue_update",
        title="Обновление очереди",
        message="Пациент вызван к врачу",
        source_module="queue",
        severity="info",
        priority="normal",
        entity_type="visit",
        entity_id="visit-100",
        payload_snapshot={
            "title": "Обновление очереди",
            "message": "Пациент вызван к врачу",
            "metadata": {"source": "queue", "attempt": 1},
        },
        deep_link="/queue",
    )
    second_delivery = await service.record_delivery_for_user(
        user=user,
        event_type="queue_update",
        title="Обновление очереди",
        message="Пациент вызван к врачу",
        source_module="queue",
        severity="info",
        priority="normal",
        entity_type="visit",
        entity_id="visit-100",
        payload_snapshot={
            "title": "Обновление очереди",
            "message": "Пациент вызван к врачу",
            "metadata": {"source": "queue", "attempt": 2},
        },
        deep_link="/queue",
    )

    assert first_delivery.delivery_id != second_delivery.delivery_id
    assert db_session.query(NotificationDelivery).count() == 2
    assert db_session.query(NotificationEvent).count() == 2
    assert service.ws_manager.send_json.await_count == 1


@pytest.mark.asyncio
async def test_queue_call_is_not_suppressed_by_burst_guard(
    db_session,
    monkeypatch,
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_is_within_quiet_hours", lambda **_: False)

    user = SimpleNamespace(
        id=93002,
        role="patient",
        is_superuser=False,
        profile=SimpleNamespace(department=None, timezone="Asia/Tashkent"),
        preferences=SimpleNamespace(desktop_notifications=True, timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            push_system_updates=True,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )

    first_delivery = await service.record_delivery_for_user(
        user=user,
        event_type="queue_call",
        title="Пациент вызван",
        message="Подойдите к кабинету",
        source_module="queue",
        severity="info",
        priority="normal",
        entity_type="visit",
        entity_id="visit-200",
        payload_snapshot={
            "title": "Пациент вызван",
            "message": "Подойдите к кабинету",
            "metadata": {"source": "queue", "attempt": 1},
        },
        deep_link="/queue",
    )
    second_delivery = await service.record_delivery_for_user(
        user=user,
        event_type="queue_call",
        title="Пациент вызван",
        message="Подойдите к кабинету",
        source_module="queue",
        severity="info",
        priority="normal",
        entity_type="visit",
        entity_id="visit-200",
        payload_snapshot={
            "title": "Пациент вызван",
            "message": "Подойдите к кабинету",
            "metadata": {"source": "queue", "attempt": 2},
        },
        deep_link="/queue",
    )

    assert first_delivery.delivery_id != second_delivery.delivery_id
    assert db_session.query(NotificationDelivery).count() == 2
    assert db_session.query(NotificationEvent).count() == 2
    assert service.ws_manager.send_json.await_count == 2


@pytest.mark.asyncio
async def test_record_delivery_for_users_keeps_inbox_but_filters_realtime_by_settings(
    db_session,
    monkeypatch,
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_is_within_quiet_hours", lambda **_: False)

    user_realtime_off = SimpleNamespace(
        id=91001,
        role="patient",
        is_superuser=False,
        profile=SimpleNamespace(department=None, timezone="Asia/Tashkent"),
        preferences=SimpleNamespace(desktop_notifications=True, timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            push_system_updates=False,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )
    user_realtime_on = SimpleNamespace(
        id=91002,
        role="patient",
        is_superuser=False,
        profile=SimpleNamespace(department=None, timezone="Asia/Tashkent"),
        preferences=SimpleNamespace(desktop_notifications=True, timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            push_system_updates=True,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )

    deliveries = await service.record_delivery_for_users(
        users=[user_realtime_off, user_realtime_on],
        event_type="queue_update",
        title="Обновление очереди",
        message="Очередь изменилась",
        source_module="queue",
        severity="info",
        priority="normal",
    )

    assert len(deliveries) == 2
    assert db_session.query(NotificationDelivery).count() == 2
    assert db_session.query(NotificationEvent).count() == 1
    assert service.ws_manager.send_json.await_count == 1


@pytest.mark.asyncio
async def test_record_delivery_for_user_persists_inbox_when_realtime_suppressed_by_event_setting(
    db_session,
    monkeypatch,
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_is_within_quiet_hours", lambda **_: False)

    user = SimpleNamespace(
        id=92001,
        role="patient",
        is_superuser=False,
        profile=SimpleNamespace(department=None, timezone="Asia/Tashkent"),
        preferences=SimpleNamespace(desktop_notifications=True, timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            push_system_updates=False,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=True,
        ),
    )

    delivery = await service.record_delivery_for_user(
        user=user,
        event_type="queue_update",
        title="Обновление очереди",
        message="Очередь изменилась",
        source_module="queue",
        severity="info",
        priority="normal",
    )

    assert delivery is not None
    assert db_session.query(NotificationDelivery).count() == 1
    assert db_session.query(NotificationEvent).count() == 1
    assert service.ws_manager.send_json.await_count == 0


@pytest.mark.asyncio
async def test_record_delivery_for_user_allows_critical_breakthrough_even_if_settings_disabled(
    db_session,
    monkeypatch,
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_is_within_quiet_hours", lambda **_: True)

    user = SimpleNamespace(
        id=92002,
        role="patient",
        is_superuser=False,
        profile=SimpleNamespace(department=None, timezone="Asia/Tashkent"),
        preferences=SimpleNamespace(desktop_notifications=False, timezone="Asia/Tashkent"),
        notification_settings=SimpleNamespace(
            push_security_alerts=False,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
            weekend_notifications=False,
        ),
    )

    delivery = await service.record_delivery_for_user(
        user=user,
        event_type="security_alert",
        title="Security alert",
        message="Suspicious activity detected",
        source_module="security",
        severity="warning",
        priority="normal",
    )

    assert delivery is not None
    assert db_session.query(NotificationDelivery).count() == 1
    assert db_session.query(NotificationEvent).count() == 1
    assert service.ws_manager.send_json.await_count == 1
