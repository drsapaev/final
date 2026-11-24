"""Synthetic patient links and provider mocks; no Telegram requests are made."""

import secrets
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.online_queue import QueueToken
from app.services.notifications import NotificationSenderService
from tests.integration.test_telegram_delivery_authorization import telegram_case  # noqa: F401


@pytest.mark.parametrize("chat_id,allowed", [(-1009876543210, False), (-42, False), (0, False), (86753099, True)])
def test_patient_delivery_rejects_nonprivate_links_over_http(
    client, db_session, admin_auth_headers, telegram_case, chat_id, allowed
):
    case = telegram_case
    case.link.chat_id = chat_id
    token = secrets.token_urlsafe(24)
    db_session.add(QueueToken(token=token, day=date(2030, 1, 2), active=True,
                              expires_at=datetime.now(UTC) + timedelta(hours=1)))
    db_session.commit()
    requests = [
        ("/api/v1/telegram/bot/send-appointment-reminder", {"user_id": chat_id, "appointment": {"id": case.appointment.id}}),
        ("/api/v1/telegram/bot/send-lab-notification", {"user_id": chat_id, "results": {"id": case.result.id}}),
        ("/api/v1/telegram/bot/send-notification", {"user_id": chat_id, "message": "SYNTHETIC"}),
        ("/api/v1/telegram/send-notification", {"chat_id": chat_id, "template_key": "appointment_reminder", "data": {"id": case.appointment.id}}),
        ("/api/v1/telegram/appointment-reminder", {"patient_phone": case.patient.phone, "appointment_data": {"id": case.appointment.id}}),
        ("/api/v1/telegram/lab-results-notification", {"patient_phone": case.patient.phone, "lab_data": {"id": case.result.id}}),
        ("/api/v1/telegram/send-qr-code", {"patient_phone": case.patient.phone, "qr_data": {"token": token}}),
    ]
    for path, body in requests:
        response = client.post(path, headers=admin_auth_headers, json=body)
        assert response.status_code == 200 if allowed else response.status_code in {404, 422}, (path, response.text)
    if allowed:
        case.direct_appointment.assert_awaited_once()
        case.direct_lab.assert_awaited_once()
        case.direct_generic.assert_awaited_once()
        assert case.service.send_plain_message.await_count == 4
    else:
        case.direct_appointment.assert_not_awaited()
        case.direct_lab.assert_not_awaited()
        case.direct_generic.assert_not_awaited()
        case.service.send_plain_message.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_id,allowed", [(-1009876543210, False), (-42, False), (0, False), (86753099, True)])
async def test_canonical_patient_senders_require_private_link(db_session, telegram_case, chat_id, allowed):
    case = telegram_case
    case.patient.user_id = case.user.id
    case.link.chat_id = chat_id
    db_session.commit()
    service = NotificationSenderService()
    service.send_telegram = AsyncMock(return_value=True)
    event = await service.send_patient_telegram_event_notification(
        db=db_session, patient_id=case.patient.id, event_type="appointment_reminder"
    )
    linked = await service.send_linked_user_telegram_notification(
        db=db_session, user_id=case.user.id, event_type="appointment_reminder", message="SYNTHETIC"
    )
    assert event is allowed and linked is allowed
    assert service.send_telegram.await_count == (2 if allowed else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_id,allowed", [(-1009876543210, False), (-42, False), (0, False), (86753099, True)])
async def test_templated_patient_sender_requires_private_link(db_session, telegram_case, chat_id, allowed):
    case = telegram_case
    case.link.chat_id = chat_id
    db_session.commit()
    service = NotificationSenderService()
    service.send_telegram = AsyncMock(return_value=True)
    result = await service.send_templated_notification(
        db=db_session, notification_type="appointment_reminder", channel="telegram",
        recipient_contact="caller-supplied-ignored", template_data={"message": "SYNTHETIC"},
        recipient_type="patient", recipient_id=case.patient.id,
    )
    assert (result is not None) is allowed
    assert service.send_telegram.await_count == (1 if allowed else 0)
    if allowed:
        assert service.send_telegram.await_args.args[1] == str(chat_id)


@pytest.mark.parametrize("chat_id,allowed", [(-1009876543210, False), (0, False), (86753099, True)])
@pytest.mark.parametrize("direct_link", [False, True])
def test_mobile_self_test_patient_link_requires_private_chat(
    client, db_session, telegram_case, chat_id, allowed, direct_link
):
    case = telegram_case
    case.patient.user_id = case.user.id
    case.link.user_id = case.user.id if direct_link else None
    case.link.chat_id = chat_id
    db_session.commit()
    response = client.post("/api/v1/telegram-integration/send-notification", headers=case.headers, json={})
    assert response.status_code == (200 if allowed else 404), response.text
    assert case.service.send_plain_message.await_count == (1 if allowed else 0)
