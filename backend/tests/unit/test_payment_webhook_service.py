from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.services.payment_webhook import PaymentWebhookService


def _valid_click_webhook_data(merchant_trans_id: str = "888") -> dict[str, str]:
    return {
        "click_trans_id": "click-tx-1",
        "service_id": "svc",
        "merchant_id": "merchant",
        "merchant_trans_id": merchant_trans_id,
        "amount": "750.00",
        "action": "0",
        "error": "",
        "error_note": "",
        "sign_time": "2026-02-14 10:00:00",
        "sign_string": "sig",
    }


@pytest.mark.unit
class TestPaymentWebhookService:
    def test_verify_payme_signature_true_for_valid_signature(self):
        data = {"id": "tx-1", "amount": 1000, "state": 2}
        sign_string = "amount=1000;id=tx-1;state=2"
        secret = "secret-key"
        signature = hmac.new(
            secret.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert (
            PaymentWebhookService.verify_payme_signature(data, signature, secret)
            is True
        )

    def test_verify_click_signature_true_for_valid_signature(self):
        data = {
            "click_trans_id": "1",
            "service_id": "2",
            "merchant_id": "merchant",
            "merchant_trans_id": "3",
            "amount": "400",
            "action": "0",
            "error": "",
            "error_note": "",
            "sign_time": "2026-02-14 10:00:00",
        }
        data["sign_string"] = "5b39d6700b1e202b3cf4091d49f9fb0a"

        assert PaymentWebhookService.verify_click_signature(data, "provider-key") is True

    def test_verify_click_signature_rejects_public_fields_without_secret(self):
        data = {
            "click_trans_id": "1",
            "service_id": "2",
            "merchant_id": "merchant",
            "merchant_trans_id": "3",
            "amount": "400",
            "action": "0",
            "error": "",
            "error_note": "",
            "sign_time": "2026-02-14 10:00:00",
        }
        data["sign_string"] = "17b433fe7039561699fd526dc2986280"

        assert PaymentWebhookService.verify_click_signature(data, "provider-key") is False

    def test_get_webhook_summary_uses_repository_counts(self, db_session):
        repository = SimpleNamespace(
            count_webhooks=lambda: 10,
            get_pending_webhooks=lambda: [1, 2, 3],
            get_failed_webhooks=lambda: [4],
            count_transactions=lambda: 20,
            get_transactions_by_status=lambda status: [1, 2]
            if status == "success"
            else [3],
        )
        with patch(
            "app.services.payment_webhook.PaymentWebhookProcessingRepository",
            return_value=repository,
        ):
            summary = PaymentWebhookService.get_webhook_summary(db_session)

        assert summary["webhooks"]["total"] == 10
        assert summary["webhooks"]["pending"] == 3
        assert summary["webhooks"]["failed"] == 1
        assert summary["transactions"]["total"] == 20
        assert summary["transactions"]["successful"] == 2
        assert summary["transactions"]["failed"] == 1

    @pytest.mark.parametrize(
        ("account", "expected_appointment_id", "expected_visit_id"),
        [
            ({"appointment_id": "123"}, 123, None),
            ({"order_id": "456"}, 456, None),
            ({"visit_id": "789"}, None, 789),
            ({"visit_id": "789", "order_id": "456"}, None, 789),
        ],
    )
    def test_payme_webhook_extracts_dict_account_targets(
        self,
        db_session,
        account,
        expected_appointment_id,
        expected_visit_id,
    ):
        webhook = SimpleNamespace(id=99)
        repository = SimpleNamespace(
            get_provider_by_code=Mock(return_value=SimpleNamespace(secret_key="secret")),
            get_webhook_by_webhook_id=Mock(return_value=None),
            create_webhook=Mock(return_value=webhook),
            create_transaction=Mock(return_value=SimpleNamespace(id=100)),
            update_webhook=Mock(return_value=webhook),
        )
        data = {
            "id": "payme-tx-1",
            "state": 2,
            "amount": 250000,
            "account": account,
        }

        with (
            patch(
                "app.services.payment_webhook.PaymentWebhookProcessingRepository",
                return_value=repository,
            ),
            patch.object(
                PaymentWebhookService, "verify_payme_signature", return_value=True
            ),
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.process_payment_for_appointment",
                return_value=(True, "appointment paid"),
            ) as process_appointment,
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.process_payment_for_existing_visit",
                return_value=(True, "visit paid"),
            ) as process_visit,
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.create_appointment_from_payment",
                return_value=(True, "created", 501),
            ) as create_appointment,
        ):
            success, message, result_webhook = PaymentWebhookService.process_payme_webhook(
                db_session, data, "signature"
            )

        assert success is True
        assert message == "Webhook processed successfully"
        assert result_webhook is webhook
        create_appointment.assert_not_called()

        if expected_appointment_id is not None:
            process_appointment.assert_called_once_with(
                db_session, expected_appointment_id, webhook
            )
            process_visit.assert_not_called()
        else:
            process_visit.assert_called_once_with(
                db_session, expected_visit_id, webhook
            )
            process_appointment.assert_not_called()

    def test_click_webhook_uses_visit_target_when_merchant_id_matches_visit_only(
        self, db_session
    ):
        webhook = SimpleNamespace(id=99)
        repository = SimpleNamespace(
            get_provider_by_code=Mock(
                return_value=SimpleNamespace(secret_key="secret")
            ),
            get_webhook_by_webhook_id=Mock(return_value=None),
            create_webhook=Mock(return_value=webhook),
            create_transaction=Mock(return_value=SimpleNamespace(id=100)),
            update_webhook=Mock(return_value=webhook),
        )

        with (
            patch(
                "app.services.payment_webhook.PaymentWebhookProcessingRepository",
                return_value=repository,
            ),
            patch.object(
                PaymentWebhookService, "verify_click_signature", return_value=True
            ),
            patch.object(
                PaymentWebhookService,
                "_resolve_click_merchant_target",
                return_value=("visit", 888),
            ),
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.process_payment_for_appointment",
                return_value=(True, "appointment paid"),
            ) as process_appointment,
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.process_payment_for_existing_visit",
                return_value=(True, "visit paid"),
            ) as process_visit,
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.create_appointment_from_payment",
                return_value=(True, "created", 501),
            ) as create_appointment,
        ):
            success, message, result_webhook = (
                PaymentWebhookService.process_click_webhook(
                    db_session, _valid_click_webhook_data()
                )
            )

        assert success is True
        assert message == "Webhook processed successfully"
        assert result_webhook is webhook
        process_visit.assert_called_once_with(db_session, 888, webhook)
        process_appointment.assert_not_called()
        create_appointment.assert_not_called()

    def test_click_webhook_fails_ambiguous_merchant_id_without_mutating_record(
        self, db_session
    ):
        webhook = SimpleNamespace(id=99)
        repository = SimpleNamespace(
            get_provider_by_code=Mock(
                return_value=SimpleNamespace(secret_key="secret")
            ),
            get_webhook_by_webhook_id=Mock(return_value=None),
            create_webhook=Mock(return_value=webhook),
            create_transaction=Mock(return_value=SimpleNamespace(id=100)),
            update_webhook=Mock(return_value=webhook),
        )

        with (
            patch(
                "app.services.payment_webhook.PaymentWebhookProcessingRepository",
                return_value=repository,
            ),
            patch.object(
                PaymentWebhookService, "verify_click_signature", return_value=True
            ),
            patch.object(
                PaymentWebhookService,
                "_resolve_click_merchant_target",
                return_value=("ambiguous", 888),
            ),
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.process_payment_for_appointment",
                return_value=(True, "appointment paid"),
            ) as process_appointment,
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.process_payment_for_existing_visit",
                return_value=(True, "visit paid"),
            ) as process_visit,
            patch(
                "app.services.payment_webhook.VisitPaymentIntegrationService.create_appointment_from_payment",
                return_value=(True, "created", 501),
            ) as create_appointment,
        ):
            success, message, result_webhook = (
                PaymentWebhookService.process_click_webhook(
                    db_session, _valid_click_webhook_data()
                )
            )

        assert success is True
        assert message == "Webhook processed successfully"
        assert result_webhook is webhook
        process_appointment.assert_not_called()
        process_visit.assert_not_called()
        create_appointment.assert_not_called()

        _, failed_update = repository.update_webhook.call_args_list[-1].args
        assert failed_update["status"] == "failed"
        expected_error = (
            "Ambiguous Click merchant_trans_id matches both "
            "Appointment.id and Visit.id"
        )
        assert failed_update["error_message"] == expected_error
