from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.enums import AppointmentStatus
from app.services.visit_payment_integration import VisitPaymentIntegrationService


class _FakeRow:
    def __init__(self, mapping: dict):
        self._mapping = mapping
        for key, value in mapping.items():
            setattr(self, key, value)


@pytest.mark.unit
class TestVisitPaymentIntegrationService:
    def test_update_visit_payment_status_when_visit_missing(self, db_session):
        repo = SimpleNamespace(get_visit=lambda _visit_id: None)
        with patch(
            "app.services.visit_payment_integration.VisitPaymentIntegrationRepository",
            return_value=repo,
        ):
            success, message = VisitPaymentIntegrationService.update_visit_payment_status(
                db_session, visit_id=10, payment_status="paid"
            )

        assert success is False
        assert message == "Визит 10 не найден"

    def test_get_visit_payment_info_success(self, db_session):
        row = _FakeRow(
            {
                "id": 5,
                "payment_status": "paid",
                "payment_amount": 100_000,
                "payment_currency": "UZS",
                "payment_provider": "click",
                "payment_transaction_id": "tx-1",
                "payment_processed_at": None,
            }
        )
        repo = SimpleNamespace(get_visit_payment_projection=lambda _visit_id: row)
        with patch(
            "app.services.visit_payment_integration.VisitPaymentIntegrationRepository",
            return_value=repo,
        ):
            success, message, payment_info = (
                VisitPaymentIntegrationService.get_visit_payment_info(
                    db_session, visit_id=5
                )
            )

        assert success is True
        assert message == "Информация о платеже получена"
        assert payment_info["visit_id"] == 5
        assert payment_info["payment_status"] == "paid"

    def test_get_visits_by_payment_status_success(self, db_session):
        rows = [
            _FakeRow({"id": 1, "payment_status": "paid"}),
            _FakeRow({"id": 2, "payment_status": "paid"}),
        ]
        repo = SimpleNamespace(
            list_visits_by_payment_status=lambda payment_status, limit, offset: rows
        )
        with patch(
            "app.services.visit_payment_integration.VisitPaymentIntegrationRepository",
            return_value=repo,
        ):
            success, message, visits = (
                VisitPaymentIntegrationService.get_visits_by_payment_status(
                    db_session, payment_status="paid", limit=100, offset=0
                )
            )

        assert success is True
        assert "Найдено 2 визитов" in message
        assert len(visits) == 2
        assert visits[0]["payment_status"] == "paid"

    def test_update_related_appointment_status_success(self, db_session):
        repo = SimpleNamespace(
            find_appointment_by_visit_id=lambda _visit_id: SimpleNamespace(id=123)
        )
        with patch(
            "app.services.visit_payment_integration.VisitPaymentIntegrationRepository",
            return_value=repo,
        ), patch(
            "app.services.visit_payment_integration.crud_appointment.update_status",
            return_value=object(),
        ) as update_status_mock:
            result = VisitPaymentIntegrationService.update_related_appointment_status(
                db_session, visit_id=99, new_status=AppointmentStatus.PAID
            )

        assert result is True
        update_status_mock.assert_called_once()
