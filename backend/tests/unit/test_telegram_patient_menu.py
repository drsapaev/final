from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest

from app.api.v1.endpoints import telegram_webhook
from app.core.config import settings
from app.models.clinic import ClinicSettings
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.telegram_config import PatientOnboardingRequest, TelegramUser
from app.models.visit import Visit
from app.services.telegram_bot import TelegramBotService

pytestmark = pytest.mark.asyncio

CHAT_ID = 76711
FRONTEND_URL = "https://clinic.example"
PATIENT_NAME = "SYNTHETIC-MenuChart"
VISIT_DATE = date(2040, 2, 1)


@pytest.fixture(params=["service", "fallback"])
def bot(request, monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", FRONTEND_URL)
    if request.param == "service":
        service = TelegramBotService()
        # Spy on the actual implementation rather than replacing the dispatch.
        service.process_patient_bot_update = AsyncMock(
            wraps=service.process_patient_bot_update
        )
    else:
        service = SimpleNamespace()
    service._send_message = AsyncMock(return_value=True)
    service._send_document = AsyncMock(return_value=(True, 1, None))
    service.process_webhook_update = AsyncMock()
    return service


def _update(
    text, *, chat_id=CHAT_ID, sender_id=CHAT_ID, chat_type="private", is_bot=False
):
    return {
        "message": {
            "chat": {"id": chat_id, "type": chat_type},
            "from": {"id": sender_id, "language_code": "ru", "is_bot": is_bot},
            "text": text,
        }
    }


async def _reply(db, bot, text):
    bot._send_message.reset_mock()
    router = getattr(bot, "process_patient_bot_update", None)
    if router is not None:
        router.reset_mock()
    assert await telegram_webhook._handle_clinic_bot_update(_update(text), db, bot)
    if router is not None:
        router.assert_awaited_once()
    bot._send_message.assert_awaited_once()
    bot.process_webhook_update.assert_not_awaited()
    recipient, message, markup = bot._send_message.await_args.args
    assert recipient == CHAT_ID
    return message, markup


def _buttons(markup):
    return [button for row in markup.get("keyboard", []) for button in row]


def _inline_buttons(markup):
    return [button for row in markup.get("inline_keyboard", []) for button in row]


def _assert_web_app(markup, section):
    (button,) = _inline_buttons(markup)
    url = urlsplit(button["web_app"]["url"])
    assert (url.scheme, url.netloc, url.path) == (
        "https",
        "clinic.example",
        "/telegram/mini-app/patient",
    )
    assert parse_qs(url.query) == {"section": [section]}
    assert not url.fragment
    assert "url" not in button
    return button


def _profile(db, *, linked=False, language="ru", active=True, blocked=False):
    patient = None
    if linked:
        patient = Patient(first_name="SYNTHETIC-Menu", last_name="MenuChart")
        db.add(patient)
        db.flush()

    user = TelegramUser(
        chat_id=CHAT_ID,
        patient_id=patient.id if patient else None,
        language_code=language,
        active=active,
        blocked=blocked,
        notifications_enabled=True,
        appointment_reminders=False,
        lab_notifications=True,
    )
    db.add(user)
    db.commit()
    return user


def _preferences(profile):
    return (
        profile.active,
        profile.blocked,
        profile.notifications_enabled,
        profile.appointment_reminders,
        profile.lab_notifications,
        profile.patient_id,
    )


@pytest.mark.parametrize(
    ("language", "labels"),
    [
        ("ru", ["Записаться", "Мой кабинет", "Результаты", "Клиника", "Настройки"]),
        (
            "uz-Latn",
            [
                "Qabulga yozilish",
                "Mening kabinetim",
                "Natijalar",
                "Klinika",
                "Sozlamalar",
            ],
        ),
    ],
)
async def test_linked_start_keeps_profile_and_uses_saved_language(
    db_session, bot, language, labels
):
    user = _profile(db_session, linked=True, language=language)
    previous = _preferences(user)

    for command in ("/start@clinic_bot", "/start"):
        _, markup = await _reply(db_session, bot, command)
        buttons = _buttons(markup)
        assert len(buttons) == len(labels)
        assert all(
            button["text"].endswith(label)
            for button, label in zip(buttons, labels, strict=True)
        )
        assert not any(button.get("request_contact") for button in buttons)

    db_session.refresh(user)
    assert user.language_code == language
    assert _preferences(user) == previous


async def test_settings_language_change_keeps_notification_preferences(db_session, bot):
    profile = _profile(db_session, linked=True)
    previous = _preferences(profile)

    _, markup = await _reply(db_session, bot, "/settings")
    assert markup == telegram_webhook._localized_settings_menu("ru")
    _, markup = await _reply(db_session, bot, "🇺🇿 O'zbekcha")
    assert markup == telegram_webhook._localized_settings_menu("uz-Latn")

    db_session.refresh(profile)
    assert profile.language_code == "uz-Latn"
    assert _preferences(profile) == previous


@pytest.mark.parametrize(
    ("selection", "language"),
    [("Русский", "ru"), ("🇺🇿   O'zbekcha", "uz-Latn")],
)
async def test_new_patient_chooses_language_then_receives_contact_keyboard(
    db_session, bot, selection, language
):
    _, markup = await _reply(db_session, bot, "/start")
    assert markup == telegram_webhook.TELEGRAM_LANGUAGE_MENU

    _, markup = await _reply(db_session, bot, selection)
    buttons = _buttons(markup)
    assert len(buttons) == 2
    assert sum(bool(button.get("request_contact")) for button in buttons) == 1
    assert any(
        ("клиника" if language == "ru" else "klinika") in button["text"].casefold()
        for button in buttons
    )
    profile = db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).one()
    assert profile.language_code == language
    assert _preferences(profile) == (True, False, False, False, False, None)
    _, restarted = await _reply(db_session, bot, "/start")
    assert _buttons(restarted) == buttons


