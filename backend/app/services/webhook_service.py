"""
Сервис для управления webhook'ами
"""
import logging
import asyncio
import json
import hmac
import hashlib
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
import httpx

from app.models.webhook import (
    Webhook, WebhookCall, WebhookEvent, 
    WebhookEventType, WebhookStatus, WebhookCallStatus
)
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)


class WebhookService:
    """Сервис для управления webhook'ами"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.AsyncClient(timeout=30.0)
    
    # ===================== УПРАВЛЕНИЕ WEBHOOK'АМИ =====================
    
    def create_webhook(
        self, 
        name: str,
        url: str,
        events: List[str],
        description: str = None,
        headers: Dict[str, str] = None,
        secret: str = None,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 30,
        filters: Dict[str, Any] = None,
        created_by: int = None
    ) -> Webhook:
        """Создает новый webhook"""
        try:
            webhook = Webhook(
                name=name,
                description=description,
                url=url,
                events=events,
                headers=headers or {},
                secret=secret,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
                filters=filters or {},
                created_by=created_by
            )
            
            self.db.add(webhook)
            self.db.commit()
            self.db.refresh(webhook)
            
            logger.info(f"Создан webhook {webhook.name} (ID: {webhook.id})")
            return webhook
            
        except Exception as e:
            logger.error(f"Ошибка создания webhook: {e}")
            self.db.rollback()
            raise
    
    def update_webhook(
        self, 
        webhook_id: int, 
        **updates
    ) -> Optional[Webhook]:
        """Обновляет webhook"""
        try:
            webhook = self.db.query(Webhook).filter(Webhook.id == webhook_id).first()
            if not webhook:
                return None
            
            for key, value in updates.items():
                if hasattr(webhook, key):
                    setattr(webhook, key, value)
            
            self.db.commit()
            self.db.refresh(webhook)
            
            logger.info(f"Обновлен webhook {webhook.name} (ID: {webhook.id})")
            return webhook
            
        except Exception as e:
            logger.error(f"Ошибка обновления webhook {webhook_id}: {e}")
            self.db.rollback()
            raise
    
    def delete_webhook(self, webhook_id: int) -> bool:
        """Удаляет webhook"""
        try:
            webhook = self.db.query(Webhook).filter(Webhook.id == webhook_id).first()
            if not webhook:
                return False
            
            self.db.delete(webhook)
            self.db.commit()
            
            logger.info(f"Удален webhook {webhook.name} (ID: {webhook.id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления webhook {webhook_id}: {e}")
            self.db.rollback()
            raise
    
    def get_webhook(self, webhook_id: int) -> Optional[Webhook]:
        """Получает webhook по ID"""
        return self.db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    def get_webhooks(
        self, 
        status: WebhookStatus = None,
        event_type: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Webhook]:
        """Получает список webhook'ов с фильтрацией"""
        query = self.db.query(Webhook)
        
        if status:
            query = query.filter(Webhook.status == status)
        
        if event_type:
            query = query.filter(Webhook.events.contains([event_type]))
        
        return query.order_by(desc(Webhook.created_at)).offset(offset).limit(limit).all()
    
    # ===================== ОБРАБОТКА СОБЫТИЙ =====================
    
    async def trigger_event(
        self, 
        event_type: WebhookEventType, 
        event_data: Dict[str, Any],
        source: str = "api",
        source_id: str = None,
        correlation_id: str = None
    ):
        """Триггерит событие для всех подписанных webhook'ов"""
        try:
            # Создаем событие в очереди
            event = WebhookEvent(
                event_type=event_type,
                event_data=event_data,
                source=source,
                source_id=source_id,
                correlation_id=correlation_id
            )
            
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            
            # Находим все активные webhook'и для этого типа события
            webhooks = self.db.query(Webhook).filter(
                and_(
                    Webhook.is_active == True,
                    Webhook.status == WebhookStatus.ACTIVE,
                    Webhook.events.contains([event_type.value])
                )
            ).all()
            
            # Отправляем webhook'и асинхронно
            tasks = []
            for webhook in webhooks:
                if self._should_trigger_webhook(webhook, event_data):
                    task = self._send_webhook_async(webhook, event_type, event_data)
                    tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Отмечаем событие как обработанное
            event.processed = True
            event.processed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Обработано событие {event_type.value} для {len(tasks)} webhook'ов")
            
        except Exception as e:
            logger.error(f"Ошибка обработки события {event_type.value}: {e}")
            raise
    
    def _should_trigger_webhook(self, webhook: Webhook, event_data: Dict[str, Any]) -> bool:
        """Проверяет, должен ли webhook быть вызван на основе фильтров"""
        if not webhook.filters:
            return True
        
        try:
            for filter_key, filter_value in webhook.filters.items():
                if filter_key in event_data:
                    if isinstance(filter_value, list):
                        if event_data[filter_key] not in filter_value:
                            return False
                    elif event_data[filter_key] != filter_value:
                        return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Ошибка проверки фильтров webhook {webhook.id}: {e}")
            return True  # При ошибке фильтрации отправляем webhook
    
    async def _send_webhook_async(
        self, 
        webhook: Webhook, 
        event_type: WebhookEventType, 
        event_data: Dict[str, Any]
    ):
        """Асинхронно отправляет webhook"""
        try:
            # Создаем запись о вызове
            call = WebhookCall(
                webhook_id=webhook.id,
                event_type=event_type,
                event_data=event_data,
                url=webhook.url,
                max_attempts=webhook.max_retries + 1
            )
            
            self.db.add(call)
            self.db.commit()
            self.db.refresh(call)
            
            # Отправляем webhook
            await self._execute_webhook_call(call)
            
        except Exception as e:
            logger.error(f"Ошибка отправки webhook {webhook.id}: {e}")
    
    async def _execute_webhook_call(self, call: WebhookCall):
        """Выполняет HTTP вызов webhook'а"""
        webhook = call.webhook
        start_time = time.time()
        
        try:
            # Подготавливаем payload
            payload = {
                "event_type": call.event_type.value,
                "event_data": call.event_data,
                "webhook_id": webhook.uuid,
                "timestamp": datetime.utcnow().isoformat(),
                "attempt": call.attempt_number
            }
            
            # Подготавливаем заголовки
            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"MediLab-Webhook/1.0",
                "X-Webhook-Event": call.event_type.value,
                "X-Webhook-ID": webhook.uuid,
                "X-Webhook-Attempt": str(call.attempt_number)
            }
            
            # Добавляем пользовательские заголовки
            if webhook.headers:
                headers.update(webhook.headers)
            
            # Добавляем подпись, если есть секрет
            if webhook.secret:
                signature = self._generate_signature(webhook.secret, json.dumps(payload))
                headers["X-Webhook-Signature"] = signature
            
            # Обновляем запись о вызове
            call.payload = payload
            call.headers = headers
            call.status = WebhookCallStatus.PENDING
            
            # Выполняем HTTP запрос
            async with httpx.AsyncClient(timeout=webhook.timeout) as client:
                response = await client.post(
                    webhook.url,
                    json=payload,
                    headers=headers
                )
            
            # Рассчитываем время выполнения
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Обновляем результат
            call.response_status_code = response.status_code
            call.response_headers = dict(response.headers)
            call.response_body = response.text[:10000]  # Ограничиваем размер
            call.duration_ms = duration_ms
            call.completed_at = datetime.utcnow()
            
            # Определяем статус
            if 200 <= response.status_code < 300:
                call.status = WebhookCallStatus.SUCCESS
                webhook.successful_calls += 1
                webhook.last_success_at = datetime.utcnow()
                logger.info(f"Webhook {webhook.id} успешно отправлен (статус: {response.status_code})")
            else:
                call.status = WebhookCallStatus.FAILED
                call.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
                webhook.failed_calls += 1
                webhook.last_failure_at = datetime.utcnow()
                logger.warning(f"Webhook {webhook.id} завершился с ошибкой: {response.status_code}")
                
                # Планируем повтор, если есть попытки
                if call.attempt_number < call.max_attempts:
                    await self._schedule_retry(call)
            
        except Exception as e:
            # Обрабатываем ошибки сети/таймаута
            duration_ms = int((time.time() - start_time) * 1000)
            
            call.status = WebhookCallStatus.FAILED
            call.error_message = str(e)[:1000]
            call.duration_ms = duration_ms
            call.completed_at = datetime.utcnow()
            
            webhook.failed_calls += 1
            webhook.last_failure_at = datetime.utcnow()
            
            logger.error(f"Ошибка выполнения webhook {webhook.id}: {e}")
            
            # Планируем повтор, если есть попытки
            if call.attempt_number < call.max_attempts:
                await self._schedule_retry(call)
        
        finally:
            # Обновляем статистику webhook'а
            webhook.total_calls += 1
            webhook.last_call_at = datetime.utcnow()
            
            self.db.commit()
    
    async def _schedule_retry(self, call: WebhookCall):
        """Планирует повторный вызов webhook'а"""
        try:
            webhook = call.webhook
            
            # Создаем новую попытку
            retry_call = WebhookCall(
                webhook_id=call.webhook_id,
                event_type=call.event_type,
                event_data=call.event_data,
                url=call.url,
                method=call.method,
                headers=call.headers,
                payload=call.payload,
                attempt_number=call.attempt_number + 1,
                max_attempts=call.max_attempts,
                next_retry_at=datetime.utcnow() + timedelta(seconds=webhook.retry_delay)
            )
            
            self.db.add(retry_call)
            self.db.commit()
            
            logger.info(f"Запланирован повтор webhook {webhook.id} (попытка {retry_call.attempt_number})")
            
        except Exception as e:
            logger.error(f"Ошибка планирования повтора webhook {call.webhook_id}: {e}")
    
    def _generate_signature(self, secret: str, payload: str) -> str:
        """Генерирует HMAC подпись для webhook'а"""
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    # ===================== ПОВТОРЫ И ОЧИСТКА =====================
    
    async def process_retries(self):
        """Обрабатывает запланированные повторы"""
        try:
            # Находим вызовы, готовые к повтору
            retry_calls = self.db.query(WebhookCall).filter(
                and_(
                    WebhookCall.status == WebhookCallStatus.RETRYING,
                    WebhookCall.next_retry_at <= datetime.utcnow()
                )
            ).limit(50).all()
            
            # Выполняем повторы
            tasks = []
            for call in retry_calls:
                task = self._execute_webhook_call(call)
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Обработано {len(tasks)} повторов webhook'ов")
            
        except Exception as e:
            logger.error(f"Ошибка обработки повторов: {e}")
    
    def cleanup_old_calls(self, days: int = 30):
        """Очищает старые вызовы webhook'ов"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            deleted_count = self.db.query(WebhookCall).filter(
                WebhookCall.created_at < cutoff_date
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Удалено {deleted_count} старых вызовов webhook'ов")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых вызовов: {e}")
            self.db.rollback()
            raise
    
    def cleanup_old_events(self, days: int = 7):
        """Очищает старые события"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            deleted_count = self.db.query(WebhookEvent).filter(
                and_(
                    WebhookEvent.created_at < cutoff_date,
                    WebhookEvent.processed == True
                )
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Удалено {deleted_count} старых событий")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых событий: {e}")
            self.db.rollback()
            raise
    
    # ===================== СТАТИСТИКА И МОНИТОРИНГ =====================
    
    def get_webhook_stats(self, webhook_id: int) -> Dict[str, Any]:
        """Получает статистику webhook'а"""
        webhook = self.get_webhook(webhook_id)
        if not webhook:
            return {}
        
        # Статистика за последние 24 часа
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_calls = self.db.query(WebhookCall).filter(
            and_(
                WebhookCall.webhook_id == webhook_id,
                WebhookCall.created_at >= last_24h
            )
        ).all()
        
        recent_success = len([c for c in recent_calls if c.status == WebhookCallStatus.SUCCESS])
        recent_failed = len([c for c in recent_calls if c.status == WebhookCallStatus.FAILED])
        
        # Средняя скорость ответа
        successful_calls = [c for c in recent_calls if c.status == WebhookCallStatus.SUCCESS and c.duration_ms]
        avg_response_time = sum(c.duration_ms for c in successful_calls) / len(successful_calls) if successful_calls else 0
        
        return {
            "webhook_id": webhook.id,
            "name": webhook.name,
            "status": webhook.status.value,
            "total_calls": webhook.total_calls,
            "successful_calls": webhook.successful_calls,
            "failed_calls": webhook.failed_calls,
            "success_rate": (webhook.successful_calls / webhook.total_calls * 100) if webhook.total_calls > 0 else 0,
            "last_call_at": webhook.last_call_at.isoformat() if webhook.last_call_at else None,
            "last_success_at": webhook.last_success_at.isoformat() if webhook.last_success_at else None,
            "last_failure_at": webhook.last_failure_at.isoformat() if webhook.last_failure_at else None,
            "recent_24h": {
                "total_calls": len(recent_calls),
                "successful_calls": recent_success,
                "failed_calls": recent_failed,
                "success_rate": (recent_success / len(recent_calls) * 100) if recent_calls else 0,
                "avg_response_time_ms": round(avg_response_time, 2)
            }
        }
    
    def get_system_webhook_stats(self) -> Dict[str, Any]:
        """Получает общую статистику системы webhook'ов"""
        total_webhooks = self.db.query(Webhook).count()
        active_webhooks = self.db.query(Webhook).filter(
            and_(
                Webhook.is_active == True,
                Webhook.status == WebhookStatus.ACTIVE
            )
        ).count()
        
        # Статистика за последние 24 часа
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_calls = self.db.query(WebhookCall).filter(
            WebhookCall.created_at >= last_24h
        ).count()
        
        recent_success = self.db.query(WebhookCall).filter(
            and_(
                WebhookCall.created_at >= last_24h,
                WebhookCall.status == WebhookCallStatus.SUCCESS
            )
        ).count()
        
        pending_retries = self.db.query(WebhookCall).filter(
            WebhookCall.status == WebhookCallStatus.RETRYING
        ).count()
        
        unprocessed_events = self.db.query(WebhookEvent).filter(
            WebhookEvent.processed == False
        ).count()
        
        return {
            "total_webhooks": total_webhooks,
            "active_webhooks": active_webhooks,
            "inactive_webhooks": total_webhooks - active_webhooks,
            "recent_24h": {
                "total_calls": recent_calls,
                "successful_calls": recent_success,
                "failed_calls": recent_calls - recent_success,
                "success_rate": (recent_success / recent_calls * 100) if recent_calls > 0 else 0
            },
            "pending_retries": pending_retries,
            "unprocessed_events": unprocessed_events
        }


def get_webhook_service(db: Session) -> WebhookService:
    """Получить экземпляр сервиса webhook'ов"""
    return WebhookService(db)

