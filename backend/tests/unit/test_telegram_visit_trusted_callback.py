"""Prove the real secret-checked webhook reaches the trusted patient action."""

import base64
import struct
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import telegram_webhook
from app.core.config import settings
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.telegram_config import TelegramConfig, TelegramUser
from app.models.visit import VisitService
from app.services import telegram_webhook_dedup
from app.services.appointment_rsvp import make_appointment_callback
from app.services.notifications_pkg import NotificationSenderService
from app.services.telegram_bot import TelegramBotService
from app.services.visit_confirmation_service import build_telegram_visit_action_token


@pytest.fixture(autouse=True)
def secure_review_origin(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://synthetic.example")


@pytest.fixture
def telegram_visit_price(db_session, test_visit):
    # Seed the price before issuing any callback for this visit.
    db_session.add(VisitService(
        visit_id=test_visit.id, service_id=123, name="SYNTHETIC",
        qty=1, price=Decimal("1.00"), currency="UZS",
    ))
    db_session.commit()


@pytest.mark.parametrize("operation", ["confirm", "cancel"])
@pytest.mark.usefixtures("telegram_visit_price")
def test_authenticated_private_callback_controls_only_linked_visit(
    client, db_session, test_visit, monkeypatch, operation
):
    config = db_session.query(TelegramConfig).first()
    if config is None:
        config = TelegramConfig()
        db_session.add(config)
    config.bot_token = "SYNTHETIC-bot-credential"
    config.webhook_secret = "SYNTHETIC-webhook-secret"
    config.active = True
    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id,
                        active=True, blocked=False)
    db_session.add(link)
    test_visit.status = "pending_confirmation"
    test_visit.visit_date = (datetime.now(UTC) + timedelta(days=3)).date()
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_token = "SYNTHETIC-webhook-visit-token"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.commit()
    capability = build_telegram_visit_action_token(
        visit_id=test_visit.id, confirmation_token=test_visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=test_visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=test_visit.confirmation_context_epoch,
    )

    service = TelegramBotService()
    service.active = True
    service.bot_token = "SYNTHETIC-bot-credential"
    service._answer_callback_query = AsyncMock(return_value=True)
    monkeypatch.setattr(telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=service))
    monkeypatch.setattr(telegram_webhook_dedup, "resolve_ledger_bot_identity", AsyncMock(return_value="SYNTHETIC-bot"))

    update = {"callback_query": {"id": "SYNTHETIC-callback", "from": {"id": 740610010},
              "message": {"chat": {"id": 740610010, "type": "private"}},
              "data": f"{operation}_visit:{capability}"}}
    path = "/api/v1/telegram/webhook"
    bad_secret = client.post(path, json=update, headers={"x-telegram-bot-api-secret-token": "wrong"})
    assert bad_secret.status_code == 403
    db_session.refresh(test_visit)
    assert test_visit.status == "pending_confirmation"
    service._answer_callback_query.assert_not_awaited()

    response = client.post(path, json=update, headers={"x-telegram-bot-api-secret-token": "SYNTHETIC-webhook-secret"})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    db_session.refresh(test_visit)
    assert test_visit.status in ({"confirmed", "open"} if operation == "confirm" else {"canceled"})
    service._answer_callback_query.assert_awaited_once()


