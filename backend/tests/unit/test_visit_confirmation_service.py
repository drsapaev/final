from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.online_queue import DailyQueue
from app.models.service import Service
from app.models.telegram_config import TelegramConfig
from app.models.visit import VisitService
from app.services.visit_confirmation_service import (
    TELEGRAM_TICKET_QR_TTL_MINUTES,
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_ticket_start_token,
    consume_telegram_ticket_start_token,
    parse_telegram_ticket_start_token,
)


@pytest.mark.unit
@pytest.mark.confirmation
class TestVisitConfirmationService:
    def test_get_visit_info_expired_token(self, db_session, test_visit):
        test_visit.confirmation_token = f"unit-expired-{test_visit.id}"
        test_visit.confirmation_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        service = VisitConfirmationService(db_session)

        try:
            service.get_visit_info(test_visit.confirmation_token)
            pytest.fail("Expected VisitConfirmationDomainError")
        except VisitConfirmationDomainError as exc:
            assert exc.status_code == 400
            assert "истек" in exc.detail

    def test_confirm_by_pwa_phone_mismatch(self, db_session, test_visit):
        test_visit.confirmation_token = f"unit-pwa-{test_visit.id}"
        test_visit.confirmation_channel = "pwa"
        test_visit.confirmation_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_visit.created_at = datetime.utcnow() - timedelta(minutes=2)
        db_session.commit()

        service = VisitConfirmationService(db_session)

        try:
            service.confirm_by_pwa(
                token=test_visit.confirmation_token,
                patient_phone="+998900000000",
                source_ip="127.0.0.1",
                user_agent="Mozilla/5.0",
            )
            pytest.fail("Expected VisitConfirmationDomainError")
        except VisitConfirmationDomainError as exc:
            assert exc.status_code == 400
            assert "не совпадает" in exc.detail

    def test_confirm_by_telegram_success(self, db_session, test_visit):
        test_visit.confirmation_token = f"unit-tg-{test_visit.id}"
        test_visit.confirmation_channel = "telegram"
        test_visit.confirmation_expires_at = datetime.utcnow() + timedelta(hours=1)
        test_visit.created_at = datetime.utcnow() - timedelta(minutes=2)
        db_session.commit()

        service = VisitConfirmationService(db_session)

        result = service.confirm_by_telegram(
            token=test_visit.confirmation_token,
            telegram_user_id="12345",
            source_ip="127.0.0.1",
            user_agent="Mozilla/5.0",
        )

        db_session.refresh(test_visit)
        assert result["success"] is True
        assert result["visit_id"] == test_visit.id
        assert test_visit.status in {"confirmed", "open"}

    def test_assign_queue_numbers_uses_doctor_id_for_daily_queue(self, db_session, test_visit, test_doctor):
        service = Service(
            code="CARDIO_CONFIRM",
            name="Подтвержденная консультация",
            price=100000,
            duration_minutes=30,
            is_active=True,
            queue_tag="cardiology_common",
        )
        db_session.add(service)
        db_session.commit()
        db_session.refresh(service)

        visit_service = VisitService(
            visit_id=test_visit.id,
            service_id=service.id,
            code=service.code,
            name=service.name,
            qty=1,
            price=service.price,
        )
        db_session.add(visit_service)
        db_session.commit()

        confirmation_service = VisitConfirmationService(db_session)
        queue_numbers, print_tickets = confirmation_service._assign_queue_numbers_on_confirmation(test_visit)
        db_session.flush()

        assert len(queue_numbers) == 1
        assert len(print_tickets) == 1

        daily_queue = (
            db_session.query(DailyQueue)
            .filter(DailyQueue.id == queue_numbers[0]["queue_id"])
            .first()
        )
        assert daily_queue is not None
        assert daily_queue.specialist_id == test_doctor.id
        assert print_tickets[0]["doctor_cabinet"] == test_doctor.cabinet

    def test_ticket_telegram_qr_payload_uses_short_security_ttl(
        self, db_session, test_visit
    ):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                bot_username="clinic_bot",
                active=True,
            )
        )
        db_session.commit()

        confirmation_service = VisitConfirmationService(db_session)
        issued_at = datetime.utcnow()

        payload = confirmation_service._build_ticket_telegram_qr_payload(test_visit)

        assert payload is not None
        assert payload.startswith("https://t.me/clinic_bot?start=")
        assert test_visit.confirmation_token is not None
        assert test_visit.confirmation_expires_at is not None
        assert 5 <= TELEGRAM_TICKET_QR_TTL_MINUTES <= 15
        assert (
            0
            < (test_visit.confirmation_expires_at - issued_at).total_seconds()
            <= (TELEGRAM_TICKET_QR_TTL_MINUTES * 60) + 2
        )

        token = payload.rsplit("start=", 1)[1]
        parsed = parse_telegram_ticket_start_token(token)

        assert parsed is not None
        assert parsed["token_hash"] == test_visit.confirmation_token
        assert (
            abs(
                (
                    parsed["expires_at"] - test_visit.confirmation_expires_at
                ).total_seconds()
            )
            <= 1
        )

    def test_ticket_telegram_qr_rollout_rejects_expired_and_malformed_tokens(
        self,
    ):
        expired_token = build_telegram_ticket_start_token(
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            nonce="expiredcase",
        )
        future_token = build_telegram_ticket_start_token(
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            nonce="futurecase",
        )
        tampered_token = f"{future_token[:-1]}x"

        assert parse_telegram_ticket_start_token(expired_token) is None
        assert parse_telegram_ticket_start_token("") is None
        assert parse_telegram_ticket_start_token("not-a-ticket-token") is None
        assert parse_telegram_ticket_start_token("tq_notbase36_nonce_sig") is None
        assert parse_telegram_ticket_start_token(tampered_token) is None

    def test_ticket_telegram_qr_rollout_rejects_expired_stored_token(
        self, db_session, test_visit
    ):
        token = build_telegram_ticket_start_token(
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            nonce="storeexpired",
        )
        parsed = parse_telegram_ticket_start_token(token)
        assert parsed is not None
        test_visit.confirmation_token = parsed["token_hash"]
        test_visit.confirmation_expires_at = datetime.utcnow() - timedelta(minutes=1)
        db_session.commit()

        consumed = consume_telegram_ticket_start_token(db_session, token)

        assert consumed is None
        db_session.refresh(test_visit)
        assert test_visit.confirmation_token == parsed["token_hash"]

    def test_ticket_telegram_qr_rollout_consumes_once_and_blocks_replay(
        self, db_session, test_visit
    ):
        token = build_telegram_ticket_start_token(
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            nonce="replaycase",
        )
        parsed = parse_telegram_ticket_start_token(token)
        assert parsed is not None
        test_visit.confirmation_token = parsed["token_hash"]
        test_visit.confirmation_expires_at = parsed["expires_at"]
        db_session.commit()

        first = consume_telegram_ticket_start_token(db_session, token)
        db_session.flush()
        second = consume_telegram_ticket_start_token(db_session, token)

        assert first is not None
        assert first.id == test_visit.id
        assert second is None
        db_session.refresh(test_visit)
        assert test_visit.confirmation_token is None
        assert test_visit.confirmation_expires_at is None
