from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.online_queue import DailyQueue
from app.models.service import Service
from app.models.visit import VisitService
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
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
