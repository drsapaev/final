"""
API endpoints для обработки webhook от платежных провайдеров
"""
from typing import Any, Dict
from datetime import datetime
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.payment import Payment
from app.models.payment_webhook import PaymentWebhook, PaymentTransaction
from app.services.payment_providers.manager import PaymentProviderManager
from app.api.v1.endpoints.payments import get_payment_manager

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/click")
async def click_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Webhook для Click платежной системы"""
    
    try:
        # Получаем данные webhook
        webhook_data = await request.json()
        
        # Логируем входящий webhook
        logger.info(f"Click webhook received: {webhook_data}")
        
        # Создаем запись webhook в БД
        webhook_id = f"click_{uuid.uuid4().hex[:8]}"
        webhook = PaymentWebhook(
            provider="click",
            webhook_id=webhook_id,
            transaction_id=webhook_data.get("merchant_trans_id", "unknown"),
            status="pending",
            amount=webhook_data.get("amount", 0),
            currency="UZS",
            raw_data=webhook_data,
            signature=webhook_data.get("sign_string")
        )
        
        db.add(webhook)
        db.commit()
        db.refresh(webhook)
        
        # Обрабатываем webhook через менеджер
        manager = get_payment_manager()
        result = manager.process_webhook("click", webhook_data)
        
        if result.success:
            # Обновляем статус webhook
            webhook.status = "processed"
            webhook.payment_status = result.status
            webhook.processed_at = datetime.utcnow()
            
            # Ищем соответствующий платеж
            payment = None
            if result.payment_id:
                # Ищем по order_id (который содержит payment.id)
                payment_id_from_order = _extract_payment_id_from_order(result.payment_id)
                if payment_id_from_order:
                    payment = db.query(Payment).filter(Payment.id == payment_id_from_order).first()
            
            if payment:
                # Обновляем статус платежа
                payment.status = _map_provider_status_to_payment_status(result.status)
                if payment.status == "paid":
                    payment.paid_at = datetime.utcnow()
                
                payment.provider_data = {
                    **(payment.provider_data or {}),
                    **result.provider_data
                }
                
                webhook.payment_id = payment.id
                webhook.visit_id = payment.visit_id
                
                # Создаем транзакцию
                transaction = PaymentTransaction(
                    transaction_id=webhook_data.get("click_trans_id", webhook_id),
                    provider="click",
                    amount=webhook_data.get("amount", 0),
                    currency="UZS",
                    status=result.status,
                    payment_id=payment.id,
                    webhook_id=webhook.id,
                    visit_id=payment.visit_id,
                    provider_data=result.provider_data
                )
                
                db.add(transaction)
            
            db.commit()
            
            # Click ожидает специфичный ответ
            action = webhook_data.get("action", 0)
            error = 0 if result.status == "completed" else -1
            
            return {
                "click_trans_id": webhook_data.get("click_trans_id"),
                "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                "merchant_prepare_id": webhook.id,
                "error": error,
                "error_note": "" if error == 0 else "Payment processing error"
            }
        
        else:
            # Ошибка обработки
            webhook.status = "failed"
            webhook.error_message = result.error_message
            webhook.processed_at = datetime.utcnow()
            db.commit()
            
            return {
                "click_trans_id": webhook_data.get("click_trans_id"),
                "merchant_trans_id": webhook_data.get("merchant_trans_id"),
                "merchant_prepare_id": webhook.id,
                "error": -1,
                "error_note": result.error_message or "Processing error"
            }
    
    except Exception as e:
        logger.error(f"Click webhook error: {str(e)}")
        return {
            "error": -1,
            "error_note": f"Internal server error: {str(e)}"
        }

@router.post("/payme")
async def payme_webhook(
    request: Request,
    db: Session = Depends(get_db)
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
        
        # Создаем запись webhook в БД
        webhook_id = f"payme_{uuid.uuid4().hex[:8]}"
        account = params.get("account", {})
        order_id = account.get("order_id", "unknown")
        
        webhook = PaymentWebhook(
            provider="payme",
            webhook_id=webhook_id,
            transaction_id=order_id,
            status="pending",
            amount=params.get("amount", 0),
            currency="UZS",
            raw_data=webhook_data
        )
        
        db.add(webhook)
        db.commit()
        db.refresh(webhook)
        
        # Обрабатываем webhook через менеджер
        manager = get_payment_manager()
        result = manager.process_webhook("payme", webhook_data)
        
        if result.success:
            # Обновляем статус webhook
            webhook.status = "processed"
            webhook.payment_status = result.status
            webhook.processed_at = datetime.utcnow()
            
            # Ищем соответствующий платеж
            payment = None
            if result.payment_id:
                payment_id_from_order = _extract_payment_id_from_order(result.payment_id)
                if payment_id_from_order:
                    payment = db.query(Payment).filter(Payment.id == payment_id_from_order).first()
            
            if payment:
                # Обновляем статус платежа
                payment.status = _map_provider_status_to_payment_status(result.status)
                if payment.status == "paid":
                    payment.paid_at = datetime.utcnow()
                
                payment.provider_data = {
                    **(payment.provider_data or {}),
                    **result.provider_data
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
                    provider_data=result.provider_data
                )
                
                db.add(transaction)
            
            db.commit()
            
            # Payme JSON-RPC ответ
            if method == "CheckPerformTransaction":
                return {
                    "result": {
                        "allow": True
                    },
                    "id": request_id
                }
            elif method == "CreateTransaction":
                return {
                    "result": {
                        "create_time": int(datetime.utcnow().timestamp() * 1000),
                        "transaction": webhook.id,
                        "state": 1
                    },
                    "id": request_id
                }
            elif method == "PerformTransaction":
                return {
                    "result": {
                        "perform_time": int(datetime.utcnow().timestamp() * 1000),
                        "transaction": webhook.id,
                        "state": 2
                    },
                    "id": request_id
                }
            elif method == "CancelTransaction":
                return {
                    "result": {
                        "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                        "transaction": webhook.id,
                        "state": -1
                    },
                    "id": request_id
                }
            else:
                return {
                    "result": {},
                    "id": request_id
                }
        
        else:
            # Ошибка обработки
            webhook.status = "failed"
            webhook.error_message = result.error_message
            webhook.processed_at = datetime.utcnow()
            db.commit()
            
            return {
                "error": {
                    "code": -32400,
                    "message": result.error_message or "Processing error"
                },
                "id": request_id
            }
    
    except Exception as e:
        logger.error(f"Payme webhook error: {str(e)}")
        return {
            "error": {
                "code": -32603,
                "message": f"Internal server error: {str(e)}"
            },
            "id": webhook_data.get("id") if webhook_data else None
        }

@router.post("/kaspi")
async def kaspi_webhook(
    request: Request,
    db: Session = Depends(get_db)
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
            signature=webhook_data.get("signature")
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
            webhook.payment_status = result.status
            webhook.processed_at = datetime.utcnow()
            
            # Ищем соответствующий платеж по transaction_id
            payment = None
            if result.payment_id:
                payment = db.query(Payment).filter(
                    Payment.provider_payment_id == result.payment_id
                ).first()
            
            if payment:
                # Обновляем статус платежа
                payment.status = _map_provider_status_to_payment_status(result.status)
                if payment.status == "paid":
                    payment.paid_at = datetime.utcnow()
                
                payment.provider_data = {
                    **(payment.provider_data or {}),
                    **result.provider_data
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
                    provider_data=result.provider_data
                )
                
                db.add(transaction)
            
            db.commit()
            
            # Kaspi ожидает простой ответ
            return {
                "status": "success",
                "message": "Webhook processed successfully"
            }
        
        else:
            # Ошибка обработки
            webhook.status = "failed"
            webhook.error_message = result.error_message
            webhook.processed_at = datetime.utcnow()
            db.commit()
            
            return {
                "status": "error",
                "message": result.error_message or "Processing error"
            }
    
    except Exception as e:
        logger.error(f"Kaspi webhook error: {str(e)}")
        return {
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }

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
        "refunded": "refunded"
    }
    return status_mapping.get(provider_status, "failed")