def test_authenticated_webhook_dispatches_signed_appointment_callback(client, db_session, test_patient, monkeypatch):
    config = db_session.query(TelegramConfig).first() or TelegramConfig()
    config.bot_token = "SYNTHETIC-bot-credential"
    config.webhook_secret = "SYNTHETIC-webhook-secret"
    config.active = True
    appointment = Appointment(patient_id=test_patient.id,
                              appointment_date=(datetime.now(UTC) + timedelta(days=4)).date(),
                              appointment_time="12:00", status="pending", occurrence_revision=0)
    link = TelegramUser(chat_id=740610010, patient_id=test_patient.id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    db_session.add_all([config, appointment, link])
    db_session.commit()
    data = make_appointment_callback("v", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    service = TelegramBotService()
    service.active = True
    service.bot_token = "SYNTHETIC-bot-credential"
    service._answer_callback_query = AsyncMock(return_value=True)
    service._httpx_post = AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"ok": True}))
    monkeypatch.setattr(telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=service))
    monkeypatch.setattr(telegram_webhook_dedup, "resolve_ledger_bot_identity", AsyncMock(return_value="SYNTHETIC-bot"))
    update = {"callback_query": {"id": "SYNTHETIC-callback", "from": {"id": link.chat_id},
              "message": {"chat": {"id": link.chat_id, "type": "private"}}, "data": data}}
    path = "/api/v1/telegram/webhook"
    assert client.post(path, json=update, headers={"x-telegram-bot-api-secret-token": "wrong"}).status_code == 403
    db_session.refresh(appointment)
    assert appointment.patient_rsvp_at is None
    response = client.post(path, json=update, headers={"x-telegram-bot-api-secret-token": "SYNTHETIC-webhook-secret"})
    assert response.status_code == 200, response.text
    db_session.refresh(appointment)
    assert appointment.patient_rsvp_at is None
    payload = service._httpx_post.await_args.kwargs["json"]
    assert "12:00" in payload["text"]
    update["callback_query"]["data"] = payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    update["callback_query"]["id"] = "SYNTHETIC-confirm-callback"
    response = client.post(path, json=update, headers={"x-telegram-bot-api-secret-token": "SYNTHETIC-webhook-secret"})
    assert response.status_code == 200, response.text
    db_session.refresh(appointment)
    assert appointment.patient_confirmed_at is not None
    assert appointment.status == "pending"
    assert appointment.payment_processed_at is None
    assert service._answer_callback_query.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type,actor", [("group", 740610010), ("private", 740610011)])
async def test_nonprivate_or_different_sender_fails_before_service(db_session, monkeypatch, chat_type, actor):
    service = TelegramBotService()
    service._answer_callback_query = AsyncMock(return_value=True)
    operation = AsyncMock()
    monkeypatch.setattr("app.services.visit_confirmation_service.VisitConfirmationService.confirm_by_telegram", operation)
    await service._handle_callback_query(
        {"id": "SYNTHETIC-callback", "from": {"id": actor},
         "message": {"chat": {"id": 740610010, "type": chat_type}},
         "data": "confirm_visit:SYNTHETIC-token"}, db_session,
    )
    operation.assert_not_called()
    service._answer_callback_query.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_exception_does_not_expose_sensitive_text(monkeypatch, caplog):
    service = TelegramBotService()
    service.bot_token = "SYNTHETIC-token"
    marker = "SYNTHETIC-CLINICAL-CANARY"
    def fail(*args, **kwargs):
        raise RuntimeError(marker)
    monkeypatch.setattr("app.services.telegram_bot.requests.post", fail)
    assert not await service._send_message(740610010, "SYNTHETIC")
    assert marker not in caplog.text


@pytest.mark.asyncio
@pytest.mark.usefixtures("telegram_visit_price")
async def test_view_callback_sends_context_then_distinct_action(db_session, test_visit, monkeypatch):
    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    test_visit.status = "pending_confirmation"
    test_visit.visit_date = (datetime.now(UTC) + timedelta(days=3)).date()
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_token = "SYNTHETIC-view-token"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    test_visit.visit_time = "15:45"
    db_session.add(link)
    db_session.commit()
    view = build_telegram_visit_action_token(
        visit_id=test_visit.id, confirmation_token=test_visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=test_visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=test_visit.confirmation_context_epoch, purpose="view",
    )
    service = TelegramBotService()
    service.bot_token = "SYNTHETIC-bot-credential"
    service._answer_callback_query = AsyncMock(return_value=True)
    service._httpx_post = AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {"ok": True}))
    callback = {"id": "SYNTHETIC-callback", "from": {"id": link.chat_id},
                "message": {"chat": {"id": link.chat_id, "type": "private"}},
                "data": f"view_visit:{view}"}
    await service._handle_callback_query(callback, db_session)
    payload = service._httpx_post.await_args.kwargs["json"]
    assert payload["text"] == "У вас новое уведомление."
    assert "15:45" not in payload["text"] and payload["chat_id"] == link.chat_id
    actions = payload["reply_markup"]["inline_keyboard"]
    assert f"#token={view}&review=telegram" in actions[0][0]["url"]
    assert "SYNTHETIC-view-token" not in actions[0][0]["url"]
    from app.services.visit_confirmation_service import VisitConfirmationService
    assert VisitConfirmationService(db_session).get_visit_info(view)["visit_time"] == "15:45"
    db_session.rollback()
    action = actions[1][0]["callback_data"]
    assert action.startswith("confirm_visit:ta") and view not in action
    db_session.refresh(test_visit)
    assert test_visit.status == "pending_confirmation"
    callback["data"] = action
    await service._handle_callback_query(callback, db_session)
    db_session.refresh(test_visit)
    assert test_visit.status in {"confirmed", "open"}


