"""
Lab Results Auto-Notification Service
Сервис автоматических уведомлений о готовности анализов
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.lab import LabOrder, LabResult
from app.models.patient import Patient
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class LabNotificationService:
    """
    Сервис автоматических уведомлений о результатах анализов
    
    Функции:
    - Уведомление пациента о готовности результатов
    - Уведомление врача о критических значениях
    - Напоминание о повторных анализах
    - Уведомление о просроченных результатах
    """
    
    # Критические значения для основных показателей
    CRITICAL_VALUES = {
        "glucose": {"low": 3.0, "high": 20.0, "unit": "mmol/L"},
        "hemoglobin": {"low": 70, "high": 200, "unit": "g/L"},
        "potassium": {"low": 2.5, "high": 6.5, "unit": "mmol/L"},
        "sodium": {"low": 120, "high": 160, "unit": "mmol/L"},
        "creatinine": {"low": 20, "high": 500, "unit": "umol/L"},
        "wbc": {"low": 2.0, "high": 30.0, "unit": "10^9/L"},
        "platelets": {"low": 50, "high": 1000, "unit": "10^9/L"},
        "inr": {"low": 0.5, "high": 5.0, "unit": ""},
    }
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)
    
    async def check_and_notify_ready_results(self) -> Dict[str, Any]:
        """
        Проверяет готовые результаты и отправляет уведомления пациентам
        
        Returns:
            Статистика отправленных уведомлений
        """
        try:
            # Находим готовые результаты без уведомления
            ready_orders = (
                self.db.query(LabOrder)
                .filter(
                    LabOrder.status == "completed",
                    or_(
                        LabOrder.notification_sent == False,
                        LabOrder.notification_sent.is_(None),
                    ),
                )
                .all()
            )
            
            notifications_sent = 0
            errors = []
            
            for order in ready_orders:
                try:
                    await self._notify_patient_results_ready(order)
                    order.notification_sent = True
                    order.notification_sent_at = datetime.utcnow()
                    notifications_sent += 1
                except Exception as e:
                    errors.append({"order_id": order.id, "error": str(e)})
            
            self.db.commit()
            
            return {
                "total_checked": len(ready_orders),
                "notifications_sent": notifications_sent,
                "errors": errors,
            }
            
        except Exception as e:
            logger.error(f"Error checking ready results: {e}")
            return {"error": str(e)}
    
    async def _notify_patient_results_ready(self, order: LabOrder):
        """Отправляет уведомление пациенту о готовности результатов"""
        patient = self.db.query(Patient).filter(Patient.id == order.patient_id).first()
        
        if not patient:
            return
        
        # Получаем пользователя пациента
        user = None
        if patient.user_id:
            user = self.db.query(User).filter(User.id == patient.user_id).first()
        
        message = f"""
✅ Результаты анализов готовы!

Уважаемый(ая) {patient.short_name()},

Ваши результаты лабораторных исследований готовы.
Номер заказа: {order.id}
Дата забора: {order.created_at.strftime('%d.%m.%Y')}

Вы можете просмотреть результаты в личном кабинете или получить их в регистратуре клиники.

С уважением,
Ваша клиника
        """.strip()
        
        # Отправляем через доступные каналы
        if user and hasattr(user, 'telegram_id') and user.telegram_id:
            await self.notification_service.send_telegram_message(
                user_id=user.telegram_id,
                message=message,
            )
        
        # SMS если есть телефон
        if patient.phone:
            short_message = f"Ваши анализы готовы! Заказ #{order.id}. Просмотр в личном кабинете."
            # await self.notification_service.send_sms(patient.phone, short_message)
        
        logger.info(f"Notification sent for order {order.id} to patient {patient.id}")
    
    async def check_critical_values(self) -> Dict[str, Any]:
        """
        Проверяет результаты на критические значения и уведомляет врачей
        
        Returns:
            Список критических результатов
        """
        try:
            # Находим результаты за последние 24 часа
            yesterday = datetime.utcnow() - timedelta(hours=24)
            
            recent_results = (
                self.db.query(LabResult)
                .filter(
                    LabResult.created_at >= yesterday,
                    or_(
                        LabResult.critical_notified == False,
                        LabResult.critical_notified.is_(None),
                    ),
                )
                .all()
            )
            
            critical_found = []
            
            for result in recent_results:
                # Проверяем на критические значения
                test_name = result.test_name.lower() if result.test_name else ""
                
                for marker, thresholds in self.CRITICAL_VALUES.items():
                    if marker in test_name:
                        try:
                            value = float(result.value)
                            if value < thresholds["low"] or value > thresholds["high"]:
                                critical_found.append({
                                    "result_id": result.id,
                                    "patient_id": result.patient_id,
                                    "test_name": result.test_name,
                                    "value": value,
                                    "unit": thresholds["unit"],
                                    "is_low": value < thresholds["low"],
                                    "is_high": value > thresholds["high"],
                                })
                                
                                # Уведомляем врача
                                await self._notify_doctor_critical_value(result, value, thresholds)
                                
                                result.critical_notified = True
                                result.critical_notified_at = datetime.utcnow()
                        except (ValueError, TypeError):
                            pass
            
            self.db.commit()
            
            return {
                "checked": len(recent_results),
                "critical_found": len(critical_found),
                "critical_results": critical_found,
            }
            
        except Exception as e:
            logger.error(f"Error checking critical values: {e}")
            return {"error": str(e)}
    
    async def _notify_doctor_critical_value(
        self,
        result: LabResult,
        value: float,
        thresholds: dict,
    ):
        """Уведомляет врача о критическом значении"""
        # Получаем назначившего врача
        order = self.db.query(LabOrder).filter(LabOrder.id == result.order_id).first()
        if not order or not order.doctor_id:
            return
        
        patient = self.db.query(Patient).filter(Patient.id == result.patient_id).first()
        
        alert_type = "⬇️ КРИТИЧЕСКИ НИЗКОЕ" if value < thresholds["low"] else "⬆️ КРИТИЧЕСКИ ВЫСОКОЕ"
        
        message = f"""