@pytest.mark.parametrize(
    ("language", "label"), [("ru", "Статус заявки"), ("uz-Latn", "Ariza holati")]
)
async def test_pending_request_status_is_available_only_via_mini_app(
    db_session, bot, language, label
):
    profile = _profile(db_session, language=language)
    request = PatientOnboardingRequest(
        telegram_user_id=profile.id,
        telegram_chat_id=CHAT_ID,
        status="pending_review",
        contact_name=PATIENT_NAME,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(request)
    db_session.commit()

    _, markup = await _reply(db_session, bot, "/menu")
    assert any(label in button["text"] for button in _buttons(markup))
    message, markup = await _reply(db_session, bot, label)
    assert PATIENT_NAME not in message
    assert "pending_review" not in message
    button = _assert_web_app(markup, "appointments")
    assert label.casefold() in button["text"].casefold()
    assert request.status == "pending_review"


@pytest.mark.parametrize(
    ("command", "section"),
    [
        ("/appointments@clinic_bot", "visits"),
        ("📅   Мои   визиты", "visits"),
        ("/profile", "cabinet"),
        ("📲   Bemor kabineti", "cabinet"),
        ("/results", "results"),
        ("Документы и чеки", "results"),
        ("Hujjatlar  va  cheklar", "results"),
        ("/queue", "queue"),
        ("To'lovlar va qarz", "payments"),
        ("/book", "appointments"),
        ("🧑‍⚕️   Врачи и расписание", "appointments"),
    ],
)
async def test_linked_actions_open_protected_sections_without_chat_data(
    db_session, bot, monkeypatch, command, section
):
    profile = _profile(db_session, linked=True)
    visit = Visit(
        patient_id=profile.patient_id,
        visit_date=VISIT_DATE,
        notes="SYNTHETIC clinical details",
    )
    db_session.add(visit)
    db_session.flush()
    db_session.add(Payment(visit_id=visit.id, amount=Decimal("61359.00")))
    db_session.commit()
    if section == "results":
        # A ready report would trigger the former PDF delivery path.
        monkeypatch.setattr(
            telegram_webhook,
            "_latest_ready_lab_report_instances",
            lambda db, patient_id: [SimpleNamespace(id=456)],
        )
        monkeypatch.setattr(
            telegram_webhook,
            "_build_lab_report_pdf",
            lambda db, report: ("synthetic.pdf", b"%PDF-1.4", "SYNTHETIC ready report"),
        )

    message, markup = await _reply(db_session, bot, command)
    _assert_web_app(markup, section)
    bot._send_document.assert_not_awaited()
    for prohibited in (
        "MenuChart",
        VISIT_DATE.isoformat(),
        "clinical details",
        "61 359",
        "61359",
        "SYNTHETIC ready report",
    ):
        assert prohibited not in message


@pytest.mark.parametrize("command", ["/results", "/documents"])
async def test_unlinked_profile_has_no_access_to_result_links_or_pdfs(
    db_session, bot, command
):
    _profile(db_session)
    message, markup = await _reply(db_session, bot, command)
    if _inline_buttons(markup):
        _assert_web_app(markup, "appointments")
    assert "MenuChart" not in message
    bot._send_document.assert_not_awaited()


@pytest.mark.parametrize(("active", "blocked"), [(True, True), (False, False)])
async def test_unavailable_profile_gets_clinic_without_preferences_changes(
    db_session, bot, active, blocked
):
    profile = _profile(db_session, linked=True, active=active, blocked=blocked)
    previous = _preferences(profile)
    for command in ("/start", "/results", "🇺🇿 O'zbekcha", "🔕 Без уведомлений"):
        message, markup = await _reply(db_session, bot, command)
        assert "MenuChart" not in message
        assert not _inline_buttons(markup)
        assert all(not button.get("request_contact") for button in _buttons(markup))
        assert any(
            "клиника" in button["text"].casefold() for button in _buttons(markup)
        )

    db_session.refresh(profile)
    assert profile.language_code == "ru"
    assert _preferences(profile) == previous
    bot._send_document.assert_not_awaited()


@pytest.mark.parametrize(
    "frontend_url", ["", "javascript:alert(1)", "http://clinic.example"]
)
async def test_linked_results_with_unavailable_url_have_no_inline_link(
    db_session, bot, monkeypatch, frontend_url
):
    _profile(db_session, linked=True)
    monkeypatch.setattr(settings, "FRONTEND_URL", frontend_url)
    message, markup = await _reply(db_session, bot, "/results")
    assert not _inline_buttons(markup)
    assert "MenuChart" not in message
    bot._send_document.assert_not_awaited()


@pytest.mark.parametrize(
    "update",
    [
        _update("/appointments", chat_id=-12, chat_type="group"),
        _update("/results@clinic_bot", sender_id=CHAT_ID + 1),
        _update("📄   Результаты", sender_id=True),
    ],
    ids=["group", "mismatched-sender", "boolean-sender"],
)
async def test_invalid_patient_commands_are_consumed_without_reply_or_profile(
    db_session, bot, update
):
    assert await telegram_webhook._handle_clinic_bot_update(update, db_session, bot)
    bot._send_message.assert_not_awaited()
    bot._send_document.assert_not_awaited()
    bot.process_webhook_update.assert_not_awaited()
    assert db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).first() is None


