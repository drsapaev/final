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
2. ``POST /api/v1/telegram/visits/cancel`` exposes the same contract
   token-scoped (the token IS the capability, mirroring confirm).

Run: pytest backend/tests/unit/test_telegram_visit_cancel.py -v
"""
from __future__ import annotations

import pytest

from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
)


def _pending_visit_with_token(db_session, test_visit, token: str):
    test_visit.confirmation_token = token
    test_visit.confirmation_channel = "telegram"
    test_visit.status = "pending_confirmation"
    db_session.commit()
    db_session.refresh(test_visit)
    return test_visit


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

        result = service.cancel_by_telegram(token=visit.confirmation_token)

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
        service.cancel_by_telegram(token=visit.confirmation_token)

        db_session.expire_all()
        try:
            service.cancel_by_telegram(token="unit-cancel-ok-2")
            pytest.fail("Expected VisitConfirmationDomainError for double cancel")
        except VisitConfirmationDomainError as exc:
            assert 400 <= exc.status_code < 500
            # honest either way: the token was invalidated by the first
            # cancel (404 "уже использована") or the visit is canceled
            # (409) — both must be surfaced, never a fake success
            assert "использован" in exc.detail.lower() or "отмен" in exc.detail.lower()

    def test_cancel_after_confirm_is_honest_error(self, db_session, test_visit):
        """Canceling a visit the patient already confirmed must not
        fabricate a cancellation of a confirmed operational visit."""
        visit = _pending_visit_with_token(db_session, test_visit, "unit-cancel-ok-3")
        service = VisitConfirmationService(db_session)
        service.confirm_by_telegram(
            token=visit.confirmation_token,
            telegram_user_id="777",
            source_ip="127.0.0.1",
            user_agent="pytest",
        )

        db_session.expire_all()
        try:
            service.cancel_by_telegram(token="unit-cancel-ok-3")
            pytest.fail("Expected VisitConfirmationDomainError for cancel-after-confirm")
        except VisitConfirmationDomainError as exc:
            assert 400 <= exc.status_code < 500

    def test_unknown_token_is_404(self, db_session, test_visit):
        service = VisitConfirmationService(db_session)
        try:
            service.cancel_by_telegram(token="no-such-token-xyz-1")
            pytest.fail("Expected VisitConfirmationDomainError for unknown token")
        except VisitConfirmationDomainError as exc:
            assert exc.status_code == 404

    def test_cancel_endpoint_contract(self, db_session, client, test_visit):
        """POST /api/v1/telegram/visits/cancel — token-scoped capability,
        mirroring the confirm route; the visit must really be canceled."""
        visit = _pending_visit_with_token(db_session, test_visit, "unit-cancel-api-1")

        resp = client.post(
            "/api/v1/telegram/visits/cancel",
            json={"token": visit.confirmation_token},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "canceled"

        db_session.expire_all()
        db_session.refresh(visit)
        assert visit.status == "canceled"
        assert visit.confirmation_token is None

        resp2 = client.post(
            "/api/v1/telegram/visits/cancel",
            json={"token": "no-such-token-xyz-2"},
        )
        assert resp2.status_code == 404