🚨 КРИТИЧЕСКОЕ ЗНАЧЕНИЕ!

{alert_type} значение:

📊 Показатель: {result.test_name}
📈 Значение: {value} {thresholds.get('unit', '')}
📉 Норма: {thresholds['low']} - {thresholds['high']}

👤 Пациент: {patient.short_name() if patient else f'ID {result.patient_id}'}

Требуется срочное внимание!
        """.strip()
        
        # Отправляем врачу
        doctor_user = self.db.query(User).filter(User.id == order.doctor_id).first()
        if doctor_user and hasattr(doctor_user, 'telegram_id') and doctor_user.telegram_id:
            await self.notification_service.send_telegram_message(
                user_id=doctor_user.telegram_id,
                message=message,
            )
        
        logger.warning(f"Critical value alert sent for result {result.id}")
    
    async def send_follow_up_reminders(self, days_before: int = 3) -> Dict[str, Any]:
        """
        Отправляет напоминания о повторных анализах
        
        Args:
            days_before: За сколько дней до даты напоминать
            
        Returns:
            Статистика отправленных напоминаний
        """
        try:
            target_date = datetime.utcnow() + timedelta(days=days_before)
            
            # Находим заказы с датой повторного анализа
            upcoming_followups = (
                self.db.query(LabOrder)
                .filter(
                    LabOrder.follow_up_date.isnot(None),
                    LabOrder.follow_up_date >= datetime.utcnow(),
                    LabOrder.follow_up_date <= target_date,
                    or_(
                        LabOrder.follow_up_reminded == False,
                        LabOrder.follow_up_reminded.is_(None),
                    ),
                )
                .all()
            )
            
            reminders_sent = 0
            
            for order in upcoming_followups:
                patient = self.db.query(Patient).filter(Patient.id == order.patient_id).first()
                
                if patient:
                    days_until = (order.follow_up_date - datetime.utcnow()).days
                    
                    message = f"""
📅 Напоминание о повторном анализе

Уважаемый(ая) {patient.short_name()},

Напоминаем, что через {days_until} дней ({order.follow_up_date.strftime('%d.%m.%Y')}) вам необходимо сдать повторный анализ.

Пожалуйста, запишитесь на приём заранее.

С уважением,
Ваша клиника
                    """.strip()
                    
                    # Отправляем напоминание
                    if patient.user_id:
                        user = self.db.query(User).filter(User.id == patient.user_id).first()
                        if user and hasattr(user, 'telegram_id') and user.telegram_id:
                            await self.notification_service.send_telegram_message(
                                user_id=user.telegram_id,
                                message=message,
                            )
                            reminders_sent += 1
                    
                    order.follow_up_reminded = True
                    order.follow_up_reminded_at = datetime.utcnow()
            
            self.db.commit()
            
            return {
                "upcoming_followups": len(upcoming_followups),
                "reminders_sent": reminders_sent,
            }
            
        except Exception as e:
            logger.error(f"Error sending follow-up reminders: {e}")
            return {"error": str(e)}


async def run_lab_notifications(db: Session) -> Dict[str, Any]:
    """
    Запускает все проверки уведомлений по анализам
    Может использоваться в cron job или scheduled task
    """
    service = LabNotificationService(db)
    
    results = {
        "ready_results": await service.check_and_notify_ready_results(),
        "critical_values": await service.check_critical_values(),
        "follow_up_reminders": await service.send_follow_up_reminders(),
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(f"Lab notifications run completed: {results}")
    return results