async def test_clinic_button_escapes_public_fields_and_keeps_navigation(
    db_session, bot
):
    _profile(db_session, linked=True)
    db_session.add_all(
        [
            ClinicSettings(
                category="clinic",
                key="clinic_address",
                value="SYNTHETIC <b>address</b>",
            ),
            ClinicSettings(
                category="clinic", key="clinic_phone", value="SYNTHETIC clinic phone"
            ),
            ClinicSettings(
                category="clinic", key="clinic_working_hours_start", value="08:30"
            ),
            ClinicSettings(
                category="clinic", key="clinic_working_hours_end", value="16:45"
            ),
        ]
    )
    db_session.commit()

    message, markup = await _reply(db_session, bot, "Клиника")
    assert "SYNTHETIC &lt;b&gt;address&lt;/b&gt;" in message
    assert "SYNTHETIC clinic phone" in message
    assert "08:30" in message and "16:45" in message
    assert "<b>address</b>" not in message
    assert "clinic_support" not in message
    assert not _inline_buttons(markup)
    _, markup = await _reply(db_session, bot, "Главное меню")
    assert markup == telegram_webhook._localized_main_menu("ru")


async def test_clinic_omits_missing_public_contact_fields(db_session, bot):
    db_session.add(
        ClinicSettings(
            category="clinic", key="clinic_working_hours_start", value="invalid"
        )
    )
    db_session.commit()

    message, markup = await _reply(db_session, bot, "/support")
    assert message
    assert all(label not in message for label in ("Телефон:", "Адрес:", "Часы работы:"))
    assert "https://" not in message
    assert not _inline_buttons(markup)


