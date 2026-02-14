"""Service layer for payment webhook API endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.repositories.payment_webhook_api_repository import PaymentWebhookApiRepository
from app.schemas.payment_webhook import PaymentProviderCreate, PaymentProviderUpdate


@dataclass
class PaymentWebhookApiDomainError(Exception):
    status_code: int
    detail: str


class PaymentWebhookApiService:
    """Orchestrates payment webhook endpoint logic."""

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self.repository = PaymentWebhookApiRepository(db)

    def process_payme_webhook(self, *, data: dict[str, Any], signature: str) -> dict[str, Any]:
        try:
            success, message, webhook = self.repository.process_payme_webhook(
                data, signature
            )
            return {
                "ok": bool(success),
                "message": message,
                "webhook_id": webhook.id if webhook else None,
            }
        except Exception as exc:
            return {"ok": False, "message": f"Error processing webhook: {exc}"}

    def process_click_webhook(self, *, data: dict[str, Any]) -> dict[str, Any]:
        try:
            success, message, webhook = self.repository.process_click_webhook(data)
            return {
                "ok": bool(success),
                "message": message,
                "webhook_id": webhook.id if webhook else None,
            }
        except Exception as exc:
            return {"ok": False, "message": f"Error processing webhook: {exc}"}

    def list_providers(self):
        return self.repository.list_providers()

    def create_provider(self, provider_in: PaymentProviderCreate):
        existing = self.repository.get_provider_by_code(provider_in.code)
        if existing:
            raise PaymentWebhookApiDomainError(
                status_code=400,
                detail=f"Provider with code '{provider_in.code}' already exists",
            )
        return self.repository.create_provider(provider_in)

    def get_provider(self, provider_id: int):
        provider = self.repository.get_provider(provider_id)
        if not provider:
            raise PaymentWebhookApiDomainError(status_code=404, detail="Provider not found")
        return provider

    def update_provider(self, provider_id: int, provider_in: PaymentProviderUpdate):
        self.get_provider(provider_id)
        return self.repository.update_provider(provider_id, provider_in)

    def delete_provider(self, provider_id: int) -> dict[str, Any]:
        self.get_provider(provider_id)
        success = self.repository.delete_provider(provider_id)
        if not success:
            raise PaymentWebhookApiDomainError(
                status_code=500, detail="Failed to delete provider"
            )
        return {"ok": True, "message": "Provider deleted successfully"}

    def list_webhooks(
        self,
        *,
        skip: int,
        limit: int,
        provider: str | None,
        status: str | None,
    ):
        webhooks = self.repository.list_webhooks(skip=skip, limit=limit)
        if provider:
            webhooks = [w for w in webhooks if w.provider == provider]
        if status:
            webhooks = [w for w in webhooks if w.status == status]
        return webhooks

    def list_transactions(
        self,
        *,
        skip: int,
        limit: int,
        provider: str | None,
        status: str | None,
        visit_id: int | None,
    ):
        transactions = self.repository.list_transactions(skip=skip, limit=limit)
        if provider:
            transactions = [t for t in transactions if t.provider == provider]
        if status:
            transactions = [t for t in transactions if t.status == status]
        if visit_id is not None:
            transactions = [t for t in transactions if t.visit_id == visit_id]
        return transactions

    def get_webhook_summary(self, *, provider: str | None):
        return self.repository.get_webhook_summary(provider)

    def get_transaction(self, transaction_id: int):
        transaction = self.repository.get_transaction(transaction_id)
        if not transaction:
            raise PaymentWebhookApiDomainError(
                status_code=404, detail="Transaction not found"
            )
        return transaction

    def get_webhook(self, webhook_id: int):
        webhook = self.repository.get_webhook(webhook_id)
        if not webhook:
            raise PaymentWebhookApiDomainError(status_code=404, detail="Webhook not found")
        return webhook