@pytest.mark.asyncio
async def test_unsafe_review_origin_never_sends_token(db_session, test_visit, monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://clinic.example")
    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    test_visit.status = "pending_confirmation"
    test_visit.visit_date = (datetime.now(UTC) + timedelta(days=3)).date()
    test_visit.visit_time = "15:45"
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_token = "SYNTHETIC-no-unsafe-send"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(link)
    db_session.commit()
    view = build_telegram_visit_action_token(
        visit_id=test_visit.id, confirmation_token=test_visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=test_visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=test_visit.confirmation_context_epoch, purpose="view",
    )
    service = TelegramBotService()
    service.bot_token = "SYNTHETIC-bot"
    service._answer_callback_query = AsyncMock(return_value=True)
    service._httpx_post = AsyncMock()
    await service._handle_callback_query(
        {"id": "SYNTHETIC-callback", "from": {"id": link.chat_id},
         "message": {"chat": {"id": link.chat_id, "type": "private"}},
         "data": f"view_visit:{view}"}, db_session,
    )
    service._httpx_post.assert_not_awaited()
    assert view not in str(service._answer_callback_query.await_args)
    assert "SYNTHETIC-no-unsafe-send" not in str(service._answer_callback_query.await_args)


@pytest.mark.asyncio
@pytest.mark.usefixtures("telegram_visit_price")
async def test_future_date_only_issuer_view_and_action(db_session, test_visit, monkeypatch):
    from app.services.visit_confirmation_service import VisitConfirmationService

    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    test_visit.visit_date = (datetime.now(UTC) + timedelta(days=4)).date()
    test_visit.visit_time = None
    test_visit.status = "pending_confirmation"
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_token = "SYNTHETIC-date-only-token"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(link)
    db_session.commit()
    sender = NotificationSenderService(db=db_session)
    fake_send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender.telegram_bot, "send_confirmation_invitation", fake_send)
    data = sender._prepare_notification_data(db_session, test_visit, test_visit.patient)
    assert (await sender._send_telegram_invitation(test_visit.patient, data, db_session))["success"]
    callback = fake_send.await_args.kwargs["keyboard"][0][0]["callback_data"]
    preview = VisitConfirmationService(db_session).preview_by_telegram(
        token=callback.split(":", 1)[1], telegram_user_id=str(link.chat_id))
    assert preview["text"] == "У вас новое уведомление."
    assert f"#token={callback.split(':', 1)[1]}&review=telegram" in preview["view_url"]
    result = VisitConfirmationService(db_session).confirm_by_telegram(
        token=preview["action_token"], telegram_user_id=str(link.chat_id), source_ip=None, user_agent="telegram")
    assert result["success"]


@pytest.mark.asyncio
async def test_preview_send_after_subject_deletion_contains_no_clinical_details(db_session, test_visit):
    from app.services.visit_confirmation_service import (
        VisitConfirmationDomainError,
        VisitConfirmationService,
    )

    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    test_visit.status = "pending_confirmation"
    test_visit.visit_date = (datetime.now(UTC) + timedelta(days=3)).date()
    test_visit.visit_time = "15:45"
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_token = "SYNTHETIC-stale-preview"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(link)
    db_session.commit()
    capability = build_telegram_visit_action_token(
        visit_id=test_visit.id, confirmation_token=test_visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=test_visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=test_visit.confirmation_context_epoch, purpose="view",
    )
    service = TelegramBotService()
    service.bot_token = "SYNTHETIC-bot"
    service._answer_callback_query = AsyncMock(return_value=True)
    checked = []

    async def transfer_before_send(*args, **kwargs):
        patient = db_session.get(Patient, test_visit.patient_id)
        patient.is_deleted = True
        db_session.commit()
        assert kwargs["json"]["text"] == "У вас новое уведомление."
        assert "15:45" not in kwargs["json"]["text"]
        with pytest.raises(VisitConfirmationDomainError):
            VisitConfirmationService(db_session).get_visit_info(capability)
        checked.append(True)
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    service._httpx_post = AsyncMock(side_effect=transfer_before_send)
    await service._handle_callback_query(
        {"id": "SYNTHETIC-callback", "from": {"id": link.chat_id},
         "message": {"chat": {"id": link.chat_id, "type": "private"}},
         "data": f"view_visit:{capability}"}, db_session,
    )
    service._httpx_post.assert_awaited_once()
    service._answer_callback_query.assert_awaited_once()
    assert checked == [True]


