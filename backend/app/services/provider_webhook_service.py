"""Service layer for provider webhook endpoints (click/payme/kaspi)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.db.transactions import transaction as transaction_ctx
from app.models.audit import AuditLog
from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.repositories.provider_webhook_repository import ProviderWebhookRepository
from app.services.payment_provider_manager_factory import get_payment_manager
from app.services.payment_state_checks import (
    can_transition_payment_status,
    can_transition_transaction_status,
)

logger = logging.getLogger(__name__)

# Secondary audit event for operators reviewing a successful Payme cancellation.
PAYME_TX_PRE_CANCEL_STATE_ACTION = "PAYME_TX_PRE_CANCEL_STATE"
_PAYME_METHODS = frozenset({
    "CheckPerformTransaction",
    "CreateTransaction",
    "PerformTransaction",
    "CancelTransaction",
    "CheckTransaction",
    "GetStatement",
})


class ProviderWebhookService:
    """Handles provider webhook processing formerly implemented in controller."""

    def __init__(
        self,
        db: Session,
        repository: ProviderWebhookRepository | None = None,
    ):
        self.db = db
        self.repository = repository or ProviderWebhookRepository(db)

    def _update_payment_status(self, payment_id: int, new_status: str, commit: bool = False):
        """Update payment status via canonical BillingService.

        Issue #06 Phase 4b B2: centralized through this method so that
        unit tests can mock it (instead of creating inline BillingService
        instances that can't be patched).

        P2 fix (Codex): if the payment is already in a terminal state and
        the new status is 'failed' (late provider error callback), skip the
        transition — preserve terminal payment status. The webhook failure
        record is still committed by the caller.
        """
        from app.services.billing_service import BillingService
        from app.services.payment_state_checks import is_terminal_payment

        # P2 fix: check current status before attempting transition.
        # If payment is already terminal (refunded/cancelled/void),
        # a late 'failed' callback should NOT change the status.
        # Note: "paid" is NOT terminal — it has outgoing transitions
        # to refunded/void/cancelled (see ALLOWED_PAYMENT_TRANSITIONS
        # in payment_state_checks.py, the authoritative SSOT).
        payment = self.repository.get_payment_by_id(payment_id) if hasattr(self.repository, 'get_payment_by_id') else None
        if payment and is_terminal_payment(payment.status) and new_status == "failed":
            logger.warning(
                "webhook.skip_failed_transition payment_id=%s current=%s is terminal — "
                "preserving terminal status, webhook failure still recorded",
                payment_id, payment.status,
            )
            return payment

        return BillingService(self.db).update_payment_status(
            payment_id=payment_id,
            new_status=new_status,
            commit=commit,
        )

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

    @staticmethod
    def _click_payment_matches_order(payment: Any, order_id: Any) -> bool:
        return (
            payment is not None
            and isinstance(order_id, str)
            and payment.provider == "click"
            and payment.currency == "UZS"
            and payment.provider_payment_id == order_id
        )

    def _click_replay_response(
        self,
        transaction: PaymentTransaction,
        payment: Payment | None,
        webhook_data: dict[str, Any],
    ) -> dict[str, Any]:
        order_id = webhook_data.get("merchant_trans_id", "unknown")
        if not self._click_payment_matches_order(payment, order_id):
            return {"error": -1, "error_note": "Payment order mismatch"}
        if not self._amounts_match(transaction.amount, webhook_data.get("amount")):
            return {"error": -1, "error_note": "Payment amount mismatch"}
        recorded_fields = getattr(transaction, "provider_data", None) or {}
        if any(
            key in recorded_fields and recorded_fields[key] != webhook_data.get(key)
            for key in ("action", "error")
        ):
            return {"error": -1, "error_note": "Payment phase mismatch"}
        logger.info("Click webhook: Transaction already processed (idempotent)")
        error = 0 if transaction.status == "completed" else -1
        return {
            "click_trans_id": webhook_data.get("click_trans_id"),
            "merchant_trans_id": order_id,
            "merchant_prepare_id": transaction.webhook_id or 0,
            "error": error,
            "error_note": "Already processed" if error == 0 else "Payment processing error",
            "payment_id": transaction.payment_id,
            "payment_status": None,
            "payment_provider": "click",
        }

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
        """Acknowledge recorded Click results and hold new legacy callbacks."""
        try:
            logger.info("Click webhook received")

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
                payment_id = existing_transaction.payment_id
                payment = (
                    self.repository.get_payment_by_id(payment_id)
                    if payment_id is not None
                    else None
                )
                return self._click_replay_response(existing_transaction, payment, webhook_data)

            # The legacy signature does not authenticate merchant_trans_id.
            # Record the receipt independently of any payment or settlement.
            webhook = self.repository.create_webhook(
                provider="click",
                webhook_id=f"click_{uuid.uuid4().hex[:8]}",
                transaction_id=transaction_id,
                amount=webhook_data.get("amount", 0),
                currency="UZS",
                raw_data=webhook_data,
                signature=signature,
                status="failed",
            )
            webhook.processed_at = datetime.now(UTC)
            webhook.error_message = "provider_reconciliation_required"
            self.db.commit()
            return {"error": -1, "error_note": "Payment reconciliation required"}

        except Exception as exc:
            self.db.rollback()
            logger.error("Click webhook error type=%s", type(exc).__name__)
            return {"error": -1, "error_note": "Internal server error"}

    @staticmethod
    def _payme_order_unavailable(request_id: Any) -> dict[str, Any]:
        return {
            "error": {
                "code": -31050,
                "message": {
                    "ru": "Заказ недоступен",
                    "uz": "Buyurtma mavjud emas",
                    "en": "Order unavailable",
                },
                "data": "order_id",
            },
            "id": request_id,
        }

    @staticmethod
    def _payme_transaction_unavailable(request_id: Any) -> dict[str, Any]:
        return {"error": {"code": -31003, "message": "Transaction not found"}, "id": request_id}

    @staticmethod
    def _payme_amount_mismatch(request_id: Any, payment_id: int) -> dict[str, Any]:
        return {
            "error": {"code": -31001, "message": "Payment amount mismatch"},
            "id": request_id,
            "payment_id": payment_id,
            "payment_status": None,
            "payment_provider": "payme",
        }

    @staticmethod
    def _payme_timestamp(value: datetime) -> int:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return int(value.timestamp() * 1000)

    @classmethod
    def _payme_create_response(
        cls, receipt: PaymentWebhook, *, request_id: Any, payment_id: int, payment_status: str | None = None
    ) -> dict[str, Any]:
        return {
            "result": {
                "create_time": cls._payme_timestamp(receipt.created_at),
                "transaction": receipt.id,
                "state": 1,
            },
            "id": request_id,
            "payment_id": payment_id,
            "payment_status": payment_status,
            "payment_provider": "payme",
        }

    def _replay_payme_creation(
        self,
        transaction: PaymentTransaction | None,
        *,
        payment: Payment,
        params: dict[str, Any],
        request_id: Any,
    ) -> dict[str, Any]:
        if (
            transaction is None
            or transaction.payment_id != payment.id
            or transaction.visit_id not in (None, payment.visit_id)
        ):
            return self._payme_transaction_unavailable(request_id)
        if not self._payme_params_amount_matches_payment(payment, params, transaction):
            return self._payme_amount_mismatch(request_id, payment.id)

        receipt = self._get_payme_creation_receipt(transaction, payment)
        if receipt is not None:
            return self._payme_create_response(
                receipt, request_id=request_id, payment_id=payment.id
            )

        return {
            "error": {"code": -32400, "message": "Creation receipt requires reconciliation"},
            "id": request_id,
        }

    def _get_payme_creation_receipt(
        self, transaction: PaymentTransaction, payment: Payment
    ) -> PaymentWebhook | None:
        if transaction.webhook_id is None or not payment.provider_payment_id:
            return None
        receipt = self.repository.get_processed_webhook(
            webhook_id=transaction.webhook_id,
            provider="payme",
            transaction_id=payment.provider_payment_id,
        )
        if receipt is not None and self._payme_creation_params(receipt, transaction, payment) is not None:
            return receipt
        return None

    @staticmethod
    def _payme_creation_params(
        receipt: PaymentWebhook, transaction: PaymentTransaction, payment: Payment
    ) -> dict[str, Any] | None:
        if not isinstance(receipt.raw_data, dict):
            return None
        original_params = receipt.raw_data.get("params")
        account = original_params.get("account") if isinstance(original_params, dict) else None
        if (
            receipt.raw_data.get("method") == "CreateTransaction"
            and isinstance(account, dict)
            and account.get("order_id") == payment.provider_payment_id
            and original_params.get("id") == transaction.transaction_id
            and receipt.amount == transaction.amount
            and receipt.currency == transaction.currency == "UZS"
        ):
            return original_params
        return None

    @staticmethod
    def _is_payme_time(value: Any) -> bool:
        return type(value) is int and 0 < value <= 9_999_999_999_999

    def _get_payme_statement(self, params: dict[str, Any], request_id: Any) -> dict[str, Any]:
        start, end = params.get("from"), params.get("to")
        if not self._is_payme_time(start) or not self._is_payme_time(end) or start > end:
            return {
                "error": {"code": -32602, "message": "Invalid statement period"},
                "id": request_id,
            }

        reconciliation = {
            "error": {"code": -32400, "message": "Statement requires reconciliation"},
            "id": request_id,
        }
        transactions = []
        seen_payments = set()
        for transaction, payment, receipt, payme_time in self.repository.iter_payme_statement(start=start, end=end):
            if transaction is None or payment is None or receipt is None or payme_time is None:
                return reconciliation
            original = self._payme_creation_params(receipt, transaction, payment)
            if (
                original is None
                or not payment.provider_payment_id
                or receipt.transaction_id != payment.provider_payment_id
                or transaction.visit_id not in (None, payment.visit_id)
                or payment.id in seen_payments
                or not self._payme_bound_amount_matches(payment, transaction, {})
                or type(original.get("amount")) is not int
                or original["amount"] != transaction.amount
            ):
                return reconciliation
            lifecycle = self._payme_lifecycle_result(transaction, payment, receipt)
            if lifecycle is None:
                return reconciliation
            seen_payments.add(payment.id)
            transactions.append({
                "id": transaction.transaction_id,
                "time": payme_time,
                "amount": transaction.amount,
                "account": {"order_id": payment.provider_payment_id},
                **lifecycle,
            })
        return {"id": request_id, "result": {"transactions": transactions}}

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

            if not isinstance(method, str) or method not in _PAYME_METHODS:
                return {"error": {"code": -32601, "message": "Method not found"}, "id": request_id}
            if not isinstance(params, dict):
                return {"error": {"code": -32602, "message": "Invalid method parameters"}, "id": request_id}
            if method == "GetStatement":
                return self._get_payme_statement(params, request_id)

            account = params.get("account")
            order_id = account.get("order_id") if isinstance(account, dict) else None
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
                payment_status = None
                with transaction_ctx(self.db):
                    # Use the cashier cancellation lock order: payment, then transaction.
                    payment_id = existing_transaction.payment_id
                    payment = (
                        self.repository.get_payment_by_id_for_update(payment_id, provider="payme")
                        if payment_id is not None
                        else None
                    )
                    if payment is None or not payment.provider_payment_id:
                        return self._payme_transaction_unavailable(request_id)
                    if "account" in params and order_id != payment.provider_payment_id:
                        return self._payme_order_unavailable(request_id)

                    existing_transaction = self.repository.get_existing_transaction(
                        transaction_id=payme_transaction_id, provider="payme", for_update=True
                    )
                    if method == "CreateTransaction":
                        return self._replay_payme_creation(
                            existing_transaction, payment=payment, params=params, request_id=request_id
                        )
                    if (
                        existing_transaction is None
                        or existing_transaction.payment_id != payment.id
                        or existing_transaction.visit_id not in (None, payment.visit_id)
                    ):
                        return self._payme_transaction_unavailable(request_id)

                    if method == "CheckPerformTransaction":
                        if not self._payme_params_amount_matches_payment(payment, params, existing_transaction):
                            return self._payme_amount_mismatch(request_id, payment.id)
                        if payment.status != "pending":
                            return self._payme_order_unavailable(request_id)
                        return {"result": {"allow": True}, "id": request_id}
                    if method == "CheckTransaction":
                        return self._check_payme_transaction(
                            existing_transaction, payment=payment, params=params, request_id=request_id
                        )
                    if method == "CancelTransaction":
                        return self._process_payme_cancellation(
                            existing_transaction, payment=payment, params=params, request_id=request_id
                        )
                    if method == "PerformTransaction":
                        payment_status = self._apply_payme_perform(
                            existing_transaction, payment=payment, params=params
                        )
                        if payment_status == "amount_mismatch":
                            return self._payme_amount_mismatch(request_id, payment_id)
                        if payment_status == "paid" and payment.paid_at is None:
                            return {
                                "error": {"code": -32400, "message": "Completion time requires reconciliation"},
                                "id": request_id,
                            }
                        if payment_status != "paid" or existing_transaction.status != "completed":
                            return {
                                "error": {"code": -31008, "message": "Payment cannot be completed"},
                                "id": request_id,
                            }
                        receipt = self._get_payme_creation_receipt(existing_transaction, payment)
                        return {
                            "result": {
                                "perform_time": self._payme_timestamp(payment.paid_at),
                                "transaction": receipt.id if receipt is not None else existing_transaction.id,
                                "state": 2,
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

            if method in {"PerformTransaction", "CancelTransaction", "CheckTransaction"}:
                return self._payme_transaction_unavailable(request_id)
            if method in {"CheckPerformTransaction", "CreateTransaction"} and not (
                isinstance(order_id, str) and order_id
            ):
                return self._payme_order_unavailable(request_id)
            if method == "CreateTransaction" and not (
                isinstance(payme_transaction_id, str) and payme_transaction_id
            ):
                return {"error": {"code": -32602, "message": "Invalid transaction ID"}, "id": request_id}

            if method == "CreateTransaction":
                if not self._is_payme_time(params.get("time")):
                    return {"error": {"code": -32602, "message": "Invalid transaction time"}, "id": request_id}
                amount = params.get("amount")
                # Both payment evidence rows store the provider amount as a PostgreSQL Integer.
                if type(amount) is not int or not 0 < amount <= 2_147_483_647:
                    return {"error": {"code": -32602, "message": "Invalid transaction amount"}, "id": request_id}

            with transaction_ctx(self.db):
                result = manager.process_webhook("payme", webhook_data)
                payment = None
                if isinstance(order_id, str) and order_id and order_id == result.payment_id:
                    payment = self.repository.get_payment_by_provider_payment_id_for_update(
                        provider="payme", provider_payment_id=order_id
                    )

                if method == "CreateTransaction" and result.success and payment is not None:
                    # The initial read may have preceded a concurrent creation.
                    existing_transaction = self.repository.get_existing_transaction(
                        transaction_id=payme_transaction_id, provider="payme", for_update=True
                    )
                    if existing_transaction is not None:
                        return self._replay_payme_creation(
                            existing_transaction, payment=payment, params=params, request_id=request_id
                        )
                    if payment.status != "pending":
                        return {
                            "error": {"code": -31008, "message": "Order is already reserved or closed"},
                            "id": request_id,
                        }

                webhook_id = f"payme_{uuid.uuid4().hex[:8]}"
                webhook = self.repository.create_webhook(
                    provider="payme",
                    webhook_id=webhook_id,
                    transaction_id=order_id or "unknown",
                    amount=params.get("amount", 0),
                    currency="UZS",
                    raw_data=webhook_data,
                )

                if result.success:
                    webhook.processed_at = datetime.now(UTC)
                    if payment is None:
                        webhook.status = "failed"
                        webhook.error_message = "provider_payment_binding_unavailable"
                        return self._payme_order_unavailable(request_id)

                    if not self._result_amount_matches_payment(payment, result):
                        webhook.status = "failed"
                        webhook.error_message = "provider_amount_mismatch"
                        return self._payme_amount_mismatch(request_id, payment.id)
                    if method == "CheckPerformTransaction":
                        if payment.status != "pending":
                            webhook.status = "failed"
                            webhook.error_message = "provider_payment_not_pending"
                            return self._payme_order_unavailable(request_id)
                        webhook.status = "processed"
                        return {"result": {"allow": True}, "id": request_id}

                    webhook.status = "processed"
                    mapped_status = self._map_provider_status_to_payment_status(result.status)
                    payment = self._update_payment_status(
                        payment_id=payment.id,
                        new_status=mapped_status,
                        commit=False,
                    )
                    if payment.status == "paid" and not payment.paid_at:
                        payment.paid_at = datetime.now(UTC)

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

                    if method == "CreateTransaction":
                        return self._payme_create_response(
                            webhook,
                            request_id=request_id,
                            payment_id=payment.id,
                            payment_status=mapped_status,
                        )
                    return {
                        "result": {},
                        "id": request_id,
                        "payment_id": payment.id if payment else None,
                        "payment_status": mapped_status,
                        "payment_provider": "payme",
                    }

                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.now(UTC)

                failed_payment = payment
                if failed_payment:
                    # Issue #06 Phase 4b B2: use canonical update_payment_status
                    failed_payment = self._update_payment_status(
                        payment_id=failed_payment.id,
                        new_status="failed",
                        commit=False,
                    )
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
            logger.error("Payme webhook error type=%s", type(exc).__name__)
            return {
                "error": {"code": -32603, "message": "Internal server error"},
                "id": request_id,
            }

    # State-machine rules are now in app.services.payment_state_checks
    # (shared with PaymentCancelService). These class attributes and
    # classmethods are retained as thin delegates for backward
    # compatibility with existing tests and any external callers.
    _TERMINAL_PAYMENT_STATUSES = frozenset({"refunded", "cancelled", "void"})
    _TERMINAL_TRANSACTION_STATUSES = frozenset({"cancelled", "refunded"})

    @classmethod
    def _can_transition_payment_status(
        cls, current_status: str, target_status: str
    ) -> bool:
        """Delegate to shared payment_state_checks module.

        Same-status duplicates (e.g. ``paid → paid`` from a retry webhook)
        are allowed as idempotent no-ops — ``payment.status`` is not
        mutated, but ``provider_data`` is still updated to preserve the
        audit trail.
        """
        return can_transition_payment_status(current_status, target_status)

    @classmethod
    def _can_transition_transaction_status(
        cls, current_status: str, target_status: str
    ) -> bool:
        """Delegate to shared payment_state_checks module."""
        return can_transition_transaction_status(current_status, target_status)

    def _apply_payme_perform(
        self,
        transaction: PaymentTransaction,
        *,
        payment: Payment,
        params: dict[str, Any],
    ) -> str:
        method = "PerformTransaction"
        provider_status = "completed"
        payment_status = "paid"
        payment_id = payment.id
        if not self._payme_params_amount_matches_payment(payment, params, transaction):
            return "amount_mismatch"

        current_tx_status = transaction.status
        current_payment_status = payment.status
        payment_blocked = not self._can_transition_payment_status(current_payment_status, payment_status)
        transaction_blocked = not self._can_transition_transaction_status(
            current_tx_status, provider_status
        )
        if payment_blocked:
            logger.warning(
                "Payme webhook: ignored invalid payment transition "
                "current=%s target=%s payment_id=%s method=%s",
                current_payment_status,
                payment_status,
                payment_id,
                method,
            )
            if current_tx_status != provider_status:
                logger.warning(
                    "Payme webhook: blocked transaction transition because "
                    "linked payment is terminal or incompatible "
                    "tx_current=%s tx_target=%s payment_status=%s "
                    "transaction_id=%s method=%s (Payme duplicate-webhook protector)",
                    current_tx_status,
                    provider_status,
                    current_payment_status,
                    transaction.id,
                    method,
                )
        elif transaction_blocked:
            logger.warning(
                "Payme webhook: ignored invalid transaction transition "
                "current=%s target=%s transaction_id=%s method=%s",
                current_tx_status, provider_status, transaction.id, method,
            )

        if current_payment_status == "paid" and payment.paid_at is None:
            # An existing completed payment without a timestamp needs reconciliation.
            return current_payment_status

        if not (payment_blocked or transaction_blocked):
            # BillingService owns the first paid_at and validates the full payment transition.
            if current_payment_status != payment_status:
                payment = self._update_payment_status(
                    payment_id=payment_id, new_status=payment_status, commit=False
                )
            transaction.status = provider_status

        self._store_payme_callback(transaction, payment, method=method, params=params)
        return payment.status

    @staticmethod
    def _store_payme_callback(
        transaction: PaymentTransaction,
        payment: Payment,
        *,
        method: str,
        params: dict[str, Any],
    ) -> None:
        transaction.provider_data = {
            **(transaction.provider_data or {}),
            "method": method,
            "transaction_id": params.get("id"),
            "params": params,
        }
        payment.provider_data = {
            **(payment.provider_data or {}),
            **transaction.provider_data,
        }

    @staticmethod
    def _payme_cancel_response(
        receipt: dict[str, Any], *, request_id: Any, payment_id: int, payment_status: str | None = None
    ) -> dict[str, Any]:
        return {
            "result": {key: receipt[key] for key in ("cancel_time", "transaction", "state")},
            "id": request_id,
            "payment_id": payment_id,
            "payment_status": payment_status,
            "payment_provider": "payme",
        }

    def _payme_bound_amount_matches(
        self, payment: Payment, transaction: PaymentTransaction, params: dict[str, Any]
    ) -> bool:
        return (
            payment.currency == transaction.currency == "UZS"
            and transaction.amount > 0
            and self._amounts_match(payment.amount, Decimal(transaction.amount) / 100)
            and (
                params.get("amount") is None
                or self._payme_params_amount_matches_payment(payment, params, transaction)
            )
        )

    @staticmethod
    def _payme_state(transaction: PaymentTransaction, payment: Payment) -> int | None:
        if transaction.status == "completed" and payment.status in {"paid", "completed"}:
            return 2
        if transaction.status in {"pending", "processing"} and payment.status in {"pending", "processing", "failed"}:
            return 1
        if transaction.status == payment.status:
            return {"cancelled": -1, "refunded": -2}.get(transaction.status)
        return None

    @staticmethod
    def _get_payme_cancellation_receipt(
        transaction: PaymentTransaction, payment: Payment, state: int | None
    ) -> dict[str, Any] | None:
        receipt = transaction.payme_cancel_receipt
        if (
            isinstance(receipt, dict)
            and state in {-1, -2}
            and type(receipt.get("payment_id")) is int
            and receipt["payment_id"] == payment.id
            and receipt.get("amount_minor") == transaction.amount
            and receipt.get("currency") == transaction.currency
            and type(receipt.get("state")) is int
            and receipt["state"] == state
            and type(receipt.get("transaction")) is int
            and receipt["transaction"] > 0
            and type(receipt.get("cancel_time")) is int
            and receipt["cancel_time"] > 0
            and (receipt.get("reason") is None or type(receipt["reason"]) is int)
        ):
            return receipt
        return None

    def _check_payme_transaction(
        self,
        transaction: PaymentTransaction,
        *,
        payment: Payment,
        params: dict[str, Any],
        request_id: Any,
    ) -> dict[str, Any]:
        if not self._payme_bound_amount_matches(payment, transaction, params):
            return self._payme_amount_mismatch(request_id, payment.id)

        creation = self._get_payme_creation_receipt(transaction, payment)
        if creation is not None:
            result = self._payme_lifecycle_result(transaction, payment, creation)
            if result is not None:
                return {"id": request_id, "result": result}
        return {
            "error": {"code": -32400, "message": "Transaction history requires reconciliation"},
            "id": request_id,
        }

    def _payme_lifecycle_result(
        self, transaction: PaymentTransaction, payment: Payment, creation: PaymentWebhook
    ) -> dict[str, Any] | None:
        state = self._payme_state(transaction, payment)
        if state is None:
            return None

        cancellation = None
        if state < 0:
            cancellation = self._get_payme_cancellation_receipt(transaction, payment, state)
            if cancellation is None or cancellation["transaction"] != creation.id:
                return None

        perform_time = 0
        if state in {2, -2}:
            if payment.paid_at is None:
                return None
            perform_time = self._payme_timestamp(payment.paid_at)

        return {
            "transaction": str(creation.id),
            "create_time": self._payme_timestamp(creation.created_at),
            "perform_time": perform_time,
            "cancel_time": cancellation["cancel_time"] if cancellation else 0,
            "state": state,
            "reason": cancellation.get("reason") if cancellation else None,
        }

    def _process_payme_cancellation(
        self,
        transaction: PaymentTransaction,
        *,
        payment: Payment,
        params: dict[str, Any],
        request_id: Any,
    ) -> dict[str, Any]:
        if not self._payme_bound_amount_matches(payment, transaction, params):
            return self._payme_amount_mismatch(request_id, payment.id)

        state = self._payme_state(transaction, payment)
        if transaction.payme_cancel_receipt is not None or transaction.status in {"cancelled", "refunded"}:
            receipt = self._get_payme_cancellation_receipt(transaction, payment, state)
            if receipt is not None:
                return self._payme_cancel_response(
                    receipt, request_id=request_id, payment_id=payment.id
                )
            return {
                "error": {"code": -32400, "message": "Cancellation receipt requires reconciliation"},
                "id": request_id,
            }

        if state not in {1, 2}:
            return {
                "error": {"code": -31007, "message": "Payment cannot be cancelled"},
                "id": request_id,
            }

        target_status = "refunded" if state == 2 else "cancelled"
        creation = self._get_payme_creation_receipt(transaction, payment)
        self._persist_pre_cancel_state(transaction.id, transaction.status)
        payment = self._update_payment_status(
            payment_id=payment.id, new_status=target_status, commit=False
        )
        reason = params.get("reason")
        callback_params = {"id": transaction.transaction_id}
        if type(reason) is int:
            callback_params["reason"] = reason

        receipt = {
            "payment_id": payment.id,
            "amount_minor": transaction.amount,
            "currency": transaction.currency,
            "transaction": creation.id if creation is not None else transaction.id,
            "state": -state,
            "cancel_time": self._payme_timestamp(datetime.now(UTC)),
            "reason": callback_params.get("reason"),
        }
        transaction.status = target_status
        transaction.payme_cancel_receipt = receipt
        self._store_payme_callback(
            transaction, payment, method="CancelTransaction", params=callback_params
        )
        return self._payme_cancel_response(
            receipt, request_id=request_id, payment_id=payment.id, payment_status=target_status
        )

    def _persist_pre_cancel_state(
        self, tx_id: int | None, pre_cancel_status: str | None
    ) -> None:
        """Append cancel pre-state atomically while retaining the financial row locks."""
        if tx_id is None:
            return
        try:
            with self.db.begin_nested():
                self.db.add(AuditLog(
                    action=PAYME_TX_PRE_CANCEL_STATE_ACTION,
                    entity_type="payment_transaction",
                    entity_id=tx_id,
                    payload={"pre_cancel_status": pre_cancel_status},
                    actor_type="system",
                    outcome="success",
                ))
                self.db.flush()
        except Exception as exc:
            logger.warning(
                "Payme webhook: secondary cancellation AuditLog INSERT failed. "
                "transaction_id=%s pre_cancel_status=%s error_type=%s",
                tx_id,
                pre_cancel_status,
                type(exc).__name__,
            )

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
                payment = None
                if result.payment_id:
                    payment = self.repository.get_payment_by_provider_payment_id_for_update(
                        provider="kaspi", provider_payment_id=result.payment_id
                    )

                if result.success:
                    webhook.status = "processed"
                    webhook.processed_at = datetime.now(UTC)
                    if result.payment_id and payment is None:
                        webhook.status = "failed"
                        webhook.error_message = "provider_payment_binding_unavailable"

                    mapped_status = None
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
                        # Issue #06 Phase 4b B2: Replaced direct payment.status =
                        # mapped_status with billing_service.update_payment_status()
                        # to enforce payment state machine validation.
                        #
                        # The lock is already acquired above via
                        # the repository. update_payment_status()
                        # will re-acquire it (idempotent within same transaction)
                        # and validate the transition via ALLOWED_PAYMENT_TRANSITIONS.
                        #
                        # commit=False because this is inside a larger webhook
                        # transaction (PaymentTransaction + webhook record +
                        # visit projection all committed together by the caller).
                        mapped_status = self._map_provider_status_to_payment_status(result.status)
                        payment = self._update_payment_status(
                            payment_id=payment.id,
                            new_status=mapped_status,
                            commit=False,
                        )
                        if payment.status == "paid" and not payment.paid_at:
                            payment.paid_at = datetime.now(UTC)

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
                webhook.processed_at = datetime.now(UTC)

                if payment:
                    payment = self._update_payment_status(
                        payment_id=payment.id,
                        new_status="failed",
                        commit=False,
                    )
                    payment.provider_data = {
                        **(payment.provider_data or {}),
                        "webhook_error": result.error_message,
                    }

                return {
                    "status": "error",
                    "message": result.error_message or "Processing error",
                    "payment_id": payment.id if payment else None,
                    "payment_status": "failed" if payment else None,
                    "payment_provider": "kaspi",
                }
        except Exception:
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
