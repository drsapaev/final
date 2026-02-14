"""Service layer for provider webhook endpoints (click/payme/kaspi)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.api.v1.endpoints.payments import get_payment_manager
from app.db.transactions import transaction as transaction_ctx
from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook

logger = logging.getLogger(__name__)


class ProviderWebhookService:
    """Handles provider webhook processing formerly implemented in controller."""

    def __init__(self, db: Session):
        self.db = db

    def process_click_webhook(self, webhook_data: dict[str, Any]) -> dict[str, Any]:
        """Webhook для Click платежной системы."""
        try:
            logger.info("Click webhook received: %s", webhook_data)

            manager = get_payment_manager()
            signature = webhook_data.get("sign_string")

            if not signature:
                logger.error("Click webhook: Missing signature")
                return {"error": -1, "error_note": "Missing signature"}

            click_provider = manager.get_provider("click")
            if not click_provider:
                logger.error("Click webhook: Provider not configured")
                return {"error": -1, "error_note": "Provider not configured"}

            if not click_provider.validate_webhook_signature(webhook_data, signature):
                logger.error("Click webhook: Invalid signature")
                return {"error": -1, "error_note": "Invalid signature"}

            transaction_id = webhook_data.get("merchant_trans_id", "unknown")
            click_trans_id = webhook_data.get("click_trans_id")

            existing_transaction = (
                self.db.query(PaymentTransaction)
                .filter(
                    PaymentTransaction.transaction_id == click_trans_id,
                    PaymentTransaction.provider == "click",
                )
                .first()
            )

            if existing_transaction:
                logger.info(
                    "Click webhook: Transaction %s already processed (idempotent)",
                    click_trans_id,
                )
                return {
                    "click_trans_id": click_trans_id,
                    "merchant_trans_id": transaction_id,
                    "merchant_prepare_id": existing_transaction.webhook_id or 0,
                    "error": 0,
                    "error_note": "Already processed",
                }

            with transaction_ctx(self.db) as txn:
                webhook_id = f"click_{uuid.uuid4().hex[:8]}"
                webhook = PaymentWebhook(
                    provider="click",
                    webhook_id=webhook_id,
                    transaction_id=transaction_id,
                    status="pending",
                    amount=webhook_data.get("amount", 0),
                    currency="UZS",
                    raw_data=webhook_data,
                    signature=signature,
                )

                txn.add(webhook)
                txn.flush()
                txn.refresh(webhook)

                result = manager.process_webhook("click", webhook_data)

                if result.success:
                    webhook.status = "processed"
                    webhook.processed_at = datetime.utcnow()

                    payment = None
                    if result.payment_id:
                        payment_id_from_order = self._extract_payment_id_from_order(
                            result.payment_id
                        )
                        if payment_id_from_order:
                            payment = (
                                txn.query(Payment)
                                .filter(Payment.id == payment_id_from_order)
                                .first()
                            )

                    if payment:
                        payment.status = self._map_provider_status_to_payment_status(
                            result.status
                        )
                        if payment.status == "paid":
                            payment.paid_at = datetime.utcnow()

                        payment.provider_data = {
                            **(payment.provider_data or {}),
                            **result.provider_data,
                        }

                        webhook.payment_id = payment.id
                        webhook.visit_id = payment.visit_id

                        payment_transaction = PaymentTransaction(
                            transaction_id=webhook_data.get("click_trans_id", webhook_id),
                            provider="click",
                            amount=webhook_data.get("amount", 0),
                            currency="UZS",
                            status=result.status,
                            payment_id=payment.id,
                            webhook_id=webhook.id,
                            visit_id=payment.visit_id,
                            provider_data=result.provider_data,
                        )

                        txn.add(payment_transaction)

                    error = 0 if result.status == "completed" else -1
                    return {
                        "click_trans_id": webhook_data.get("click_trans_id"),
                        "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                        "merchant_prepare_id": webhook.id,
                        "error": error,
                        "error_note": "" if error == 0 else "Payment processing error",
                    }

                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.utcnow()

                return {
                    "click_trans_id": webhook_data.get("click_trans_id"),
                    "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                    "merchant_prepare_id": webhook.id,
                    "error": -1,
                    "error_note": result.error_message or "Processing error",
                }

        except Exception as exc:
            logger.error("Click webhook error: %s", exc)
            return {"error": -1, "error_note": f"Internal server error: {exc}"}

    def process_payme_webhook(
        self, webhook_data: dict[str, Any], auth_header: str | None
    ) -> dict[str, Any]:
        """Webhook для Payme платежной системы (JSON-RPC)."""
        request_id = webhook_data.get("id")
        try:
            logger.info("Payme webhook received: %s", webhook_data)

            method = webhook_data.get("method")
            params = webhook_data.get("params", {})

            manager = get_payment_manager()

            if not auth_header:
                logger.error("Payme webhook: Missing Authorization header")
                return {
                    "error": {"code": -32504, "message": "Missing Authorization header"},
                    "id": request_id,
                }

            payme_provider = manager.get_provider("payme")
            if not payme_provider:
                logger.error("Payme webhook: Provider not configured")
                return {
                    "error": {"code": -32504, "message": "Provider not configured"},
                    "id": request_id,
                }

            if not payme_provider.validate_webhook_signature(
                webhook_data, None, auth_header
            ):
                logger.error("Payme webhook: Invalid Authorization header")
                return {
                    "error": {"code": -32504, "message": "Invalid Authorization"},
                    "id": request_id,
                }

            account = params.get("account", {})
            order_id = account.get("order_id", "unknown")
            payme_transaction_id = params.get("id")

            existing_transaction = None
            if payme_transaction_id:
                existing_transaction = (
                    self.db.query(PaymentTransaction)
                    .filter(
                        PaymentTransaction.transaction_id == payme_transaction_id,
                        PaymentTransaction.provider == "payme",
                    )
                    .first()
                )

            if existing_transaction:
                logger.info(
                    "Payme webhook: Transaction %s already processed (idempotent)",
                    payme_transaction_id,
                )
                if method == "CheckPerformTransaction":
                    return {"result": {"allow": True}, "id": request_id}
                if method == "CreateTransaction":
                    return {
                        "result": {
                            "create_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": existing_transaction.id,
                            "state": 1,
                        },
                        "id": request_id,
                    }
                if method == "PerformTransaction":
                    return {
                        "result": {
                            "perform_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": existing_transaction.id,
                            "state": 2,
                        },
                        "id": request_id,
                    }
                if method == "CancelTransaction":
                    return {
                        "result": {
                            "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": existing_transaction.id,
                            "state": -1,
                        },
                        "id": request_id,
                    }
                return {"result": {}, "id": request_id}

            with transaction_ctx(self.db) as txn:
                webhook_id = f"payme_{uuid.uuid4().hex[:8]}"
                webhook = PaymentWebhook(
                    provider="payme",
                    webhook_id=webhook_id,
                    transaction_id=order_id,
                    status="pending",
                    amount=params.get("amount", 0),
                    currency="UZS",
                    raw_data=webhook_data,
                )

                txn.add(webhook)
                txn.flush()
                txn.refresh(webhook)

                result = manager.process_webhook("payme", webhook_data)

                if result.success:
                    webhook.status = "processed"
                    webhook.processed_at = datetime.utcnow()

                    payment = None
                    if result.payment_id:
                        payment_id_from_order = self._extract_payment_id_from_order(
                            result.payment_id
                        )
                        if payment_id_from_order:
                            payment = (
                                txn.query(Payment)
                                .filter(Payment.id == payment_id_from_order)
                                .first()
                            )

                    if payment:
                        payment.status = self._map_provider_status_to_payment_status(
                            result.status
                        )
                        if payment.status == "paid":
                            payment.paid_at = datetime.utcnow()

                        payment.provider_data = {
                            **(payment.provider_data or {}),
                            **result.provider_data,
                        }

                        webhook.payment_id = payment.id
                        webhook.visit_id = payment.visit_id

                        transaction = PaymentTransaction(
                            transaction_id=params.get("id", webhook_id),
                            provider="payme",
                            amount=params.get("amount", 0),
                            currency="UZS",
                            status=result.status,
                            payment_id=payment.id,
                            webhook_id=webhook.id,
                            visit_id=payment.visit_id,
                            provider_data=result.provider_data,
                        )

                        txn.add(transaction)

                    if method == "CheckPerformTransaction":
                        return {"result": {"allow": True}, "id": request_id}
                    if method == "CreateTransaction":
                        return {
                            "result": {
                                "create_time": int(datetime.utcnow().timestamp() * 1000),
                                "transaction": webhook.id,
                                "state": 1,
                            },
                            "id": request_id,
                        }
                    if method == "PerformTransaction":
                        return {
                            "result": {
                                "perform_time": int(datetime.utcnow().timestamp() * 1000),
                                "transaction": webhook.id,
                                "state": 2,
                            },
                            "id": request_id,
                        }
                    if method == "CancelTransaction":
                        return {
                            "result": {
                                "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                                "transaction": webhook.id,
                                "state": -1,
                            },
                            "id": request_id,
                        }
                    return {"result": {}, "id": request_id}

                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.utcnow()

                return {
                    "error": {
                        "code": -32400,
                        "message": result.error_message or "Processing error",
                    },
                    "id": request_id,
                }

        except Exception as exc:
            logger.error("Payme webhook error: %s", exc)
            return {
                "error": {"code": -32603, "message": f"Internal server error: {exc}"},
                "id": request_id,
            }

    def process_kaspi_webhook(self, webhook_data: dict[str, Any]) -> dict[str, Any]:
        """Webhook для Kaspi Pay платежной системы."""
        try:
            logger.info("Kaspi webhook received: %s", webhook_data)

            webhook_id = f"kaspi_{uuid.uuid4().hex[:8]}"
            webhook = PaymentWebhook(
                provider="kaspi",
                webhook_id=webhook_id,
                transaction_id=webhook_data.get("transaction_id", "unknown"),
                status="pending",
                amount=webhook_data.get("amount", 0),
                currency=webhook_data.get("currency", "KZT"),
                raw_data=webhook_data,
                signature=webhook_data.get("signature"),
            )

            self.db.add(webhook)
            self.db.commit()
            self.db.refresh(webhook)

            manager = get_payment_manager()
            result = manager.process_webhook("kaspi", webhook_data)

            if result.success:
                webhook.status = "processed"
                webhook.processed_at = datetime.utcnow()

                payment = None
                if result.payment_id:
                    payment = (
                        self.db.query(Payment)
                        .filter(Payment.provider_payment_id == result.payment_id)
                        .first()
                    )

                if payment:
                    payment.status = self._map_provider_status_to_payment_status(
                        result.status
                    )
                    if payment.status == "paid":
                        payment.paid_at = datetime.utcnow()

                    payment.provider_data = {
                        **(payment.provider_data or {}),
                        **result.provider_data,
                    }

                    webhook.payment_id = payment.id
                    webhook.visit_id = payment.visit_id

                    transaction = PaymentTransaction(
                        transaction_id=webhook_data.get("transaction_id", webhook_id),
                        provider="kaspi",
                        amount=webhook_data.get("amount", 0),
                        currency=webhook_data.get("currency", "KZT"),
                        status=result.status,
                        payment_id=payment.id,
                        webhook_id=webhook.id,
                        visit_id=payment.visit_id,
                        provider_data=result.provider_data,
                    )

                    self.db.add(transaction)

                self.db.commit()
                return {"status": "success", "message": "Webhook processed successfully"}

            webhook.status = "failed"
            webhook.error_message = result.error_message
            webhook.processed_at = datetime.utcnow()
            self.db.commit()

            return {
                "status": "error",
                "message": result.error_message or "Processing error",
            }
        except Exception as exc:
            logger.error("Kaspi webhook error: %s", exc)
            return {"status": "error", "message": f"Internal server error: {exc}"}

    @staticmethod
    def _extract_payment_id_from_order(order_id: str) -> int | None:
        """Извлекает payment_id из order_id формата clinic_{payment_id}_{timestamp}."""
        try:
            parts = order_id.split("_")
            if len(parts) >= 2 and parts[0] == "clinic":
                return int(parts[1])
        except (ValueError, IndexError):
            pass
        return None

    @staticmethod
    def _map_provider_status_to_payment_status(provider_status: str) -> str:
        """Маппинг статусов провайдера в статусы платежа."""
        status_mapping = {
            "pending": "pending",
            "processing": "processing",
            "completed": "paid",
            "failed": "failed",
            "cancelled": "cancelled",
            "refunded": "refunded",
        }
        return status_mapping.get(provider_status, "failed")