@pytest.mark.asyncio
async def test_reminder_issues_chat_bound_capability(db_session, test_visit, monkeypatch):
    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    db_session.add(link)
    test_visit.confirmation_token = "SYNTHETIC-raw-pwa-token"
    db_session.commit()
    sender = NotificationSenderService(db=db_session)
    fake_send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender.telegram_bot, "send_confirmation_invitation", fake_send)
    monkeypatch.setattr(sender, "_prepare_notification_data", lambda *args: {
        "doctor_name": "SYNTHETIC", "visit_date": "SYNTHETIC", "visit_time": "SYNTHETIC"
    })
    result = await sender.send_confirmation_reminder(db_session, test_visit.id, channel="telegram")
    assert result["success"]
    kwargs = fake_send.await_args.kwargs
    assert kwargs["chat_id"] == link.chat_id
    capability = build_telegram_visit_action_token(
        visit_id=test_visit.id, confirmation_token=test_visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=test_visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=test_visit.confirmation_context_epoch, purpose="view",
    )
    assert capability in str(kwargs["keyboard"])
    assert test_visit.confirmation_token not in str(kwargs["keyboard"])
    assert kwargs["message"] == "У вас новое уведомление."
    assert "визит" not in str(kwargs["keyboard"]).lower()
    decoded = base64.urlsafe_b64decode(capability[2:] + "=")
    assert decoded[:16] != struct.pack(">IIQ", test_visit.id, link.id, link.patient_link_epoch)


