"""Repository helpers for payment webhook API service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.payment_webhook import (
    create_provider,
    delete_provider,
    get_all_providers,
    get_all_transactions,
    get_all_webhooks,
    get_provider_by_code,
    get_provider_by_id,
    get_transaction_by_id,
    get_webhook_by_id,
    update_provider,
)
from app.schemas.payment_webhook import PaymentProviderCreate, PaymentProviderUpdate
from app.services.payment_webhook import payment_webhook_service


class PaymentWebhookApiRepository:
    """Encapsulates data and webhook-service access for API layer."""

    def __init__(self, db: Session):
        self.db = db

    def process_payme_webhook(self, data: dict, signature: str):
        return payment_webhook_service.process_payme_webhook(self.db, data, signature)

    def process_click_webhook(self, data: dict):
        return payment_webhook_service.process_click_webhook(self.db, data)

    def get_webhook_summary(self, provider: str | None):
        return payment_webhook_service.get_webhook_summary(self.db, provider)

    def list_providers(self):
        return get_all_providers(self.db)

    def get_provider_by_code(self, code: str):
        return get_provider_by_code(self.db, code=code)

    def create_provider(self, provider_in: PaymentProviderCreate):
        return create_provider(self.db, provider_in)

    def get_provider(self, provider_id: int):
        return get_provider_by_id(self.db, provider_id)

    def update_provider(self, provider_id: int, provider_in: PaymentProviderUpdate):
        return update_provider(self.db, provider_id, provider_in)

    def delete_provider(self, provider_id: int) -> bool:
        return delete_provider(self.db, provider_id)

    def list_webhooks(self, skip: int, limit: int):
        return get_all_webhooks(self.db, skip=skip, limit=limit)

    def list_transactions(self, skip: int, limit: int):
        return get_all_transactions(self.db, skip=skip, limit=limit)

    def get_transaction(self, transaction_id: int):
        return get_transaction_by_id(self.db, transaction_id)

    def get_webhook(self, webhook_id: int):
        return get_webhook_by_id(self.db, webhook_id)
