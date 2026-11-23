"""TGCONFIRM-BE-003 (audit #3892, group 20) — patient Telegram cancel.

The invitation UI sends ``cancel_visit:<token>``; the bot dispatch routes
it to ``_handle_visit_confirmation(..., confirm=False)``, but that branch
ONLY edited the Telegram message to "Визит отменен": no cancellation
call, no token invalidation, no DB status update. The scheduled visit
stayed ``pending_confirmation`` with a valid token and could later be
confirmed or reminded — while the patient was told it was canceled.

Pinned here (service + endpoint contract):
1. ``VisitConfirmationService.cancel_by_telegram`` persists the
   cancellation through the authorized lifecycle state machine
   (``pending_confirmation -> canceled``), invalidates the token, and
   honestly refuses a second cancel / cancel-after-confirm;
2. The public HTTP endpoint does not treat a caller-supplied Telegram ID as
   proof of identity; a trusted callback invokes the service after binding.

Run: pytest backend/tests/unit/test_telegram_visit_cancel.py -v
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.telegram_config import TelegramUser
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_visit_action_token,
)


@pytest.fixture(autouse=True)
def _future_telegram_start(monkeypatch):
    monkeypatch.setattr("app.tasks.worker._appointment_start_utc", lambda visit: datetime.now(UTC) + timedelta(days=1))


def _pending_visit_with_token(db_session, test_visit, token: str):
    test_visit.confirmation_token = token
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    test_visit.status = "pending_confirmation"
    link = db_session.query(TelegramUser).filter_by(chat_id=777).first()
    if link is None:
        link = TelegramUser(chat_id=777)
        db_session.add(link)
    link.patient_id = test_visit.patient_id
    link.active = True
    link.blocked = False
    link.notifications_enabled = True
    link.appointment_reminders = True
    db_session.commit()
    db_session.refresh(test_visit)
    return test_visit


def _capability(db_session, visit):
    link = db_session.query(TelegramUser).filter_by(chat_id=777).one()
    return build_telegram_visit_action_token(
        visit_id=visit.id, confirmation_token=visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch,
    )


@pytest.mark.unit
@pytest.mark.confirmation
class TestTelegramVisitCancel:
    def test_cancel_persists_canceled_and_invalidates_token(
        self, db_session, test_visit
    ):
        """RED (TGCONFIRM-BE-003): a cancel_visit callback token must
        actually cancel the visit through the lifecycle state machine
        and invalidate the token."""
        visit = _pending_visit_with_token(db_session, test_visit, "unit-cancel-ok-1")
        service = VisitConfirmationService(db_session)

        result = service.cancel_by_telegram(token=_capability(db_session, visit), telegram_user_id="777")

        assert result["success"] is True
        assert result["visit_id"] == visit.id
        db_session.refresh(visit)
        assert visit.status == "canceled"
        assert visit.confirmation_token is None, "token must be invalidated"

    def test_second_cancel_is_honest_error(self, db_session, test_visit):
        """A replayed cancel callback (double-tap, retried delivery) must
        NOT silently succeed again — it must surface the already-canceled
        state honestly."""
        visit = _pending_visit_with_token(db_session, test_visit, "unit-cancel-ok-2")
        service = VisitConfirmationService(db_session)
        capability = _capability(db_session, visit)
        service.cancel_by_telegram(token=capability, telegram_user_id="777")

        db_session.expire_all()
        try:
            service.cancel_by_telegram(token=capability, telegram_user_id="777")
            pytest.fail("Expected VisitConfirmationDomainError for double cancel")
        except VisitConfirmationDomainError as exc:
            assert 400 <= exc.status_code < 500
            # honest either way: the token was invalidated by the first
            # cancel (404 "уже использована") or the visit is canceled
            # (409) — both must be surfaced, never a fake success
            assert "недействитель" in exc.detail.lower() or "использован" in exc.detail.lower()

    def test_cancel_after_confirm_is_honest_error(self, db_session, test_visit):
        """Canceling a visit the patient already confirmed must not
        fabricate a cancellation of a confirmed operational visit."""
        visit = _pending_visit_with_token(db_session, test_visit, "unit-cancel-ok-3")
        service = VisitConfirmationService(db_session)
        capability = _capability(db_session, visit)
        service.confirm_by_telegram(
            token=capability,
            telegram_user_id="777",
            source_ip="127.0.0.1",
            user_agent="pytest",
        )

        db_session.expire_all()
        try:
            service.cancel_by_telegram(token=capability, telegram_user_id="777")
            pytest.fail("Expected VisitConfirmationDomainError for cancel-after-confirm")
        except VisitConfirmationDomainError as exc:
            assert 400 <= exc.status_code < 500

    def test_unknown_token_is_404(self, db_session, test_visit):
        service = VisitConfirmationService(db_session)
        try:
            service.cancel_by_telegram(token="no-such-token-xyz-1", telegram_user_id="777")
            pytest.fail("Expected VisitConfirmationDomainError for unknown token")
        except VisitConfirmationDomainError as exc:
            assert exc.status_code == 404

    def test_cancel_endpoint_contract(self, db_session, client, test_visit):
        """A public caller cannot authenticate a Telegram identity by claiming it."""
        visit = _pending_visit_with_token(db_session, test_visit, "unit-cancel-api-1")
        capability = _capability(db_session, visit)

        resp = client.post(
            "/api/v1/telegram/visits/cancel",
            json={"token": capability, "telegram_user_id": "777"},
        )
        assert resp.status_code == 403, resp.text

        db_session.expire_all()
        db_session.refresh(visit)
        assert visit.status == "pending_confirmation"
        assert visit.confirmation_token == "unit-cancel-api-1"

        # The same visit remains cancellable through the trusted service.
        result = VisitConfirmationService(db_session).cancel_by_telegram(
            token=capability, telegram_user_id="777"
        )
        assert result["success"] is True
        db_session.refresh(visit)
        assert visit.status == "canceled"
        assert visit.confirmation_token is None
