from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.models.lab import LabOrder, LabResult
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.lab_notification_service import LabNotificationService
from app.services.notifications import notification_sender_service


def _create_user(db_session, *, username: str, role: str, full_name: str) -> User:
    existing = db_session.query(User).filter(User.username == username).first()
    if existing:
        return existing

    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name=full_name,
        hashed_password="hashed-password",
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_send_lab_results_creates_canonical_delivery(
    db_session,
    admin_user,
):
    created = await notification_sender_service.send_lab_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="lab_results",
        metadata={
            "order_id": 101,
            "patient_id": 202,
        },
    )

    assert created is True
    delivery = (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "lab_results",
            NotificationDelivery.recipient_id == admin_user.id,
        )
        .one()
    )
    event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == delivery.event_id)
        .one()
    )

    assert event.source_module == "lab"
    assert event.severity == "info"
    assert event.priority == "high"
    assert event.entity_type == "lab_result"
    assert event.entity_id == "101"
    assert event.deep_link == "/lab/results"
    assert delivery.role == "admin"
    assert delivery.payload_snapshot["metadata"]["order_id"] == 101


@pytest.mark.asyncio
async def test_send_lab_critical_result_sets_critical_priority_and_actor(
    db_session,
    admin_user,
    registrar_user,
):
    created = await notification_sender_service.send_lab_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="lab_critical_result",
        metadata={
            "result_id": 501,
            "order_id": 301,
            "patient_id": 401,
        },
        actor_user=registrar_user,
    )

    assert created is True
    delivery = (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "lab_critical_result",
            NotificationDelivery.recipient_id == admin_user.id,
        )
        .one()
    )
    event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == delivery.event_id)
        .one()
    )

    assert event.severity == "critical"
    assert event.priority == "urgent"
    assert event.actor_id == registrar_user.id
    assert event.actor_role == registrar_user.role
    assert event.entity_type == "lab_result"
    assert event.entity_id == "501"
    assert delivery.payload_snapshot["metadata"]["result_id"] == 501


@pytest.mark.asyncio
async def test_send_lab_event_rejects_unsupported_type(
    db_session,
    admin_user,
):
    created = await notification_sender_service.send_lab_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="lab_result_ready_legacy",
        metadata={"order_id": 999},
    )

    assert created is False
    count = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.event_type == "lab_result_ready_legacy")
        .count()
    )
    assert count == 0


@pytest.mark.asyncio
async def test_check_and_notify_ready_results_emits_confirmation_event(
    db_session,
    test_patient,
    monkeypatch,
):
    patient_user = _create_user(
        db_session,
        username="patient_lab_ready",
        role="patient",
        full_name="Patient Lab Ready",
    )
    test_patient.user_id = patient_user.id
    db_session.commit()

    order = LabOrder(
        patient_id=test_patient.id,
        status="completed",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    send_mock = AsyncMock(side_effect=[True, True])
    monkeypatch.setattr(
        notification_sender_service,
        "send_lab_event_notification",
        send_mock,
    )

    service = LabNotificationService(db_session)
    result = await service.check_and_notify_ready_results()

    assert result["notifications_sent"] == 1
    assert send_mock.await_count == 2
    assert send_mock.await_args_list[0].kwargs["event_type"] == "lab_results"
    assert send_mock.await_args_list[1].kwargs["event_type"] == "lab_result_sent_confirmation"


@pytest.mark.asyncio
async def test_check_critical_values_emits_critical_finding_event(
    db_session,
    test_patient,
    test_visit,
    cardio_user,
    monkeypatch,
):
    order = LabOrder(
        patient_id=test_patient.id,
        visit_id=test_visit.id,
        status="completed",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    result = LabResult(
        order_id=order.id,
        test_name="Glucose",
        value="24.4",
        abnormal=True,
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)

    send_mock = AsyncMock(side_effect=[True, True])
    monkeypatch.setattr(
        notification_sender_service,
        "send_lab_event_notification",
        send_mock,
    )

    service = LabNotificationService(db_session)
    outcome = await service.check_critical_values()

    assert outcome["critical_found"] == 1
    assert send_mock.await_count == 2
    first_call = send_mock.await_args_list[0]
    second_call = send_mock.await_args_list[1]
    assert first_call.kwargs["event_type"] == "lab_critical_result"
    assert second_call.kwargs["event_type"] == "lab_critical_finding"
    assert first_call.kwargs["recipient"].id == cardio_user.id
    assert second_call.kwargs["recipient"].id == cardio_user.id
