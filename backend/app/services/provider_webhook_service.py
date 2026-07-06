"""Service layer for provider webhook endpoints (click/payme/kaspi)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.db.transactions import transaction as transaction_ctx
from app.repositories.provider_webhook_repository import ProviderWebhookRepository
from app.services.payment_provider_manager_factory import get_payment_manager

logger = logging.getLogger(__name__)


class ProviderWebhookService:
    """Handles provider webhook processing formerly implemented in controller."""

    def __init__(
        self,
        db: Session,
        repository: ProviderWebhookRepository | None = None,
    ):
        self.db = db
        self.repository = repository or ProviderWebhookRepository(db)

    @staticmethod
    def _decimal_amount(value: Any) -> Decimal | None:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @classmethod
    def _amounts_match(cls, expected: Any, actual: Any) -> bool:
        expected_amount = cls._decimal_amount(expected)
        actual_amount = cls._decimal_amount(actual)
        return (
            expected_amount is not None
            and actual_amount is not None
            and expected_amount == actual_amount
        )

    def _result_amount_matches_payment(self, payment: Any, result: Any) -> bool:
        provider_amount = (getattr(result, "provider_data", None) or {}).get("amount")
        return self._amounts_match(getattr(payment, "amount", None), provider_amount)

    def _payme_params_amount_matches_payment(
        self,
        payment: Any,
        params: dict[str, Any],
        transaction: Any | None = None,
    ) -> bool:
        raw_amount = params.get("amount")
        if raw_amount is not None:
            provider_amount = self._decimal_amount(raw_amount)
            if provider_amount is None:
                return False
            provider_amount = provider_amount / Decimal("100")
        else:
            provider_amount = self._decimal_amount(
                (getattr(transaction, "provider_data", None) or {}).get("amount")
            )
            if provider_amount is None:
                return False
        return self._amounts_match(
            getattr(payment, "amount", None),
            provider_amount,
        )

    def process_click_webhook(self, webhook_data: dict[str, Any]) -> dict[str, Any]:
        """Webhook для Click платежной системы."""
        try:
            # PAY-REAUDIT-28 P1-2: PII-safe logging — только идентификаторы,
            # не весь payload (webhook_data содержит order_id с payment_id).
            logger.info(
                "Click webhook received",
                extra={
                    "click_trans_id": webhook_data.get("click_trans_id"),
                    "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                    "action": webhook_data.get("action"),
                },
            )

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

            existing_transaction = self.repository.get_existing_transaction(
                transaction_id=click_trans_id,
                provider="click",
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
                    "payment_id": getattr(existing_transaction, "payment_id", None),
                    "payment_status": None,
                    "payment_provider": "click",
                }

            with transaction_ctx(self.db):
                webhook_id = f"click_{uuid.uuid4().hex[:8]}"
                webhook = self.repository.create_webhook(
                    provider="click",
                    webhook_id=webhook_id,
                    transaction_id=transaction_id,
                    amount=webhook_data.get("amount", 0),
                    currency="UZS",
                    raw_data=webhook_data,
                    signature=signature,
                )

                result = manager.process_webhook("click", webhook_data)

                if result.success:
                    webhook.status = "processed"
                    webhook.processed_at = datetime.utcnow()

                    payment = None
                    mapped_status = None
                    if result.payment_id:
                        payment_id_from_order = self._extract_payment_id_from_order(
                            result.payment_id
                        )
                        if payment_id_from_order:
                            payment = self.repository.get_payment_by_id(
                                payment_id_from_order
                            )

                    if payment:
                        if not self._result_amount_matches_payment(payment, result):
                            webhook.status = "failed"
                            webhook.error_message = "provider_amount_mismatch"
                            return {
                                "click_trans_id": webhook_data.get("click_trans_id"),
                                "merchant_trans_id": webhook_data.get(
                                    "merchant_trans_id"
                                ),
                                "merchant_prepare_id": webhook.id,
                                "error": -1,
                                "error_note": "Payment amount mismatch",
                                "payment_id": payment.id,
                                "payment_status": None,
                                "payment_provider": "click",
                            }
                        mapped_status = self._map_provider_status_to_payment_status(result.status)
                        payment.status = mapped_status
                        if payment.status == "paid":
                            payment.paid_at = datetime.utcnow()

                        payment.provider_data = {
                            **(payment.provider_data or {}),
                            **result.provider_data,
                        }

                        webhook.payment_id = payment.id
                        webhook.visit_id = payment.visit_id

                        self.repository.create_transaction(
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

                    error = 0 if result.status == "completed" else -1
                    return {
                        "click_trans_id": webhook_data.get("click_trans_id"),
                        "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                        "merchant_prepare_id": webhook.id,
                        "error": error,
                        "error_note": "" if error == 0 else "Payment processing error",
                        "payment_id": payment.id if payment else None,
                        "payment_status": mapped_status,
                        "payment_provider": "click",
                    }

                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.utcnow()

                failed_payment = None
                if result.payment_id:
                    payment_id_from_order = self._extract_payment_id_from_order(result.payment_id)
                    if payment_id_from_order:
                        failed_payment = self.repository.get_payment_by_id(payment_id_from_order)
                if failed_payment:
                    failed_payment.status = "failed"
                    failed_payment.provider_data = {
                        **(failed_payment.provider_data or {}),
                        "webhook_error": result.error_message,
                    }

                return {
                    "click_trans_id": webhook_data.get("click_trans_id"),
                    "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                    "merchant_prepare_id": webhook.id,
                    "error": -1,
                    "error_note": result.error_message or "Processing error",
                    "payment_id": failed_payment.id if failed_payment else None,
                    "payment_status": "failed" if failed_payment else None,
                    "payment_provider": "click",
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
            # PAY-REAUDIT-28 P1-2: PII-safe logging
            logger.info(
                "Payme webhook received",
                extra={
                    "method": webhook_data.get("method"),
                    "rpc_id": (webhook_data.get("id") if isinstance(webhook_data, dict) else None),
                },
            )

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
                existing_transaction = self.repository.get_existing_transaction(
                    transaction_id=payme_transaction_id,
                    provider="payme",
                )

            if existing_transaction:
                logger.info(
                    "Payme webhook: Transaction %s already processed (idempotent)",
                    payme_transaction_id,
                )
                if method == "CheckPerformTransaction":
                    return {"result": {"allow": True}, "id": request_id}
                payment_id = getattr(existing_transaction, "payment_id", None)
                payment_status = None
                if method in {"PerformTransaction", "CancelTransaction"}:
                    with transaction_ctx(self.db):
                        payment_status = self._apply_existing_payme_transaction_state(
                            existing_transaction,
                            method=method,
                            params=params,
                        )
                        payment_id = getattr(existing_transaction, "payment_id", None)
                if payment_status == "amount_mismatch":
                    return {
                        "error": {
                            "code": -31001,
                            "message": "Payment amount mismatch",
                        },
                        "id": request_id,
                        "payment_id": payment_id,
                        "payment_status": None,
                        "payment_provider": "payme",
                    }
                if method == "CreateTransaction":
                    return {
                        "result": {
                            "create_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": existing_transaction.id,
                            "state": 1,
                        },
                        "id": request_id,
                        "payment_id": payment_id,
                        "payment_status": payment_status,
                        "payment_provider": "payme",
                    }
                if method == "PerformTransaction":
                    return {
                        "result": {
                            "perform_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": existing_transaction.id,
                            "state": 2,
                        },
                        "id": request_id,
                        "payment_id": payment_id,
                        "payment_status": payment_status,
                        "payment_provider": "payme",
                    }
                if method == "CancelTransaction":
                    return {
                        "result": {
                            "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": existing_transaction.id,
                            "state": -1,
                        },
                        "id": request_id,
                        "payment_id": payment_id,
                        "payment_status": payment_status,
                        "payment_provider": "payme",
                    }
                return {
                    "result": {},
                    "id": request_id,
                    "payment_id": payment_id,
                    "payment_status": payment_status,
                    "payment_provider": "payme",
                }

            with transaction_ctx(self.db):
                webhook_id = f"payme_{uuid.uuid4().hex[:8]}"
                webhook = self.repository.create_webhook(
                    provider="payme",
                    webhook_id=webhook_id,
                    transaction_id=order_id,
                    amount=params.get("amount", 0),
                    currency="UZS",
                    raw_data=webhook_data,
                )

                result = manager.process_webhook("payme", webhook_data)

                if result.success:
                    webhook.status = "processed"
                    webhook.processed_at = datetime.utcnow()

                    payment = None
                    mapped_status = None
                    if result.payment_id:
                        payment_id_from_order = self._extract_payment_id_from_order(
                            result.payment_id
                        )
                        if payment_id_from_order:
                            payment = self.repository.get_payment_by_id(
                                payment_id_from_order
                            )

                    if payment:
                        if not self._result_amount_matches_payment(payment, result):
                            webhook.status = "failed"
                            webhook.error_message = "provider_amount_mismatch"
                            return {
                                "error": {
                                    "code": -31001,
                                    "message": "Payment amount mismatch",
                                },
                                "id": request_id,
                                "payment_id": payment.id,
                                "payment_status": None,
                                "payment_provider": "payme",
                            }
                        mapped_status = self._map_provider_status_to_payment_status(result.status)
                        payment.status = mapped_status
                        if payment.status == "paid":
                            payment.paid_at = datetime.utcnow()

                        payment.provider_data = {
                            **(payment.provider_data or {}),
                            **result.provider_data,
                        }

                        webhook.payment_id = payment.id
                        webhook.visit_id = payment.visit_id

                        self.repository.create_transaction(
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

                    if method == "CheckPerformTransaction":
                        return {
                            "result": {"allow": True},
                            "id": request_id,
                            "payment_id": payment.id if payment else None,
                            "payment_status": mapped_status,
                            "payment_provider": "payme",
                        }
                    if method == "CreateTransaction":
                        return {
                            "result": {
                                "create_time": int(datetime.utcnow().timestamp() * 1000),
                                "transaction": webhook.id,
                                "state": 1,
                            },
                            "id": request_id,
                            "payment_id": payment.id if payment else None,
                            "payment_status": mapped_status,
                            "payment_provider": "payme",
                        }
                    if method == "PerformTransaction":
                        return {
                            "result": {
                                "perform_time": int(datetime.utcnow().timestamp() * 1000),
                                "transaction": webhook.id,
                                "state": 2,
                            },
                            "id": request_id,
                            "payment_id": payment.id if payment else None,
                            "payment_status": mapped_status,
                            "payment_provider": "payme",
                        }
                    if method == "CancelTransaction":
                        return {
                            "result": {
                                "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                                "transaction": webhook.id,
                                "state": -1,
                            },
                            "id": request_id,
                            "payment_id": payment.id if payment else None,
                            "payment_status": mapped_status,
                            "payment_provider": "payme",
                        }
                    return {
                        "result": {},
                        "id": request_id,
                        "payment_id": payment.id if payment else None,
                        "payment_status": mapped_status,
                        "payment_provider": "payme",
                    }

                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.utcnow()

                failed_payment = None
                if result.payment_id:
                    payment_id_from_order = self._extract_payment_id_from_order(result.payment_id)
                    if payment_id_from_order:
                        failed_payment = self.repository.get_payment_by_id(payment_id_from_order)
                if failed_payment:
                    failed_payment.status = "failed"
                    failed_payment.provider_data = {
                        **(failed_payment.provider_data or {}),
                        "webhook_error": result.error_message,
                    }

                return {
                    "error": {
                        "code": -32400,
                        "message": result.error_message or "Processing error",
                    },
                    "id": request_id,
                    "payment_id": failed_payment.id if failed_payment else None,
                    "payment_status": "failed" if failed_payment else None,
                    "payment_provider": "payme",
                }

        except Exception as exc:
            logger.error("Payme webhook error: %s", exc)
            return {
                "error": {"code": -32603, "message": f"Internal server error: {exc}"},
                "id": request_id,
            }

    def _apply_existing_payme_transaction_state(
        self,
        transaction: Any,
        *,
        method: str,
        params: dict[str, Any],
    ) -> str | None:
        if method == "PerformTransaction":
            provider_status = "completed"
        elif method == "CancelTransaction":
            provider_status = "cancelled" if params.get("reason") == 1 else "refunded"
        else:
            return None

        payment_status = self._map_provider_status_to_payment_status(provider_status)
        payment_id = getattr(transaction, "payment_id", None)
        if payment_id:
            payment = self.repository.get_payment_by_id(payment_id)
            if payment:
                if not self._payme_params_amount_matches_payment(
                    payment,
                    params,
                    transaction,
                ):
                    return "amount_mismatch"

        transaction.status = provider_status
        transaction.provider_data = {
            **(transaction.provider_data or {}),
            "method": method,
            "transaction_id": params.get("id"),
            "params": params,
        }

        if payment_id:
            payment = self.repository.get_payment_by_id(payment_id)
            if payment:
                payment.status = payment_status
                if payment_status == "paid" and not payment.paid_at:
                    payment.paid_at = datetime.utcnow()
                payment.provider_data = {
                    **(payment.provider_data or {}),
                    **(transaction.provider_data or {}),
                }
        return payment_status

    def process_kaspi_webhook(self, webhook_data: dict[str, Any]) -> dict[str, Any]:
        """Webhook для Kaspi Pay платежной системы.

        PAY-REAUDIT-28 P0-5: добавлена идемпотентность (проверка existing
        transaction) и атомарность (transaction_ctx вместо нескольких
        raw db.commit()). Раньше повторный webhook создавал дубликаты
        транзакций и переобрабатывал платёж.
        """
        try:
            # PII-safe logging: только идентификаторы, не весь payload.
            logger.info(
                "Kaspi webhook received",
                extra={
                    "transaction_id": webhook_data.get("transaction_id"),
                    "merchant_id": webhook_data.get("merchant_id"),
                },
            )

            manager = get_payment_manager()
            signature = webhook_data.get("signature")

            if not signature:
                logger.error("Kaspi webhook: Missing signature")
                return {"status": "error", "message": "Missing signature"}

            kaspi_provider = manager.get_provider("kaspi")
            if not kaspi_provider:
                logger.error("Kaspi webhook: Provider not configured")
                return {"status": "error", "message": "Provider not configured"}

            if not kaspi_provider.validate_webhook_signature(webhook_data, signature):
                logger.error("Kaspi webhook: Invalid signature")
                return {"status": "error", "message": "Invalid signature"}

            transaction_id = webhook_data.get("transaction_id", "unknown")

            # IDEMPOTENCY: проверяем, не был ли этот webhook уже обработан.
            existing_transaction = self.repository.get_existing_transaction(
                transaction_id=transaction_id,
                provider="kaspi",
            )
            if existing_transaction:
                logger.info(
                    "Kaspi webhook: Transaction %s already processed (idempotent)",
                    transaction_id,
                )
                return {
                    "status": "success",
                    "message": "Already processed",
                    "payment_id": getattr(existing_transaction, "payment_id", None),
                    "payment_status": None,
                    "payment_provider": "kaspi",
                }

            # ATOMIC: всё в одной транзакции.
            with transaction_ctx(self.db):
                webhook_id = f"kaspi_{uuid.uuid4().hex[:8]}"
                webhook = self.repository.create_webhook(
                    provider="kaspi",
                    webhook_id=webhook_id,
                    transaction_id=transaction_id,
                    amount=webhook_data.get("amount", 0),
                    currency=webhook_data.get("currency", "KZT"),
                    raw_data=webhook_data,
                    signature=signature,
                )

                result = manager.process_webhook("kaspi", webhook_data)

                if result.success:
                    webhook.status = "processed"
                    webhook.processed_at = datetime.utcnow()

                    payment = None
                    mapped_status = None
                    if result.payment_id:
                        payment = self.repository.get_payment_by_provider_payment_id(
                            result.payment_id
                        )

                    if payment:
                        if not self._result_amount_matches_payment(payment, result):
                            webhook.status = "failed"
                            webhook.error_message = "provider_amount_mismatch"
                            return {
                                "status": "error",
                                "message": "Payment amount mismatch",
                                "payment_id": payment.id,
                                "payment_status": None,
                                "payment_provider": "kaspi",
                            }
                        mapped_status = self._map_provider_status_to_payment_status(result.status)
                        payment.status = mapped_status
                        if payment.status == "paid":
                            payment.paid_at = datetime.utcnow()

                        payment.provider_data = {
                            **(payment.provider_data or {}),
                            **result.provider_data,
                        }

                        webhook.payment_id = payment.id
                        webhook.visit_id = payment.visit_id

                        self.repository.create_transaction(
                            transaction_id=transaction_id,
                            provider="kaspi",
                            amount=webhook_data.get("amount", 0),
                            currency=webhook_data.get("currency", "KZT"),
                            status=result.status,
                            payment_id=payment.id,
                            webhook_id=webhook.id,
                            visit_id=payment.visit_id,
                            provider_data=result.provider_data,
                        )

                    return {
                        "status": "success",
                        "message": "Webhook processed successfully",
                        "payment_id": payment.id if payment else None,
                        "payment_status": mapped_status,
                        "payment_provider": "kaspi",
                    }

                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.utcnow()

                failed_payment = None
                if result.payment_id:
                    failed_payment = self.repository.get_payment_by_provider_payment_id(result.payment_id)
                if failed_payment:
                    failed_payment.status = "failed"
                    failed_payment.provider_data = {
                        **(failed_payment.provider_data or {}),
                        "webhook_error": result.error_message,
                    }

                return {
                    "status": "error",
                    "message": result.error_message or "Processing error",
                    "payment_id": failed_payment.id if failed_payment else None,
                    "payment_status": "failed" if failed_payment else None,
                    "payment_provider": "kaspi",
                }
        except Exception as exc:
            logger.exception("Kaspi webhook error")
            return {"status": "error", "message": "Internal server error"}

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
