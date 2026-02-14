from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.visit_payment_api_service import (
    VisitPaymentApiDomainError,
    VisitPaymentApiService,
)


@pytest.mark.unit
class TestVisitPaymentApiService:
    def test_get_visit_payment_info_not_found(self, db_session):
        service = VisitPaymentApiService(db_session)
        with patch(
            "app.services.visit_payment_api_service.VisitPaymentIntegrationService.get_visit_payment_info",
            return_value=(False, "Визит 1 не найден", None),
        ):
            with pytest.raises(VisitPaymentApiDomainError) as exc_info:
                service.get_visit_payment_info(visit_id=1)

        assert exc_info.value.status_code == 404
        assert "не найден" in exc_info.value.detail

    def test_update_visit_payment_status_invalid_status(self, db_session):
        service = VisitPaymentApiService(db_session)

        with pytest.raises(VisitPaymentApiDomainError) as exc_info:
            service.update_visit_payment_status(visit_id=1, payment_status="unknown")

        assert exc_info.value.status_code == 400
        assert "Неверный статус платежа" in exc_info.value.detail

    def test_get_visit_payments_summary_aggregates(self, db_session):
        service = VisitPaymentApiService(db_session)

        def _fake_status_call(_db, status, limit=1000, offset=0):  # noqa: ANN001
            if status == "paid":
                return True, "ok", [{"payment_amount": 100}, {"payment_amount": 50}]
            if status == "pending":
                return True, "ok", [{"payment_amount": 20}, {"payment_amount": None}]
            return True, "ok", []

        with patch(
            "app.services.visit_payment_api_service.VisitPaymentIntegrationService.get_visits_by_payment_status",
            side_effect=_fake_status_call,
        ):
            summary = service.get_visit_payments_summary()

        assert summary["success"] is True
        assert summary["summary"]["paid"]["count"] == 2
        assert summary["summary"]["paid"]["total_amount"] == 150.0
        assert summary["summary"]["pending"]["count"] == 2
        assert summary["summary"]["pending"]["total_amount"] == 20.0
        assert summary["total_visits"] == 4
        assert summary["payment_success_rate"] == 50.0

    def test_create_visit_from_payment_failure(self, db_session):
        service = VisitPaymentApiService(db_session)
        with patch(
            "app.services.visit_payment_api_service.VisitPaymentIntegrationService.update_visit_payment_status",
            return_value=(False, "update failed"),
        ):
            with pytest.raises(VisitPaymentApiDomainError) as exc_info:
                service.create_visit_from_payment(
                    visit_id=77,
                    patient_id=10,
                    doctor_id=20,
                    notes=None,
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "update failed"
