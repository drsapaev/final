"""
API endpoints для обработки webhook от платежных провайдеров
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.payments import get_payment_manager
from app.db.session import get_db
from app.db.transactions import transaction as transaction_ctx
from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.services.payment_providers.manager import PaymentProviderManager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/click")
async def click_webhook(
    request: Request, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Webhook для Click платежной системы"""

    try:
        # Получаем данные webhook
        webhook_data = await request.json()

        # Логируем входящий webhook
        logger.info(f"Click webhook received: {webhook_data}")

        # ✅ SECURITY: Verify signature BEFORE processing
        manager = get_payment_manager()
        signature = webhook_data.get("sign_string")
        
        if not signature:
            logger.error("Click webhook: Missing signature")
            return {"error": -1, "error_note": "Missing signature"}
        
        # Verify signature using provider
        click_provider = manager.get_provider("click")
        if not click_provider:
            logger.error("Click webhook: Provider not configured")
            return {"error": -1, "error_note": "Provider not configured"}
        
        if not click_provider.validate_webhook_signature(webhook_data, signature):
            logger.error("Click webhook: Invalid signature")
            return {"error": -1, "error_note": "Invalid signature"}

        # ✅ SECURITY: Idempotency check - prevent duplicate processing
        transaction_id = webhook_data.get("merchant_trans_id", "unknown")
        click_trans_id = webhook_data.get("click_trans_id")
        
        # Check if this transaction was already processed
        existing_transaction = (
            db.query(PaymentTransaction)
            .filter(
                PaymentTransaction.transaction_id == click_trans_id,
                PaymentTransaction.provider == "click"
            )
            .first()
        )
        
        if existing_transaction:
            logger.info(f"Click webhook: Transaction {click_trans_id} already processed (idempotent)")
            # Return success for duplicate webhook (idempotent)
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": transaction_id,
                "merchant_prepare_id": existing_transaction.webhook_id or 0,
                "error": 0,
                "error_note": "Already processed",
            }

        # ✅ SECURITY: Only after signature verification and idempotency check, create webhook record
        # ✅ SECURITY: Use explicit transaction for atomicity
        with transaction_ctx(db) as txn:
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
            txn.flush()  # Get webhook.id without committing
            txn.refresh(webhook)

            # Обрабатываем webhook через менеджер
            result = manager.process_webhook("click", webhook_data)

            if result.success:
                # Обновляем статус webhook
                webhook.status = "processed"
                # Note: payment_status field removed from model, using status instead
                webhook.processed_at = datetime.utcnow()

                # Ищем соответствующий платеж
                payment = None
                if result.payment_id:
                    # Ищем по order_id (который содержит payment.id)
                    payment_id_from_order = _extract_payment_id_from_order(
                        result.payment_id
                    )
                    if payment_id_from_order:
                        payment = (
                            txn.query(Payment)
                            .filter(Payment.id == payment_id_from_order)
                            .first()
                        )

                if payment:
                    # Обновляем статус платежа
                    payment.status = _map_provider_status_to_payment_status(result.status)
                    if payment.status == "paid":
                        payment.paid_at = datetime.utcnow()

                    payment.provider_data = {
                        **(payment.provider_data or {}),
                        **result.provider_data,
                    }

                    webhook.payment_id = payment.id
                    webhook.visit_id = payment.visit_id

                    # Создаем транзакцию
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
                # Transaction commits automatically on exit

                # Click ожидает специфичный ответ
                action = webhook_data.get("action", 0)
                error = 0 if result.status == "completed" else -1

                return {
                    "click_trans_id": webhook_data.get("click_trans_id"),
                    "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                    "merchant_prepare_id": webhook.id,
                    "error": error,
                    "error_note": "" if error == 0 else "Payment processing error",
                }
            else:
                # Ошибка обработки
                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.utcnow()
                # Transaction commits automatically on exit

            return {
                "click_trans_id": webhook_data.get("click_trans_id"),
                "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                "merchant_prepare_id": webhook.id,
                "error": -1,
                "error_note": result.error_message or "Processing error",
            }

    except Exception as e:
        logger.error(f"Click webhook error: {str(e)}")
        return {"error": -1, "error_note": f"Internal server error: {str(e)}"}


