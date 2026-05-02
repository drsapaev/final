"""Repository helpers for payment webhook processing service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.payment_webhook import (
    count_transactions,
    count_webhooks,
    create_transaction,
    create_webhook,
    get_failed_webhooks,
    get_pending_webhooks,
    get_provider_by_code,
    get_transactions_by_status,
    get_webhook_by_webhook_id,
    update_webhook,
)
from app.schemas.payment_webhook import PaymentTransactionCreate, PaymentWebhookCreate


class PaymentWebhookProcessingRepository:
    """Encapsulates webhook CRUD access for processing service logic."""

    def __init__(self, db: Session):
        self.db = db

    def get_provider_by_code(self, code: str):
        return get_provider_by_code(self.db, code=code)

    def get_webhook_by_webhook_id(self, webhook_id: str):
        return get_webhook_by_webhook_id(self.db, webhook_id=webhook_id)

    def create_webhook(self, webhook_in: PaymentWebhookCreate):
        return create_webhook(self.db, webhook_in)

    def create_transaction(self, transaction_in: PaymentTransactionCreate):
        return create_transaction(self.db, transaction_in)

    def update_webhook(self, webhook_id: int, webhook_in: dict):
        return update_webhook(self.db, webhook_id, webhook_in)

    def count_webhooks(self) -> int:
        return count_webhooks(self.db)

    def get_pending_webhooks(self):
        return get_pending_webhooks(self.db)

    def get_failed_webhooks(self):
        return get_failed_webhooks(self.db)

    def count_transactions(self) -> int:
        return count_transactions(self.db)

    def get_transactions_by_status(self, status: str):
        return get_transactions_by_status(self.db, status=status)
