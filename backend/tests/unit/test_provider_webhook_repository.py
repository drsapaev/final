from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.repositories.provider_webhook_repository import ProviderWebhookRepository


@pytest.mark.unit
class TestProviderWebhookRepository:
    def test_get_existing_transaction_returns_match(self, db_session):
        repo = ProviderWebhookRepository(db_session)
        transaction = PaymentTransaction(
            transaction_id="tx-click-1",
            provider="click",
            amount=1500,
            currency="UZS",
            status="completed",
        )
        db_session.add(transaction)
        db_session.commit()

        found = repo.get_existing_transaction(
            transaction_id="tx-click-1",
            provider="click",
        )

        assert found is not None
        assert found.id == transaction.id

    def test_create_webhook_persists_record(self, db_session):
        repo = ProviderWebhookRepository(db_session)

        webhook = repo.create_webhook(
            provider="payme",
            webhook_id="payme_a1b2c3d4",
            transaction_id="order-77",
            amount=3500,
            currency="UZS",
            raw_data={"id": 1},
            signature="sig",
        )
        db_session.commit()

        saved = (
            db_session.query(PaymentWebhook)
            .filter(PaymentWebhook.webhook_id == "payme_a1b2c3d4")
            .first()
        )
        assert webhook.id is not None
        assert saved is not None
        assert saved.transaction_id == "order-77"

    def test_get_payment_by_provider_payment_id_returns_payment(
        self, db_session, test_visit
    ):
        repo = ProviderWebhookRepository(db_session)
        payment = Payment(
            visit_id=test_visit.id,
            amount=Decimal("1000.00"),
            currency="UZS",
            method="online",
            status="pending",
            provider="click",
            provider_payment_id="provider-order-123",
        )
        db_session.add(payment)
        db_session.commit()

        found = repo.get_payment_by_provider_payment_id("provider-order-123")

        assert found is not None
        assert found.id == payment.id

    def test_create_transaction_persists_record(self, db_session):
        repo = ProviderWebhookRepository(db_session)
        webhook = repo.create_webhook(
            provider="kaspi",
            webhook_id="kaspi_deadbeef",
            transaction_id="kaspi-order-1",
            amount=5000,
            currency="KZT",
            raw_data={"status": "ok"},
        )
        repo.create_transaction(
            transaction_id="kaspi-trx-1",
            provider="kaspi",
            amount=5000,
            currency="KZT",
            status="completed",
            payment_id=None,
            webhook_id=webhook.id,
            visit_id=None,
            provider_data={"extra": "data"},
        )
        db_session.commit()

        saved = (
            db_session.query(PaymentTransaction)
            .filter(PaymentTransaction.transaction_id == "kaspi-trx-1")
            .first()
        )
        assert saved is not None
        assert saved.webhook_id == webhook.id
        assert saved.provider_data == {"extra": "data"}