@pytest.mark.parametrize(
    ("active", "blocked"), [(False, False), (True, True), (True, False)]
)
async def test_dual_link_uses_patient_menu_for_plain_start(
    db_session, bot, registrar_user, active, blocked
):
    profile = _profile(db_session, linked=True, active=active, blocked=blocked)
    profile.user_id = registrar_user.id
    db_session.commit()

    _, markup = await _reply(db_session, bot, "/start")
    labels = [button["text"] for button in _buttons(markup)]
    if active and not blocked:
        assert any("Мой кабинет" in label for label in labels)
    else:
        assert len(labels) == 1
        assert "Клиника" in labels[0]
    assert not _inline_buttons(markup)


@pytest.mark.parametrize(
    "update",
    [
        _update("SYNTHETIC ignored", chat_type="group"),
        _update("SYNTHETIC ignored", sender_id=CHAT_ID + 1),
        _update("SYNTHETIC ignored", is_bot=True),
        {"message": None},
        {"message": {"chat": ["invalid"], "text": "SYNTHETIC ignored"}},
        _update("SYNTHETIC ignored", chat_id="invalid"),
        _update(None),
        _update("  "),
        _update({"text": "SYNTHETIC ignored"}),
    ],
    ids=[
        "group",
        "mismatched-sender",
        "bot",
        "bad-message",
        "bad-chat",
        "bad-chat-id",
        "no-text",
        "blank",
        "bad-text",
    ],
)
async def test_invalid_messages_do_not_reach_legacy_dispatch(db_session, bot, update):
    assert await telegram_webhook._handle_clinic_bot_update(update, db_session, bot)
    bot._send_message.assert_not_awaited()
    bot.process_webhook_update.assert_not_awaited()
    assert db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).first() is None


async def test_callback_still_passes_clinic_patient_dispatch(db_session, bot):
    assert not await telegram_webhook._handle_clinic_bot_update(
        {"callback_query": {"id": "synthetic-callback"}}, db_session, bot
    )


async def test_unknown_slash_command_returns_help_without_echo(db_session, bot):
    help_message, help_markup = await _reply(db_session, bot, "/help")
    message, markup = await _reply(db_session, bot, "/synthetic_unknown SYNTHETIC-NOTE")
    assert (message, markup) == (help_message, help_markup)
    assert "synthetic" not in message.casefold()


@pytest.mark.parametrize(
    ("language", "results_label", "protected_label"),
    [("ru", "результаты", "защищ"), ("uz-Latn", "natijalar", "himoya")],
)
async def test_help_points_to_protected_results_without_promising_pdfs(
    db_session, bot, language, results_label, protected_label
):
    _profile(db_session, linked=True, language=language)

    message, _ = await _reply(db_session, bot, "/help")

    assert any(
        results_label in line and protected_label in line
        for line in message.casefold().splitlines()
    )
    assert "pdf" not in message.casefold()
