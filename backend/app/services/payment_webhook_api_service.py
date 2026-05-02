"""Service layer for payment webhook API endpoints."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction
from app.models.user import User
from app.models.visit import Visit
from app.repositories.payment_webhook_api_repository import PaymentWebhookApiRepository
from app.schemas.payment_webhook import PaymentProviderCreate, PaymentProviderUpdate
from app.services.notification_platform_service import NotificationPlatformService

logger = logging.getLogger(__name__)


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
            self._emit_legacy_payment_notification(
                webhook=webhook,
                provider="payme",
                success=bool(success),
                message=message,
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
            self._emit_legacy_payment_notification(
                webhook=webhook,
                provider="click",
                success=bool(success),
                message=message,
            )
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
        return self.repository.list_webhooks(
            skip=skip,
            limit=limit,
            provider=provider,
            status=status,
        )

    def list_transactions(
        self,
        *,
        skip: int,
        limit: int,
        provider: str | None,
        status: str | None,
        visit_id: int | None,
    ):
        return self.repository.list_transactions(
            skip=skip,
            limit=limit,
            provider=provider,
            status=status,
            visit_id=visit_id,
        )

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

    def _emit_legacy_payment_notification(
        self,
        *,
        webhook: Any,
        provider: str,
        success: bool,
        message: str,
    ) -> None:
        """Best-effort canonical payment_notification for legacy webhook endpoints."""
        if webhook is None:
            return

        db = self.repository.db
        try:
            payment_status, change_type = self._resolve_legacy_payment_state(
                success=success,
                webhook_status=getattr(webhook, "status", None),
            )
            if not payment_status:
                return

            recipient, resolution = self._resolve_legacy_webhook_recipient(webhook)
            if recipient is None:
                logger.info(
                    "[FIX:NOTIFICATIONS] legacy webhook notification skipped: recipient unresolved",
                    extra={
                        "webhook_id": getattr(webhook, "id", None),
                        "provider": provider,
                        "payment_status": payment_status,
                    },
                )
                return

            title = "Оплата подтверждена" if payment_status == "paid" else "Платеж не выполнен"
            body = (
                "Онлайн-платеж успешно обработан."
                if payment_status == "paid"
                else "Онлайн-платеж не был завершен."
            )
            # Keep canonical inbox payload deterministic for webhook retries.
            # Dynamic provider reasons ("already processed", etc.) can differ
            # across repeated callbacks and would break event-level dedup.

            platform_service = NotificationPlatformService(db)
            event_type = platform_service.normalize_event_type("payment_notification")
            metadata = {
                "provider": provider,
                "payment_status": payment_status,
                "change_type": change_type,
                "webhook_id": getattr(webhook, "id", None),
                "transaction_id": getattr(webhook, "transaction_id", None),
                "visit_id": resolution.get("visit_id"),
                "patient_id": resolution.get("patient_id"),
                "payment_id": resolution.get("payment_id"),
                "legacy_webhook_path": True,
            }
            payload_snapshot = platform_service._build_payload_snapshot(
                title=title,
                message=body,
                deep_link="/patient",
                metadata=metadata,
            )
            role = platform_service.resolve_panel_role_for_user(recipient)
            department_key = platform_service.normalize_department_key(
                getattr(getattr(recipient, "profile", None), "department", None)
            )
            correlation_id = f"legacy_webhook:{provider}:{getattr(webhook, 'id', 'unknown')}"
            event = platform_service._create_or_get_event(
                event_type=event_type,
                source_module="payments_webhook_legacy",
                scope_key=f"user:{recipient.id}",
                title=title,
                message=body,
                severity="warning" if payment_status == "failed" else "info",
                priority="high" if payment_status == "failed" else "normal",
                correlation_id=correlation_id,
                actor_id=None,
                actor_role=None,
                entity_type="payment",
                entity_id=(
                    str(resolution["payment_id"])
                    if resolution.get("payment_id") is not None
                    else str(getattr(webhook, "id", ""))
                ),
                payload_snapshot=payload_snapshot,
                deep_link="/patient",
                expires_at=None,
            )
            delivery = platform_service._create_or_get_delivery(
                event=event,
                recipient_type="user",
                recipient_id=recipient.id,
                role=role,
                department_key=department_key,
                channel=NotificationPlatformService.INBOX_CHANNEL,
                payload_snapshot=payload_snapshot,
            )
            db.commit()

            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if running_loop and not running_loop.is_closed():
                running_loop.create_task(
                    platform_service._broadcast_delivery(recipient.id, delivery)
                )

        except Exception as exc:
            db.rollback()
            logger.warning(
                "[FIX:NOTIFICATIONS] failed legacy webhook canonical emit",
                extra={
                    "webhook_id": getattr(webhook, "id", None),
                    "provider": provider,
                    "error": str(exc),
                },
            )

    @staticmethod
    def _resolve_legacy_payment_state(
        *,
        success: bool,
        webhook_status: str | None,
    ) -> tuple[str | None, str | None]:
        normalized_status = str(webhook_status or "").strip().lower()
        paid_statuses = {"processed", "success", "completed", "visit_updated", "visit_created", "appointment_created"}
        failed_statuses = {"failed", "error"}

        if normalized_status in paid_statuses:
            return "paid", "paid"
        if normalized_status in failed_statuses:
            return "failed", "failed"
        if success:
            return "paid", "paid"
        return "failed", "failed"

    def _resolve_legacy_webhook_recipient(self, webhook: Any) -> tuple[User | None, dict[str, int | None]]:
        db = self.repository.db
        patient_id = self._safe_int(getattr(webhook, "patient_id", None))
        visit_id = self._safe_int(getattr(webhook, "visit_id", None))
        payment_id = None

        transaction = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.webhook_id == getattr(webhook, "id", None))
            .order_by(PaymentTransaction.id.desc())
            .first()
        )
        if transaction:
            payment_id = self._safe_int(getattr(transaction, "payment_id", None))
            if visit_id is None:
                visit_id = self._safe_int(getattr(transaction, "visit_id", None))

        if payment_id is not None:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if payment and visit_id is None:
                visit_id = self._safe_int(getattr(payment, "visit_id", None))

        if visit_id is not None and patient_id is None:
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if visit:
                patient_id = self._safe_int(getattr(visit, "patient_id", None))

        if patient_id is None:
            raw_data = getattr(webhook, "raw_data", None)
            patient_id = self._extract_patient_id_from_raw_data(raw_data)

        if patient_id is None:
            return None, {"patient_id": None, "visit_id": visit_id, "payment_id": payment_id}

        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient or not patient.user_id:
            return None, {"patient_id": patient_id, "visit_id": visit_id, "payment_id": payment_id}

        recipient = (
            db.query(User)
            .filter(User.id == patient.user_id, User.is_active.is_(True))
            .first()
        )
        return recipient, {"patient_id": patient_id, "visit_id": visit_id, "payment_id": payment_id}

    @staticmethod
    def _extract_patient_id_from_raw_data(raw_data: Any) -> int | None:
        if not isinstance(raw_data, dict):
            return None
        for key in ("patient_id", "patientId", "client_id", "clientId"):
            candidate = PaymentWebhookApiService._safe_int(raw_data.get(key))
            if candidate is not None:
                return candidate

        params = raw_data.get("params")
        if isinstance(params, dict):
            account = params.get("account")
            if isinstance(account, dict):
                for key in ("patient_id", "patientId", "client_id", "clientId"):
                    candidate = PaymentWebhookApiService._safe_int(account.get(key))
                    if candidate is not None:
                        return candidate
        return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