@router.post("/payme")
async def payme_webhook(
    request: Request, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Webhook для Payme платежной системы (JSON-RPC)"""

    try:
        # Получаем данные webhook
        webhook_data = await request.json()

        # Логируем входящий webhook
        logger.info(f"Payme webhook received: {webhook_data}")

        method = webhook_data.get("method")
        params = webhook_data.get("params", {})
        request_id = webhook_data.get("id")

        # ✅ SECURITY: Verify Authorization header BEFORE processing
        manager = get_payment_manager()
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            logger.error("Payme webhook: Missing Authorization header")
            return {
                "error": {"code": -32504, "message": "Missing Authorization header"},
                "id": request_id,
            }
        
        # Verify Authorization using provider
        payme_provider = manager.get_provider("payme")
        if not payme_provider:
            logger.error("Payme webhook: Provider not configured")
            return {
                "error": {"code": -32504, "message": "Provider not configured"},
                "id": request_id,
            }
        
        if not payme_provider.validate_webhook_signature(webhook_data, None, auth_header):
            logger.error("Payme webhook: Invalid Authorization header")
            return {
                "error": {"code": -32504, "message": "Invalid Authorization"},
                "id": request_id,
            }

        # ✅ SECURITY: Idempotency check - prevent duplicate processing
        account = params.get("account", {})
        order_id = account.get("order_id", "unknown")
        payme_transaction_id = params.get("id")  # PayMe transaction ID
        
        # Check if this transaction was already processed
        existing_transaction = None
        if payme_transaction_id:
            existing_transaction = (
                db.query(PaymentTransaction)
                .filter(
                    PaymentTransaction.transaction_id == payme_transaction_id,
                    PaymentTransaction.provider == "payme"
                )
                .first()
            )
        
        if existing_transaction:
            logger.info(f"Payme webhook: Transaction {payme_transaction_id} already processed (idempotent)")
            # Return success for duplicate webhook (idempotent)
            if method == "CheckPerformTransaction":
                return {"result": {"allow": True}, "id": request_id}
            elif method == "CreateTransaction":
                return {
                    "result": {
                        "create_time": int(datetime.utcnow().timestamp() * 1000),
                        "transaction": existing_transaction.id,
                        "state": 1,
                    },
                    "id": request_id,
                }
            elif method == "PerformTransaction":
                return {
                    "result": {
                        "perform_time": int(datetime.utcnow().timestamp() * 1000),
                        "transaction": existing_transaction.id,
                        "state": 2,
                    },
                    "id": request_id,
                }
            elif method == "CancelTransaction":
                # ✅ ИСПРАВЛЕНО: Добавлена обработка CancelTransaction для идемпотентности
                return {
                    "result": {
                        "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                        "transaction": existing_transaction.id,
                        "state": -1,
                    },
                    "id": request_id,
                }
            else:
                return {"result": {}, "id": request_id}

        # ✅ SECURITY: Only after signature verification and idempotency check, create webhook record
        # ✅ SECURITY: Use explicit transaction for atomicity (same as Click webhook)
        with transaction_ctx(db) as txn:
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
            txn.flush()  # Get webhook.id without committing
            txn.refresh(webhook)

            # Обрабатываем webhook через менеджер
            result = manager.process_webhook("payme", webhook_data)

            if result.success:
                # Обновляем статус webhook
                webhook.status = "processed"
                # Note: payment_status field removed from model, using status instead
                webhook.processed_at = datetime.utcnow()

                # Ищем соответствующий платеж
                payment = None
                if result.payment_id:
                    payment_id_from_order = _extract_payment_id_from_order(
                        result.payment_id
                    )
                    if payment_id_from_order:
                        payment = (
                            txn.query(Payment)
                            .filter(Payment.id == payment_id_from_order)
                            .first()
                        )

                if payment:
                    # Обновляем статус платежа
                    payment.status = _map_provider_status_to_payment_status(result.status)
                    if payment.status == "paid":
                        payment.paid_at = datetime.utcnow()

                    payment.provider_data = {
                        **(payment.provider_data or {}),
                        **result.provider_data,
                    }

                    webhook.payment_id = payment.id
                    webhook.visit_id = payment.visit_id

                    # Создаем транзакцию
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
                # Transaction commits automatically on exit

                # Payme JSON-RPC ответ для успешной обработки
                if method == "CheckPerformTransaction":
                    return {"result": {"allow": True}, "id": request_id}
                elif method == "CreateTransaction":
                    return {
                        "result": {
                            "create_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": webhook.id,
                            "state": 1,
                        },
                        "id": request_id,
                    }
                elif method == "PerformTransaction":
                    return {
                        "result": {
                            "perform_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": webhook.id,
                            "state": 2,
                        },
                        "id": request_id,
                    }
                elif method == "CancelTransaction":
                    return {
                        "result": {
                            "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                            "transaction": webhook.id,
                            "state": -1,
                        },
                        "id": request_id,
                    }
                else:
                    return {"result": {}, "id": request_id}
            else:
                # Ошибка обработки
                webhook.status = "failed"
                webhook.error_message = result.error_message
                webhook.processed_at = datetime.utcnow()
                # Transaction commits automatically on exit

                return {
                    "error": {
                        "code": -32400,
                        "message": result.error_message or "Processing error",
                    },
                    "id": request_id,
                }

    except Exception as e:
        logger.error(f"Payme webhook error: {str(e)}")
        return {
            "error": {"code": -32603, "message": f"Internal server error: {str(e)}"},
            "id": webhook_data.get("id") if webhook_data else None,
        }


@router.post("/kaspi")
async def kaspi_webhook(
    request: Request, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Webhook для Kaspi Pay платежной системы"""

    try:
        # Получаем данные webhook
        webhook_data = await request.json()

        # Логируем входящий webhook
        logger.info(f"Kaspi webhook received: {webhook_data}")

        # Создаем запись webhook в БД
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

        db.add(webhook)
        db.commit()
        db.refresh(webhook)

        # Обрабатываем webhook через менеджер
        manager = get_payment_manager()
        result = manager.process_webhook("kaspi", webhook_data)

        if result.success:
            # Обновляем статус webhook
            webhook.status = "processed"
            # Note: payment_status field removed from model, using status instead
            webhook.processed_at = datetime.utcnow()

            # Ищем соответствующий платеж по transaction_id
            payment = None
            if result.payment_id:
                payment = (
                    db.query(Payment)
                    .filter(Payment.provider_payment_id == result.payment_id)
                    .first()
                )

            if payment:
                # Обновляем статус платежа
                payment.status = _map_provider_status_to_payment_status(result.status)
                if payment.status == "paid":
                    payment.paid_at = datetime.utcnow()

                payment.provider_data = {
                    **(payment.provider_data or {}),
                    **result.provider_data,
                }

                webhook.payment_id = payment.id
                webhook.visit_id = payment.visit_id

                # Создаем транзакцию
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

                db.add(transaction)

            db.commit()

            # Kaspi ожидает простой ответ
            return {"status": "success", "message": "Webhook processed successfully"}

        else:
            # Ошибка обработки
            webhook.status = "failed"
            webhook.error_message = result.error_message
            webhook.processed_at = datetime.utcnow()
            db.commit()

            return {
                "status": "error",
                "message": result.error_message or "Processing error",
            }

    except Exception as e:
        logger.error(f"Kaspi webhook error: {str(e)}")
        return {"status": "error", "message": f"Internal server error: {str(e)}"}


# Вспомогательные функции


def _extract_payment_id_from_order(order_id: str) -> int:
    """Извлекает payment_id из order_id формата clinic_{payment_id}_{timestamp}"""
    try:
        parts = order_id.split("_")
        if len(parts) >= 2 and parts[0] == "clinic":
            return int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


def _map_provider_status_to_payment_status(provider_status: str) -> str:
    """Маппинг статусов провайдера в статусы платежа"""
    status_mapping = {
        "pending": "pending",
        "processing": "processing",
        "completed": "paid",
        "failed": "failed",
        "cancelled": "cancelled",
        "refunded": "refunded",
    }
    return status_mapping.get(provider_status, "failed")
