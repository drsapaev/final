from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.repositories.visit_payment_integration_repository import (
    VisitPaymentIntegrationRepository,
)


@pytest.mark.unit
class TestVisitPaymentIntegrationRepository:
    def test_update_webhook_status_delegates_to_crud(self, db_session):
        repository = VisitPaymentIntegrationRepository(db_session)
        with patch(
            "app.repositories.visit_payment_integration_repository.update_webhook"
        ) as update_webhook_mock:
            repository.update_webhook_status(webhook_id=11, status="visit_updated")

        update_webhook_mock.assert_called_once()

    def test_update_appointment_status_returns_true_when_updated(self, db_session):
        repository = VisitPaymentIntegrationRepository(db_session)
        with patch(
            "app.repositories.visit_payment_integration_repository.crud_appointment.update_status",
            return_value=object(),
        ) as update_status_mock:
            result = repository.update_appointment_status(
                appointment_id=22,
                new_status="paid",
            )

        assert result is True
        update_status_mock.assert_called_once()

    def test_update_appointment_fields_returns_false_when_missing(self, db_session):
        repository = VisitPaymentIntegrationRepository(db_session)
        with patch(
            "app.repositories.visit_payment_integration_repository.crud_appointment.get",
            return_value=None,
        ):
            result = repository.update_appointment_fields(
                appointment_id=77,
                values={"payment_status": "paid"},
            )

        assert result is False

    def test_create_appointment_delegates_to_crud(self, db_session):
        repository = VisitPaymentIntegrationRepository(db_session)
        appointment_obj = SimpleNamespace(id=99)
        with patch(
            "app.repositories.visit_payment_integration_repository.crud_appointment.create",
            return_value=appointment_obj,
        ) as create_mock:
            result = repository.create_appointment(SimpleNamespace())

        assert result.id == 99
        create_mock.assert_called_once()
