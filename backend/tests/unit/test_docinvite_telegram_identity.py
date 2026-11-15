"""DOCVITE... DOCINVITE-BE-001 (audit #3892, group 19) — patient→Telegram identity contract.

The initial visit invitation previously required ``patient.telegram_id`` —
an attribute the Patient model NEVER had (the canonical link is
``TelegramUser.patient_id → chat_id``), so the Telegram invitation ALWAYS
failed for normal Patient ORM objects and auto channel choice never
prioritized Telegram. The fix (merged #4060) joins TelegramUser by
patient_id with explicit consent filters — the same pattern reminder
delivery already used.

These tests pin the audit's synthetic contract on the current
implementation:

1. a plain Patient ORM object with an ACTIVE/UNBLOCKED/CONSENTING linked
   TelegramUser gets the invitation dispatched to THAT chat (auto channel
   also prefers telegram);
2. unlinked / blocked / consent-withdrawn patients fail HONESTLY with
   zero dispatch attempts (notification_sent=false surfaced by the
   scheduling caller, never a silent crash).

No real Telegram API: telegram_bot is replaced with a recording fake.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.models.patient import Patient
from app.models.telegram_config import TelegramUser


def _patient(db, *, unique: str, phone: str | None = None):
    patient = Patient(
        last_name="Тестов", first_name="Пациент", birth_date=date(1990, 1, 1),
        sex="M",
        phone=phone,  # synthetic — no real-looking numbers
        email=f"p_{unique}@t.local",
        created_at=datetime.now(UTC), is_deleted=False,
    )
    db.add(patient)
    db.flush()
    return patient


def _link(db, patient_id: int, chat_id: int, *, active=True, blocked=False,
          notifications=True) -> TelegramUser:
    tu = TelegramUser(
        patient_id=patient_id,
        chat_id=chat_id,
        username=f"u_{chat_id}",
        language_code="ru",
        notifications_enabled=notifications,
        appointment_reminders=True,
        active=active,
        blocked=blocked,
    )
    db.add(tu)
    db.flush()
    return tu


def _invite_data() -> dict:
    return {
        "patient_name": "Тестов Пациент",
        "doctor_name": "Докторов Доктор",
        "visit_date": "2026-11-20",
        "visit_time": "10:00",
        "visit_type": "consultation",
        "services": ["• Консультация - 10000 сум"],
        "total_amount": "10000",
        "expires_at": None,
        "confirmation_token": "tok-invite-123",
    }


class _FakeBot:
    def __init__(self, *, succeed=True):
        self.calls: list[dict] = []
        self._succeed = succeed

    async def send_confirmation_invitation(self, **kwargs):
        self.calls.append(kwargs)
        if self._succeed:
            return {"success": True, "message_id": 42}
        return {"success": False, "error": "synthetic telegram outage"}


@pytest.mark.unit
class TestDocInviteTelegramIdentity:
    def test_invitation_dispatches_to_linked_chat(
        self, db_session, monkeypatch: pytest.MonkeyPatch
    ):
        """A plain Patient ORM object (no telegram_id attribute) with an
        active linked TelegramUser receives the invitation via THAT chat."""
        from app.services.notifications_pkg import NotificationSenderService

        patient = _patient(db_session, unique="linked1", phone="+998900000001")
        link = _link(db_session, patient.id, 777001)

        svc = NotificationSenderService(db=db_session)
        bot = _FakeBot()
        monkeypatch.setattr(svc, "telegram_bot", bot, raising=False)

        import asyncio

        result = asyncio.run(
            svc._send_telegram_invitation(patient, _invite_data(), db_session)
        )

        db_session.rollback()  # reading back the row is not needed; keep tx clean

        assert result["success"] is True, result
        assert result["channel"] == "telegram", result
        assert len(bot.calls) == 1
        call = bot.calls[0]
        assert call["chat_id"] == link.chat_id
        assert "Тестов Пациент" in call["message"]
        assert any(
            "confirm_visit:tok-invite-123" in btn["callback_data"]
            for row in call["keyboard"] for btn in row
        )

    def test_auto_channel_prefers_linked_telegram(self, db_session):
        """Auto channel choice resolves the chat via TelegramUser — linked
        consenting patient → telegram, even with a +998 phone that would
        otherwise win PWA."""
        from app.services.notifications_pkg import NotificationSenderService

        svc = NotificationSenderService(db=db_session)

        linked = _patient(db_session, unique="auto1", phone="+998900000002")
        _link(db_session, linked.id, 777002)

        unlinked = _patient(db_session, unique="auto2", phone="+998900000003")
        unlinked_nophone = _patient(db_session, unique="auto3", phone=None)
        db_session.commit()

        assert svc._determine_best_channel(linked, db_session) == "telegram"
        assert svc._determine_best_channel(unlinked, db_session) == "pwa"
        assert svc._determine_best_channel(unlinked_nophone, db_session) == "phone"

    def test_unlinked_blocked_or_no_consent_fail_without_dispatch(
        self, db_session, monkeypatch: pytest.MonkeyPatch
    ):
        """Unlinked, bot-blocked and consent-withdrawn patients must fail
        honestly with ZERO dispatch attempts — never a silent crash."""
        from app.services.notifications_pkg import NotificationSenderService

        svc = NotificationSenderService(db=db_session)
        bot = _FakeBot()
        monkeypatch.setattr(svc, "telegram_bot", bot, raising=False)

        unlinked = _patient(db_session, unique="neg1")
        blocked = _patient(db_session, unique="neg2")
        _link(db_session, blocked.id, 777003, blocked=True)
        no_consent = _patient(db_session, unique="neg3")
        _link(db_session, no_consent.id, 777004, notifications=False)
        db_session.commit()

        import asyncio

        for patient in (unlinked, blocked, no_consent):
            result = asyncio.run(
                svc._send_telegram_invitation(patient, _invite_data(), db_session)
            )
            assert result["success"] is False, (patient.id, result)
            assert "привязк" in result["error"] or "Telegram" in result["error"]

        assert bot.calls == []

    def test_keyboard_has_no_unsupported_tel_url(self):
        """NOTIFYTGPHONEURL-BE-001 (audit #3892, group 60): Telegram inline
        keyboards support only https/tg:// URLs. The historical third button
        used a tel: scheme built from a nonexistent settings.CLINIC_PHONE —
        AttributeError killed EVERY invitation before dispatch."""
        from app.services.notifications_pkg import NotificationSenderService

        svc = NotificationSenderService()
        keyboard = svc._create_telegram_keyboard("tok-x")

        assert len(keyboard) == 2
        for row in keyboard:
            for btn in row:
                assert "tel:" not in str(btn.get("url", ""))
        assert any(
            "confirm_visit:tok-x" in btn["callback_data"]
            for row in keyboard for btn in row
        )
        assert any(
            "cancel_visit:tok-x" in btn["callback_data"]
            for row in keyboard for btn in row
        )

    def test_db_required_fails_honestly(self, db_session, monkeypatch: pytest.MonkeyPatch):
        """Without a session the invitation cannot resolve the chat — an
        honest failure, not AttributeError on a nonexistent patient field."""
        from app.services.notifications_pkg import NotificationSenderService

        svc = NotificationSenderService(db=None)
        bot = _FakeBot()
        monkeypatch.setattr(svc, "telegram_bot", bot, raising=False)

        import asyncio

        result = asyncio.run(
            svc._send_telegram_invitation(
                SimpleNamespace(id=1, phone="+998900000004"), _invite_data(), None
            )
        )

        assert result["success"] is False
        assert bot.calls == []
