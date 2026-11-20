"""Legacy cashier snapshots cannot disclose stale patient ownership."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.notification import NotificationDelivery, NotificationEvent
from app.services.notification_platform_service import NotificationPlatformService

SECRET = "SYNTHETIC_PRIVATE_942311"


@pytest.fixture
def legacy_deliveries(db_session, admin_user, test_patient):
    test_patient.user_id = admin_user.id
    events = []
    for sequence, (source, event_type, title, message) in enumerate((
        ("cashier", "payment_notification", SECRET, f"{SECRET} 942311 UZS"),
        ("system", "queue_update", "SYNTHETIC_PUBLIC", "Visible queue update"),
        ("manual", "payment_notification", "SYNTHETIC_MANUAL", "Visible staff message"),
    ), start=1):
        event = NotificationEvent(source_module=source, event_type=event_type, title=title, message=message,
                                  severity="warning", priority="high", dedup_key=f"event-{uuid4()}",
                                  correlation_id=str(uuid4()), entity_type="payment", entity_id=SECRET,
                                  deep_link=f"/patient?ref={SECRET}",
                                  payload_snapshot={"metadata": {"amount": SECRET, "reason": SECRET}})
        db_session.add(event)
        db_session.flush()
        delivery = NotificationDelivery(event_id=event.id, recipient_type="user", recipient_id=admin_user.id,
            role="admin", department_key=SECRET if source == "cashier" else None,
            channel="in_app_inbox", dedup_key=f"{SECRET}-{uuid4()}", sequence_id=sequence,
            delivery_status="delivered", payload_snapshot={"metadata": {"amount": SECRET, "reason": SECRET}})
        if source != "cashier":
            event.deep_link = "/queue"
            event.payload_snapshot = {"metadata": {"ok": True}}
            delivery.dedup_key = f"visible-{uuid4()}"
            delivery.payload_snapshot = {"metadata": {"ok": True}}
        db_session.add(delivery)
        events.append((event, delivery))
    db_session.commit()
    # Represent a later transfer away from this recipient; the old event stays.
    test_patient.user_id = None
    db_session.commit()
    return events


def _assert_neutral(item):
    assert item["event_type"] == "notification"
    assert item["title"] == "Новое уведомление"
    assert item["message"] == "Откройте личный кабинет для просмотра."
    assert item["deep_link"] == "/patient"
    assert item["department_key"] is None
    assert item["severity"] == "info" and item["priority"] == "normal"
    assert SECRET not in json.dumps(item, ensure_ascii=False, default=str)


def test_inbox_sync_mobile_and_search_do_not_reveal_legacy_snapshot(
    client, db_session, admin_user, admin_auth_headers, legacy_deliveries
):
    service = NotificationPlatformService(db_session)
    inbox = service.get_inbox(current_user=admin_user, limit=50)
    legacy_id = legacy_deliveries[0][1].delivery_id
    neutral = next(item for item in inbox["items"] if item["delivery_id"] == legacy_id)
    _assert_neutral(neutral)
    assert service.get_inbox(current_user=admin_user, search=SECRET, limit=50)["total"] == 0
    assert service.get_inbox(current_user=admin_user, search="942311", limit=50)["total"] == 0
    assert service.get_inbox(current_user=admin_user, department_key=SECRET, limit=50)["total"] == 0
    assert service.get_unread_counts(current_user=admin_user, department_key=SECRET)["total"] == 0
    assert service.get_inbox(current_user=admin_user, search="SYNTHETIC_PUBLIC", limit=50)["total"] == 1
    filtered = service.get_inbox(current_user=admin_user, event_type="payment_notification", limit=50)
    assert [item["title"] for item in filtered["items"]] == ["SYNTHETIC_MANUAL"]
    assert service.get_inbox(current_user=admin_user, event_type="notification", limit=50)["total"] == 1
    assert service.get_unread_counts(current_user=admin_user)["by_severity"]["info"] == 1
    assert service.get_inbox(current_user=admin_user, severity="info", limit=50)["total"] == 1

    for url in ("/api/v1/notifications/inbox", "/api/v1/notifications/sync"):
        response = client.get(url, headers=admin_auth_headers)
        assert response.status_code == 200, response.text
        _assert_neutral(next(item for item in response.json()["items"] if item["delivery_id"] == legacy_id))
        search = client.get(url, headers=admin_auth_headers, params={"search": SECRET})
        assert search.status_code == 200 and search.json()["total"] == 0
    mobile = client.get("/api/v1/mobile/notifications", headers=admin_auth_headers)
    assert mobile.status_code == 200, mobile.text
    mobile_item = next(item for item in mobile.json() if item["id"] == legacy_id)
    assert mobile_item["title"] == "Новое уведомление" and SECRET not in json.dumps(mobile_item)
    # Redaction affects projection only; the original evidence is retained.
    assert db_session.get(NotificationEvent, legacy_deliveries[0][0].id).message.endswith("942311 UZS")


def test_classifier_and_search_match_for_legacy_casing(db_session, admin_user, legacy_deliveries):
    event = legacy_deliveries[0][0]
    event.source_module, event.event_type = " CASHIER ", " PAYMENT_NOTIFICATION "
    db_session.commit()
    service = NotificationPlatformService(db_session)
    inbox = service.get_inbox(current_user=admin_user, event_type="notification")
    assert inbox["total"] == 1
    _assert_neutral(inbox["items"][0])
    assert service.get_inbox(current_user=admin_user, search=SECRET)["total"] == 0


@pytest.mark.asyncio
async def test_broadcast_state_changes_and_stats_use_neutral_projection(db_session, admin_user, legacy_deliveries):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock())
    event, delivery = legacy_deliveries[0]
    assert await service.mark_all_read(current_user=admin_user, department_key=SECRET) == 0
    assert delivery.read_at is None
    await service._broadcast_delivery(admin_user.id, delivery)
    await service.mark_seen(current_user=admin_user, delivery_id=delivery.delivery_id)
    for call in service.ws_manager.send_json.await_args_list:
        payload = call.args[0]
        assert payload["title"] == "Новое уведомление" and payload["event_type"] == "notification"
        _assert_neutral(payload["notification"])
        assert SECRET not in json.dumps(payload, ensure_ascii=False, default=str)
    stats = service.get_stats(days=7)
    recent = next(item for item in stats["recent_activity"] if item["id"] == delivery.delivery_id)
    assert recent["notification_type"] == "notification" and SECRET not in json.dumps(recent, default=str)
    assert event.message.endswith("942311 UZS")


@pytest.mark.asyncio
async def test_websocket_sync_uses_same_neutral_projection(db_session, admin_user, legacy_deliveries, monkeypatch):
    from app.api.v1.endpoints import notification_websocket as endpoint
    from tests.unit.test_notification_websocket_sync_limit import (
        FakeManager,
        FakeSocket,
    )

    service = NotificationPlatformService(db_session)
    manager = FakeManager()

    async def authenticate(_token, _db):
        return admin_user

    monkeypatch.setattr(endpoint, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(endpoint, "get_notification_ws_manager", lambda: manager)
    monkeypatch.setattr(endpoint, "extract_ws_token", lambda _socket: "synthetic-token")
    monkeypatch.setattr(endpoint, "authenticate_websocket_token", authenticate)
    monkeypatch.setattr(endpoint, "get_notification_platform_service", lambda _db: service)
    socket = FakeSocket([{"type": "notification_sync"}])
    await endpoint.websocket_notifications(socket)
    response = next(item for item in socket.sent if item["type"] == "notification_sync_response")
    assert SECRET not in json.dumps(response, ensure_ascii=False, default=str)
    assert "Новое уведомление" in json.dumps(response, ensure_ascii=False)


def test_postgres_search_counts_and_stats_use_visible_values():
    import os

    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from sqlalchemy.schema import CreateSchema, DropSchema

    raw = os.environ.get("DATABASE_URL", "sqlite://")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    schema = "cashier_notify_" + uuid4().hex
    admin = sa.create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
    try:
        with engine.begin() as conn:
            conn.execute(sa.schema.CreateTable(NotificationEvent.__table__))
            conn.execute(sa.schema.CreateTable(NotificationDelivery.__table__))
        with Session(engine) as db:
            event = NotificationEvent(source_module="cashier", event_type="payment_notification",
                                      title=SECRET, message=f"{SECRET} 942311 UZS", severity="warning",
                                      dedup_key="synthetic-event-" + uuid4().hex)
            db.add(event)
            db.flush()
            db.add(NotificationDelivery(event_id=event.id, recipient_type="user", recipient_id=1,
                role="patient", channel="in_app_inbox", dedup_key="synthetic-delivery-" + uuid4().hex,
                sequence_id=1, delivery_status="delivered"))
            db.commit()
            actor = SimpleNamespace(id=1, role="Patient", is_superuser=False, profile=None)
            service = NotificationPlatformService(db)
            assert service.get_inbox(current_user=actor, search=SECRET)["total"] == 0
            assert service.get_inbox(current_user=actor, event_type="payment_notification")["total"] == 0
            assert service.get_inbox(current_user=actor, event_type="notification")["total"] == 1
            assert service.get_unread_counts(current_user=actor)["by_severity"] == {"info": 1}
            stats = service.get_stats(days=7)
            assert stats["by_type"].get("notification") == 1
            assert SECRET not in json.dumps(stats, default=str)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()
