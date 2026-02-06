"""
Сервис для массового переноса очереди на завтра (форс-мажор)
согласно ONLINE_QUEUE_SYSTEM_V2.md раздел 20.3

Используется когда:
- Смена врача закончилась, но в очереди остались люди
- Врачу срочно нужно уйти (болезнь, экстренная ситуация)
- Форс-мажорные обстоятельства в клинике
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment
from app.models.refund_deposit import (
    PatientDeposit, 
    DepositTransaction,
    RefundRequest,
    RefundRequestStatus,
    RefundType,
    DepositTransactionType
)
from app.services.fcm_service import get_fcm_service
from app.services.notifications import notification_sender_service

logger = logging.getLogger(__name__)


class ForceMajeureError(Exception):
    """Ошибка при обработке форс-мажора"""
    pass


class ForceMajeureService:
    """
    Сервис для обработки форс-мажорных ситуаций с очередью
    
    Основные функции:
    1. Массовый перенос записей на завтра (первыми в очереди)
    2. Массовая отмена с возвратом средств
    3. Уведомление пациентов о переносе/отмене
    """
    
    TRANSFER_PRIORITY = 2  # Приоритет для перенесённых записей (выше обычного)
    
    def __init__(self, db: Session):
        self.db = db
        self.fcm_service = get_fcm_service()
    
    def get_pending_entries(
        self, 
        queue_id: Optional[int] = None,
        specialist_id: Optional[int] = None,
        target_date: Optional[date] = None
    ) -> List[OnlineQueueEntry]:
        """
        Получить записи в ожидании для переноса/отмены
        
        Args:
            queue_id: ID конкретной очереди
            specialist_id: ID специалиста
            target_date: Дата (по умолчанию сегодня)
        
        Returns:
            Список записей со статусами waiting, called, in_service, diagnostics
        """
        target_date = target_date or date.today()
        
        query = self.db.query(OnlineQueueEntry).join(DailyQueue)
        
        if queue_id:
            query = query.filter(OnlineQueueEntry.queue_id == queue_id)
        
        if specialist_id:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        
        query = query.filter(
            DailyQueue.day == target_date,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        )
        
        return query.order_by(OnlineQueueEntry.priority.desc(), OnlineQueueEntry.queue_time).all()
    
    def transfer_entries_to_tomorrow(
        self,
        entries: List[OnlineQueueEntry],
        specialist_id: int,
        reason: str,
        performed_by_id: int,
        send_notifications: bool = True
    ) -> Dict[str, Any]:
        """
        Массовый перенос записей на завтра
        
        Записи получают высокий приоритет (2) и будут первыми в очереди
        после утреннего распределения.
        
        Args:
            entries: Список записей для переноса
            specialist_id: ID специалиста
            reason: Причина переноса
            performed_by_id: ID пользователя, выполнившего перенос
            send_notifications: Отправить уведомления
        
        Returns:
            Результат операции с деталями
        """
        if not entries:
            return {
                "success": True,
                "transferred": 0,
                "message": "Нет записей для переноса"
            }
        
        tomorrow = date.today() + timedelta(days=1)
        
        # Получаем или создаём очередь на завтра
        tomorrow_queue = self._get_or_create_queue(specialist_id, tomorrow)
        
        transferred = []
        failed = []
        notification_targets = []
        
        # Получаем следующий номер в очереди на завтра
        next_number = self._get_next_queue_number(tomorrow_queue.id)
        
        for entry in entries:
            try:
                # Создаём новую запись на завтра
                new_entry = OnlineQueueEntry(
                    queue_id=tomorrow_queue.id,
                    number=next_number,
                    patient_id=entry.patient_id,
                    patient_name=entry.patient_name,
                    phone=entry.phone,
                    telegram_id=entry.telegram_id,
                    birth_year=entry.birth_year,
                    address=entry.address,
                    visit_id=entry.visit_id,
                    visit_type=entry.visit_type,
                    discount_mode=entry.discount_mode,
                    services=entry.services,
                    service_codes=entry.service_codes,
                    total_amount=entry.total_amount,
                    source="force_majeure_transfer",
                    status="waiting",
                    priority=self.TRANSFER_PRIORITY,  # Высокий приоритет
                    queue_time=datetime.utcnow()  # Новое время в очереди
                )
                
                self.db.add(new_entry)
                
                # Отмечаем старую запись как перенесённую
                entry.status = "cancelled"
                entry.incomplete_reason = f"Форс-мажор: {reason}"
                
                transferred.append({
                    "old_entry_id": entry.id,
                    "new_entry_id": None,  # Будет заполнено после flush
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "telegram_id": entry.telegram_id,
                    "new_number": next_number,
                    "new_date": str(tomorrow)
                })
                
                # Добавляем в список для уведомлений
                if entry.phone or entry.telegram_id:
                    notification_targets.append({
                        "phone": entry.phone,
                        "telegram_id": entry.telegram_id,
                        "patient_name": entry.patient_name,
                        "new_number": next_number,
                        "new_date": tomorrow
                    })
                
                next_number += 1
                
            except Exception as e:
                logger.error(f"Ошибка при переносе записи {entry.id}: {e}")
                failed.append({
                    "entry_id": entry.id,
                    "error": str(e)
                })
        
        self.db.flush()
        
        # Обновляем ID новых записей
        for i, item in enumerate(transferred):
            # ID будут присвоены после flush
            pass
        
        self.db.commit()
        
        # Отправляем уведомления
        if send_notifications and notification_targets:
            self._send_transfer_notifications(notification_targets, reason)
        
        logger.info(
            f"Форс-мажор перенос: {len(transferred)} записей перенесено на {tomorrow}, "
            f"{len(failed)} ошибок. Причина: {reason}"
        )
        
        return {
            "success": True,
            "transferred": len(transferred),
            "failed": len(failed),
            "new_date": str(tomorrow),
            "new_queue_id": tomorrow_queue.id,
            "details": transferred,
            "errors": failed,
            "reason": reason
        }
    
    def cancel_entries_with_refund(
        self,
        entries: List[OnlineQueueEntry],
        reason: str,
        refund_type: RefundType,
        performed_by_id: int,
        send_notifications: bool = True
    ) -> Dict[str, Any]:
        """
        Массовая отмена записей с возвратом средств
        
        Args:
            entries: Список записей для отмены
            reason: Причина отмены
            refund_type: Тип возврата (депозит или ручной возврат)
            performed_by_id: ID пользователя, выполнившего отмену
            send_notifications: Отправить уведомления
        
        Returns:
            Результат операции с деталями
        """
        if not entries:
            return {
                "success": True,
                "cancelled": 0,
                "message": "Нет записей для отмены"
            }
        
        cancelled = []
        failed = []
        refund_requests = []
        notification_targets = []
        
        for entry in entries:
            try:
                # Получаем связанный платёж
                payment = self._get_payment_for_entry(entry)
                
                # Отмечаем запись как отменённую
                entry.status = "cancelled"
                entry.incomplete_reason = f"Форс-мажор: {reason}"
                
                refund_info = None
                
                if payment and payment.status == "paid" and payment.amount > 0:
                    # Создаём заявку на возврат
                    if refund_type == RefundType.DEPOSIT:
                        refund_info = self._add_to_deposit(
                            patient_id=entry.patient_id,
                            amount=payment.amount,
                            reason=reason,
                            payment_id=payment.id,
                            visit_id=entry.visit_id,
                            performed_by_id=performed_by_id
                        )
                    else:
                        refund_info = self._create_refund_request(
                            patient_id=entry.patient_id,
                            payment_id=payment.id,
                            visit_id=entry.visit_id,
                            amount=payment.amount,
                            reason=reason,
                            refund_type=refund_type,
                            is_automatic=True
                        )
                        refund_requests.append(refund_info)
                
                cancelled.append({
                    "entry_id": entry.id,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "refund_type": refund_type.value if refund_type else None,
                    "refund_amount": float(payment.amount) if payment else 0,
                    "refund_info": refund_info
                })
                
                # Добавляем в список для уведомлений
                if entry.phone or entry.telegram_id:
                    notification_targets.append({
                        "phone": entry.phone,
                        "telegram_id": entry.telegram_id,
                        "patient_name": entry.patient_name,
                        "refund_type": refund_type.value if refund_type else None,
                        "refund_amount": float(payment.amount) if payment else 0
                    })
                
            except Exception as e:
                logger.error(f"Ошибка при отмене записи {entry.id}: {e}")
                failed.append({
                    "entry_id": entry.id,
                    "error": str(e)
                })
        
        self.db.commit()
        
        # Отправляем уведомления
        if send_notifications and notification_targets:
            self._send_cancellation_notifications(notification_targets, reason)
        
        logger.info(
            f"Форс-мажор отмена: {len(cancelled)} записей отменено, "
            f"{len(failed)} ошибок. Причина: {reason}"
        )
        
        return {
            "success": True,
            "cancelled": len(cancelled),
            "failed": len(failed),
            "refund_requests_created": len(refund_requests),
            "details": cancelled,
            "errors": failed,
            "reason": reason
        }
    
    def _get_or_create_queue(self, specialist_id: int, target_date: date) -> DailyQueue:
        """Получить или создать очередь на указанную дату"""
        queue = self.db.query(DailyQueue).filter(
            DailyQueue.specialist_id == specialist_id,
            DailyQueue.day == target_date
        ).first()
        
        if not queue:
            # Получаем информацию о специалисте
            doctor = self.db.query(Doctor).filter(Doctor.id == specialist_id).first()
            queue_tag = None
            if doctor and doctor.specialty:
                queue_tag = doctor.specialty.lower().replace(" ", "_")
            
            queue = DailyQueue(
                day=target_date,
                specialist_id=specialist_id,
                queue_tag=queue_tag,
                active=True
            )
            self.db.add(queue)
            self.db.flush()
        
        return queue
    
    def _get_next_queue_number(self, queue_id: int) -> int:
        """Получить следующий номер в очереди с учётом приоритета"""
        max_number = self.db.query(OnlineQueueEntry.number).filter(
            OnlineQueueEntry.queue_id == queue_id,
            OnlineQueueEntry.status != "cancelled"
        ).order_by(OnlineQueueEntry.number.desc()).first()
        
        return (max_number[0] + 1) if max_number else 1
    
    def _get_payment_for_entry(self, entry: OnlineQueueEntry) -> Optional[Payment]:
        """Получить платёж для записи"""
        if not entry.visit_id:
            return None
        
        return self.db.query(Payment).filter(
            Payment.visit_id == entry.visit_id,
            Payment.status == "paid"
        ).first()
    
    def _add_to_deposit(
        self,
        patient_id: int,
        amount: float,
        reason: str,
        payment_id: int,
        visit_id: Optional[int],
        performed_by_id: int
    ) -> Dict[str, Any]:
        """Добавить средства на депозит пациента"""
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        
        # Получаем или создаём депозит пациента
        deposit = self.db.query(PatientDeposit).filter(
            PatientDeposit.patient_id == patient_id
        ).first()
        
        if not deposit:
            deposit = PatientDeposit(
                patient_id=patient_id,
                balance=amount_decimal
            )
            self.db.add(deposit)
        else:
            deposit.balance += amount_decimal
        
        self.db.flush()
        
        # Создаём транзакцию
        transaction = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type=DepositTransactionType.CREDIT.value,
            amount=amount_decimal,
            balance_after=deposit.balance,
            description=f"Возврат (форс-мажор): {reason}",
            payment_id=payment_id,
            visit_id=visit_id,
            performed_by=performed_by_id
        )
        self.db.add(transaction)
        
        return {
            "type": "deposit",
            "deposit_id": deposit.id,
            "amount": float(amount_decimal),
            "new_balance": float(deposit.balance)
        }
    
    def _create_refund_request(
        self,
        patient_id: int,
        payment_id: int,
        visit_id: Optional[int],
        amount: float,
        reason: str,
        refund_type: RefundType,
        is_automatic: bool = False
    ) -> Dict[str, Any]:
        """Создать заявку на возврат"""
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        
        refund_request = RefundRequest(
            patient_id=patient_id,
            payment_id=payment_id,
            visit_id=visit_id,
            original_amount=amount_decimal,
            refund_amount=amount_decimal,
            commission_amount=Decimal("0"),
            refund_type=refund_type.value,
            status=RefundRequestStatus.PENDING.value,
            reason=reason,
            is_automatic=is_automatic
        )
        self.db.add(refund_request)
        self.db.flush()
        
        return {
            "type": "refund_request",
            "request_id": refund_request.id,
            "amount": float(amount_decimal),
            "status": refund_request.status
        }
    
    def _send_transfer_notifications(
        self, 
        targets: List[Dict[str, Any]], 
        reason: str
    ) -> None:
        """Отправить уведомления о переносе"""
        for target in targets:
            try:
                message = (
                    f"Уважаемый(ая) {target['patient_name']}!\n\n"
                    f"Ваша запись перенесена на {target['new_date'].strftime('%d.%m.%Y')}.\n"
                    f"Ваш новый номер в очереди: {target['new_number']}\n"
                    f"Вы будете одним из первых в очереди.\n\n"
                    f"Причина: {reason}\n\n"
                    f"Приносим извинения за неудобства."
                )
                
                # Отправка через Telegram
                if target.get('telegram_id'):
                    try:
                        # TODO: Интеграция с Telegram service
                        pass
                    except Exception as e:
                        logger.warning(f"Telegram notification failed: {e}")
                
                # Отправка Push уведомления
                # TODO: Получить FCM токен по patient_id и отправить
                
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")
    
    def _send_cancellation_notifications(
        self, 
        targets: List[Dict[str, Any]], 
        reason: str
    ) -> None:
        """Отправить уведомления об отмене"""
        for target in targets:
            try:
                refund_info = ""
                if target.get('refund_amount') and target['refund_amount'] > 0:
                    if target.get('refund_type') == 'deposit':
                        refund_info = (
                            f"\n💰 Средства ({target['refund_amount']:,.0f} UZS) "
                            f"зачислены на ваш депозит в клинике."
                        )
                    else:
                        refund_info = (
                            f"\n💰 Создана заявка на возврат ({target['refund_amount']:,.0f} UZS). "
                            f"С вами свяжется менеджер."
                        )
                
                message = (
                    f"Уважаемый(ая) {target['patient_name']}!\n\n"
                    f"К сожалению, ваша запись отменена.\n"
                    f"Причина: {reason}"
                    f"{refund_info}\n\n"
                    f"Приносим извинения за неудобства."
                )
                
                # Отправка через Telegram
                if target.get('telegram_id'):
                    try:
                        # TODO: Интеграция с Telegram service
                        pass
                    except Exception as e:
                        logger.warning(f"Telegram notification failed: {e}")
                
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")


# Factory function
def get_force_majeure_service(db: Session) -> ForceMajeureService:
    """Получить экземпляр сервиса форс-мажора"""
    return ForceMajeureService(db)
