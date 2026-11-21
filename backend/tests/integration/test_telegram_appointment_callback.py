"""Patient reminders are bound to a private chat and a booked occurrence."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, normalize_appointment_status
from app.models.telegram_config import TelegramUser
from app.services.appointment_rsvp import (
    apply_appointment_decision,
    make_appointment_callback,
    parse_appointment_callback,
    preview_appointment_decision,
)
from app.services.telegram import bot as bot_module
from app.services.telegram.bot import ClinicTelegramBot


@pytest.fixture
def appointment_link(db_session, test_patient):
    appointment = Appointment(
        patient_id=test_patient.id, appointment_date=(datetime.now(UTC) + timedelta(days=4)).date(),
        appointment_time="12:00", status="pending", occurrence_revision=0,
    )
    link = TelegramUser(
        patient_id=test_patient.id, chat_id=413371, active=True, blocked=False,
        notifications_enabled=True, appointment_reminders=True,
    )
    db_session.add_all([appointment, link])
    db_session.commit()
    return appointment, link


def test_confirm_is_idempotent_and_never_changes_payment_status(db_session, appointment_link):
    appointment, link = appointment_link
    data = make_appointment_callback("c", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    result = apply_appointment_decision(db_session, callback_data=data, chat_id=link.chat_id)
    db_session.refresh(appointment)
    assert result == "confirmed"
    assert normalize_appointment_status(appointment.status) == AppointmentStatus.PENDING
    assert appointment.payment_processed_at is None
    assert appointment.patient_confirmed_at is not None
    first = appointment.patient_rsvp_at
    data = make_appointment_callback("c", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    result = apply_appointment_decision(db_session, callback_data=data, chat_id=link.chat_id)
    db_session.refresh(appointment)
    assert result == "already_confirmed"
    assert appointment.patient_rsvp_at == first


@pytest.mark.parametrize("state", ["no_show", "completed", "cancelled", "in_visit", "mystery"])
def test_terminal_or_unknown_status_is_never_cancelled(db_session, appointment_link, state):
    appointment, link = appointment_link
    appointment.status = state
    db_session.commit()
    data = make_appointment_callback("x", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    assert apply_appointment_decision(db_session, callback_data=data, chat_id=link.chat_id) == "unavailable"
    db_session.refresh(appointment)
    assert appointment.status == state


def test_cancellation_respects_24_hour_policy(db_session, appointment_link):
    appointment, link = appointment_link
    appointment.appointment_date = (datetime.now(UTC) + timedelta(days=1)).date()
    db_session.commit()
    data = make_appointment_callback("x", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    result = apply_appointment_decision(db_session, callback_data=data, chat_id=link.chat_id,
                                        now=datetime.combine(appointment.appointment_date, datetime.min.time(), tzinfo=UTC))
    assert result == "unavailable"
    db_session.refresh(appointment)
    assert appointment.status == "pending"


@pytest.mark.parametrize("field,value", [
    ("active", False), ("blocked", True), ("notifications_enabled", False),
    ("appointment_reminders", False), ("patient_id", None),
])
def test_inactive_unlinked_or_nonconsenting_chat_is_denied(db_session, appointment_link, field, value):
    appointment, link = appointment_link
    setattr(link, field, value)
    db_session.commit()
    data = make_appointment_callback("c", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    result = apply_appointment_decision(db_session, callback_data=data, chat_id=link.chat_id)
    assert result == "unavailable"
    db_session.refresh(appointment)
    assert appointment.patient_rsvp_at is None


def test_callback_parser_rejects_old_unsigned_callbacks():
    signed = make_appointment_callback("c", 34, 12, 413371, 7, 2)
    assert len(signed.encode()) <= 64
    parsed = parse_appointment_callback(signed)
    assert parsed[0] == "c"
    assert parsed[2:4] != (34, 12)
    assert parse_appointment_callback("confirm_34") is None


def test_callback_hides_metadata_and_fits_telegram_limit(monkeypatch):
    from app.services import appointment_rsvp

    monkeypatch.setattr(appointment_rsvp.secrets, "randbits", lambda bits: 2**bits - 1)
    maximum = make_appointment_callback("c", 2**31 - 1, 2**63 - 1, 413371, 7, 2**52)
    parsed = parse_appointment_callback(maximum)
    assert len(maximum.encode()) <= 64
    assert parsed[1] == 2**64 - 1
    assert parsed[2:4] != (2**31 - 1, 2**63 - 1)


@pytest.mark.parametrize("tamper", ["action", "signature"])
def test_modified_callback_never_changes_appointment(db_session, appointment_link, tamper):
    appointment, link = appointment_link
    data = make_appointment_callback("c", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    if tamper == "action":
        data = data.replace("ar:c:", "ar:x:", 1)
    else:
        data = data[:-1] + ("0" if data[-1] != "0" else "1")
    assert apply_appointment_decision(db_session, callback_data=data, chat_id=link.chat_id) == "stale"
    db_session.refresh(appointment)
    assert appointment.status == "pending"
    assert appointment.patient_rsvp_at is None


def test_callback_signature_is_bound_to_current_chat_link_and_epoch(db_session, appointment_link):
    appointment, link = appointment_link
    data = make_appointment_callback("c", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    # A copied button cannot be used in another linked chat.
    other = TelegramUser(patient_id=appointment.patient_id, chat_id=413372, active=True,
                         blocked=False, notifications_enabled=True, appointment_reminders=True)
    db_session.add(other)
    db_session.commit()
    assert apply_appointment_decision(db_session, callback_data=data, chat_id=other.chat_id) == "stale"
    # Revocation followed by re-enabling must not resurrect a prior button.
    initial_epoch = link.patient_link_epoch
    link.notifications_enabled = False
    db_session.commit()
    link.notifications_enabled = True
    db_session.commit()
    assert link.patient_link_epoch != initial_epoch
    assert apply_appointment_decision(db_session, callback_data=data, chat_id=link.chat_id) == "stale"
    db_session.refresh(appointment)
    assert appointment.patient_rsvp_at is None


def test_preview_distinguishes_two_bookings_and_actions_remain_bound(db_session, appointment_link):
    first, link = appointment_link
    second = Appointment(patient_id=first.patient_id, appointment_date=first.appointment_date + timedelta(days=1),
                         appointment_time="14:30", status="pending", occurrence_revision=0)
    db_session.add(second)
    db_session.commit()
    first_id, second_id, chat_id, link_id, epoch = first.id, second.id, link.chat_id, link.id, link.patient_link_epoch
    view_first = make_appointment_callback("v", first_id, 0, chat_id, link_id, epoch)
    view_second = make_appointment_callback("v", second_id, 0, chat_id, link_id, epoch)
    assert apply_appointment_decision(db_session, callback_data=view_first, chat_id=chat_id) == "invalid"
    first_preview = preview_appointment_decision(db_session, callback_data=view_first, chat_id=chat_id)
    second_preview = preview_appointment_decision(db_session, callback_data=view_second, chat_id=chat_id)
    assert "12:00" in first_preview["text"]
    assert "14:30" in second_preview["text"]
    assert first_preview["text"] != second_preview["text"]
    assert apply_appointment_decision(db_session, callback_data=second_preview["confirm_data"], chat_id=chat_id) == "confirmed"
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.patient_rsvp_at is None
    assert second.patient_rsvp_at is not None


def test_preview_fails_after_revoke_or_occurrence_change(db_session, appointment_link):
    appointment, link = appointment_link
    appointment_id, chat_id, link_id, epoch = appointment.id, link.chat_id, link.id, link.patient_link_epoch
    view = make_appointment_callback("v", appointment_id, 0, chat_id, link_id, epoch)
    preview = preview_appointment_decision(db_session, callback_data=view, chat_id=chat_id)
    assert preview
    link.active = False
    db_session.commit()
    assert preview_appointment_decision(db_session, callback_data=view, chat_id=chat_id) is None
    assert apply_appointment_decision(db_session, callback_data=preview["confirm_data"], chat_id=chat_id) == "unavailable"
    link.active = True
    db_session.commit()
    assert preview_appointment_decision(db_session, callback_data=view, chat_id=chat_id) is None
    view = make_appointment_callback("v", appointment_id, 0, chat_id, link_id, link.patient_link_epoch)
    appointment.occurrence_revision = 1
    db_session.commit()
    assert preview_appointment_decision(db_session, callback_data=view, chat_id=chat_id) is None


def callback(data, *, actor=413371, chat=413371, chat_type="private", edit_error=None):
    message = SimpleNamespace(chat=SimpleNamespace(id=chat, type=chat_type), text="SYNTHETIC")
    message.edit_text = AsyncMock(side_effect=edit_error)
    message.answer = AsyncMock()
    return SimpleNamespace(data=data, message=message, from_user=SimpleNamespace(id=actor), answer=AsyncMock())


@pytest.mark.asyncio
async def test_view_rejects_untrusted_actor_before_retrieving_context(monkeypatch):
    retrieve = AsyncMock()
    monkeypatch.setattr(bot_module, "_run_appointment_preview", retrieve)
    event = callback(make_appointment_callback("v", 34, 0, 413371, 7, 1), actor=999)
    await ClinicTelegramBot().handle_callback(event)
    retrieve.assert_not_called()
    event.message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_view_displays_context_then_action_buttons(monkeypatch):
    monkeypatch.setattr(bot_module, "_run_appointment_preview", lambda *args: {
        "text": "Дата: 2030-01-01\nВремя: 12:00", "confirm_data": "ar:c:test", "cancel_data": "ar:x:test"})
    event = callback(make_appointment_callback("v", 34, 0, 413371, 7, 1))
    await ClinicTelegramBot().handle_callback(event)
    kwargs = event.message.answer.await_args.kwargs
    assert "12:00" in kwargs["text"]
    assert kwargs["parse_mode"] is None
    assert len(kwargs["reply_markup"].inline_keyboard[0]) == 2
    event.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_visit_view_checks_actor_and_then_shows_explicit_actions(monkeypatch):
    calls = []
    def preview(token, actor):
        calls.append((token, actor))
        return {"text": "Время: 14:30", "action_token": "ta_synthetic"}
    monkeypatch.setattr(bot_module, "_run_visit_preview", preview)
    wrong_actor = callback("view_visit:tv_synthetic", actor=999)
    await ClinicTelegramBot().handle_callback(wrong_actor)
    assert calls == []
    wrong_actor.message.answer.assert_not_awaited()
    event = callback("view_visit:tv_synthetic")
    await ClinicTelegramBot().handle_callback(event)
    assert calls == [("tv_synthetic", 413371)]
    kwargs = event.message.answer.await_args.kwargs
    assert "14:30" in kwargs["text"]
    assert kwargs["parse_mode"] is None
    buttons = kwargs["reply_markup"].inline_keyboard[0]
    assert [button.callback_data for button in buttons] == ["confirm_visit:ta_synthetic", "cancel_visit:ta_synthetic"]


@pytest.mark.asyncio
async def test_committed_decision_acknowledged_even_when_edit_fails(monkeypatch):
    bot = ClinicTelegramBot()
    decision = lambda *args: "confirmed"
    monkeypatch.setattr(bot_module, "_run_appointment_decision", decision)
    event = callback(make_appointment_callback("c", 34, 0, 413371, 7, 0), edit_error=RuntimeError("edit"))
    await bot.handle_callback(event)
    event.answer.assert_awaited_once()
    assert "подтверждена" in event.answer.await_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("actor,chat,chat_type", [(413372, 413371, "private"), (413371, 413371, "group")])
async def test_callback_requires_telegram_private_actor(monkeypatch, actor, chat, chat_type):
    bot = ClinicTelegramBot()
    decision = AsyncMock()
    monkeypatch.setattr(bot_module, "_run_appointment_decision", decision)
    event = callback(make_appointment_callback("c", 34, 0, 413371, 7, 0), actor=actor, chat=chat, chat_type=chat_type)
    await bot.handle_callback(event)
    decision.assert_not_called()
    event.answer.assert_awaited_once()