@pytest.mark.asyncio
@pytest.mark.parametrize("producer", ["invitation", "reminder"])
@pytest.mark.parametrize("failure", ["raise", "return"])
async def test_telegram_provider_failures_hide_sensitive_details(
    db_session, test_visit, monkeypatch, caplog, producer, failure
):
    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    db_session.add(link)
    test_visit.confirmation_token = "SYNTHETIC-raw-pwa-token"
    db_session.commit()
    sender = NotificationSenderService(db=db_session)
    marker = "SYNTHETIC-CLINICAL-CANARY"
    fake_send = AsyncMock(side_effect=RuntimeError(marker)) if failure == "raise" else AsyncMock(return_value={"success": False, "error": marker})
    monkeypatch.setattr(sender.telegram_bot, "send_confirmation_invitation", fake_send)
    data = {"visit_id": test_visit.id, "confirmation_token": test_visit.confirmation_token,
            "confirmation_context_epoch": test_visit.confirmation_context_epoch}
    if producer == "invitation":
        result = await sender._send_telegram_invitation(test_visit.patient, data, db_session)
    else:
        monkeypatch.setattr(sender, "_prepare_notification_data", lambda *args: data)
        result = await sender.send_confirmation_reminder(db_session, test_visit.id, channel="telegram")
    assert not result["success"]
    assert marker not in str(result)
    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_reminder_rechecks_revocation_before_dispatch(db_session, test_visit, monkeypatch):
    link = TelegramUser(chat_id=740610010, patient_id=test_visit.patient_id, active=True,
                        blocked=False, notifications_enabled=True, appointment_reminders=True)
    db_session.add(link)
    test_visit.confirmation_token = "SYNTHETIC-raw-pwa-token"
    db_session.commit()
    sender = NotificationSenderService(db=db_session)
    fake_send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender.telegram_bot, "send_confirmation_invitation", fake_send)
    monkeypatch.setattr(sender, "_prepare_notification_data", lambda *args: {})
    commit = db_session.commit
    first_commit = True

    def revoke_on_first_commit():
        nonlocal first_commit
        commit()
        if first_commit:
            first_commit = False
            link.notifications_enabled = False
            commit()

    monkeypatch.setattr(db_session, "commit", revoke_on_first_commit)
    result = await sender.send_confirmation_reminder(db_session, test_visit.id, channel="telegram")
    assert not result["success"]
    fake_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_pwa_reminder_never_delivers_snapshot_after_patient_transfer(db_session, test_visit, monkeypatch):
    from sqlalchemy import text

    replacement = Patient(first_name="SYNTHETIC", last_name="NEW")
    db_session.add(replacement)
    test_visit.confirmation_token = "SYNTHETIC-original-token"
    db_session.commit()
    sender = NotificationSenderService(db=db_session)
    monkeypatch.setattr(sender, "_prepare_notification_data", lambda db, visit, patient: {
        "confirmation_token": visit.confirmation_token, "patient_id": patient.id,
    })
    monkeypatch.setattr(sender, "_patient_channel_opted_in", lambda **kwargs: True)
    send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender, "_send_pwa_invitation", send)
    commit = db_session.commit
    first = True

    def transfer_after_snapshot():
        nonlocal first
        commit()
        if first:
            first = False
            db_session.execute(text("UPDATE visits SET patient_id = :patient, confirmation_token = :token WHERE id = :id"),
                               {"patient": replacement.id, "token": "SYNTHETIC-new-token", "id": test_visit.id})
            commit()

    monkeypatch.setattr(db_session, "commit", transfer_after_snapshot)
    result = await sender.send_confirmation_reminder(db_session, test_visit.id, channel="pwa")
    assert not result["success"]
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_pwa_reminder_rejects_worker_snapshot_after_transfer(db_session, test_visit, monkeypatch):
    from sqlalchemy import text

    replacement = Patient(first_name="SYNTHETIC", last_name="NEW")
    db_session.add(replacement)
    test_visit.confirmation_token = "SYNTHETIC-original-token"
    db_session.commit()
    expected = {name: getattr(test_visit, name) for name in (
        "patient_id", "confirmation_context_epoch", "reminder_generation",
        "reminder_claimed_at", "confirmation_token")}
    # Leave the old ORM object in the identity map while the stored owner and
    # token change; the issuer must fetch current state before preparing data.
    db_session.execute(text("UPDATE visits SET patient_id = :patient, confirmation_token = :token WHERE id = :id"),
                       {"patient": replacement.id, "token": "SYNTHETIC-new-token", "id": test_visit.id})
    sender = NotificationSenderService(db=db_session)
    send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender, "_send_pwa_invitation", send)
    result = await sender.send_confirmation_reminder(db_session, test_visit.id, channel="pwa", expected_context=expected)
    assert not result["success"]
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduled_invitation_rejects_transfer_before_dispatch(db_session, test_visit, monkeypatch):
    from sqlalchemy import text

    replacement = Patient(first_name="SYNTHETIC", last_name="NEW")
    db_session.add(replacement)
    test_visit.confirmation_token = "SYNTHETIC-original-token"
    db_session.commit()
    expected = {name: getattr(test_visit, name) for name in (
        "patient_id", "confirmation_context_epoch", "confirmation_token")}
    sender = NotificationSenderService(db=db_session)
    send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender, "_send_pwa_invitation", send)

    def prepare_then_transfer(db, visit, patient):
        data = {"confirmation_token": visit.confirmation_token}
        db.execute(text("UPDATE visits SET patient_id = :patient, confirmation_token = :token WHERE id = :id"),
                   {"patient": replacement.id, "token": "SYNTHETIC-new-token", "id": visit.id})
        return data

    monkeypatch.setattr(sender, "_prepare_notification_data", prepare_then_transfer)
    result = await sender.send_visit_confirmation_invitation(
        db_session, test_visit.id, channel="pwa", expected_context=expected)
    assert not result["success"]
    send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, ""])
async def test_scheduled_invitation_requires_bearer(db_session, test_visit, monkeypatch, token):
    test_visit.confirmation_token = token
    db_session.commit()
    expected = {name: getattr(test_visit, name) for name in (
        "patient_id", "confirmation_context_epoch", "confirmation_token")}
    sender = NotificationSenderService(db=db_session)
    send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender, "_send_pwa_invitation", send)
    result = await sender.send_visit_confirmation_invitation(
        db_session, test_visit.id, channel="pwa", expected_context=expected)
    assert not result["success"]
    send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_id", [0, -100123456])
async def test_reminder_rejects_non_private_chat(db_session, test_visit, monkeypatch, chat_id):
    db_session.query(TelegramUser).filter_by(patient_id=test_visit.patient_id).delete()
    db_session.add(TelegramUser(chat_id=chat_id, patient_id=test_visit.patient_id, active=True,
                                blocked=False, notifications_enabled=True, appointment_reminders=True))
    test_visit.confirmation_token = "SYNTHETIC-token"
    db_session.commit()
    sender = NotificationSenderService(db=db_session)
    fake_send = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(sender.telegram_bot, "send_confirmation_invitation", fake_send)
    result = await sender.send_confirmation_reminder(db_session, test_visit.id, channel="telegram")
    assert not result["success"]
    fake_send.assert_not_awaited()
