"""Repository helpers for payment webhook API service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.payment_webhook import (
    create_provider,
    delete_provider,
    get_all_providers,
    get_provider_by_code,
    get_provider_by_id,
    get_transaction_by_id,
    get_webhook_by_id,
    update_provider,
)
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.models.user import User
from app.models.visit import Visit
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
        webhook_query = self.db.query(PaymentWebhook)
        transaction_query = self.db.query(PaymentTransaction)
        if provider:
            webhook_query = webhook_query.filter(PaymentWebhook.provider == provider)
            transaction_query = transaction_query.filter(
                PaymentTransaction.provider == provider
            )

        return {
            "webhooks": {
                "total": webhook_query.count(),
                "pending": webhook_query.filter(PaymentWebhook.status == "pending").count(),
                "failed": webhook_query.filter(PaymentWebhook.status == "failed").count(),
            },
            "transactions": {
                "total": transaction_query.count(),
                "successful": transaction_query.filter(
                    PaymentTransaction.status == "success"
                ).count(),
                "failed": transaction_query.filter(
                    PaymentTransaction.status == "failed"
                ).count(),
            },
        }

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

    def list_webhooks(
        self,
        *,
        skip: int,
        limit: int,
        provider: str | None = None,
        status: str | None = None,
    ):
        query = self.db.query(PaymentWebhook)
        if provider:
            query = query.filter(PaymentWebhook.provider == provider)
        if status:
            query = query.filter(PaymentWebhook.status == status)
        return query.order_by(PaymentWebhook.id.desc()).offset(skip).limit(limit).all()

    def list_transactions(
        self,
        *,
        skip: int,
        limit: int,
        provider: str | None = None,
        status: str | None = None,
        visit_id: int | None = None,
    ):
        query = self.db.query(PaymentTransaction)
        if provider:
            query = query.filter(PaymentTransaction.provider == provider)
        if status:
            query = query.filter(PaymentTransaction.status == status)
        if visit_id is not None:
            query = query.filter(PaymentTransaction.visit_id == visit_id)
        return query.order_by(PaymentTransaction.id.desc()).offset(skip).limit(limit).all()

    def get_transaction(self, transaction_id: int):
        return get_transaction_by_id(self.db, transaction_id)

    def get_webhook(self, webhook_id: int):
        return get_webhook_by_id(self.db, webhook_id)

    def get_latest_transaction_for_webhook(self, webhook_id: int | str | None):
        return (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.webhook_id == webhook_id)
            .order_by(PaymentTransaction.id.desc())
            .first()
        )

    def get_payment(self, payment_id: int):
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_visit(self, visit_id: int):
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_patient(self, patient_id: int):
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_active_user(self, user_id: int):
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.is_active.is_(True))
            .first()
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
