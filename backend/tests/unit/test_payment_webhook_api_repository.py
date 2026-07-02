from __future__ import annotations

import pytest

from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.repositories.payment_webhook_api_repository import PaymentWebhookApiRepository


@pytest.mark.unit
class TestPaymentWebhookApiRepository:
    def test_list_webhooks_applies_provider_and_status_filters(self, db_session):
        repo = PaymentWebhookApiRepository(db_session)
        db_session.add_all(
            [
                PaymentWebhook(
                    provider="click",
                    webhook_id="wh_click_1",
                    transaction_id="trx_1",
                    status="pending",
                    amount=1000,
                    currency="UZS",
                    raw_data={"p": 1},
                ),
                PaymentWebhook(
                    provider="payme",
                    webhook_id="wh_payme_1",
                    transaction_id="trx_2",
                    status="processed",
                    amount=2000,
                    currency="UZS",
                    raw_data={"p": 2},
                ),
                PaymentWebhook(
                    provider="click",
                    webhook_id="wh_click_2",
                    transaction_id="trx_3",
                    status="processed",
                    amount=3000,
                    currency="UZS",
                    raw_data={"p": 3},
                ),
            ]
        )
        db_session.commit()

        result = repo.list_webhooks(
            skip=0,
            limit=10,
            provider="click",
            status="processed",
        )

        assert len(result) == 1
        assert result[0].webhook_id == "wh_click_2"

    def test_list_transactions_applies_all_filters(self, db_session):
        repo = PaymentWebhookApiRepository(db_session)
        db_session.add_all(
            [
                PaymentTransaction(
                    transaction_id="tx_1",
                    provider="click",
                    amount=1000,
                    currency="UZS",
                    status="success",
                    visit_id=1,
                ),
                PaymentTransaction(
                    transaction_id="tx_2",
                    provider="click",
                    amount=2000,
                    currency="UZS",
                    status="failed",
                    visit_id=1,
                ),
                PaymentTransaction(
                    transaction_id="tx_3",
                    provider="payme",
                    amount=3000,
                    currency="UZS",
                    status="success",
                    visit_id=2,
                ),
            ]
        )
        db_session.commit()

        result = repo.list_transactions(
            skip=0,
            limit=10,
            provider="click",
            status="success",
            visit_id=1,
        )

        assert len(result) == 1
        assert result[0].transaction_id == "tx_1"

    def test_get_webhook_summary_respects_provider_filter(self, db_session):
        repo = PaymentWebhookApiRepository(db_session)
        before = repo.get_webhook_summary(provider="click")
        db_session.add_all(
            [
                PaymentWebhook(
                    provider="click",
                    webhook_id="wh_sum_click_pending",
                    transaction_id="trx_sum_1",
                    status="pending",
                    amount=1000,
                    currency="UZS",
                    raw_data={"p": 1},
                ),
                PaymentWebhook(
                    provider="payme",
                    webhook_id="wh_sum_payme_failed",
                    transaction_id="trx_sum_2",
                    status="failed",
                    amount=1500,
                    currency="UZS",
                    raw_data={"p": 2},
                ),
                PaymentTransaction(
                    transaction_id="tx_sum_click_success",
                    provider="click",
                    amount=1000,
                    currency="UZS",
                    status="success",
                ),
                PaymentTransaction(
                    transaction_id="tx_sum_click_failed",
                    provider="click",
                    amount=1200,
                    currency="UZS",
                    status="failed",
                ),
                PaymentTransaction(
                    transaction_id="tx_sum_payme_success",
                    provider="payme",
                    amount=1300,
                    currency="UZS",
                    status="success",
                ),
            ]
        )
        db_session.commit()

        summary = repo.get_webhook_summary(provider="click")

        assert summary["webhooks"]["total"] == before["webhooks"]["total"] + 1
        assert summary["webhooks"]["pending"] == before["webhooks"]["pending"] + 1
        assert summary["webhooks"]["failed"] == before["webhooks"]["failed"]
        assert summary["transactions"]["total"] == before["transactions"]["total"] + 2
        assert (
            summary["transactions"]["successful"]
            == before["transactions"]["successful"] + 1
        )
        assert summary["transactions"]["failed"] == before["transactions"]["failed"] + 1
