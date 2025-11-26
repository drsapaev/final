"""
Сервис для интеграции уведомлений регистратуры
Централизованная система для отправки уведомлений регистраторам
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.user import User
from app.models.visit import Visit, VisitService
from app.models.patient import Patient
from app.models.clinic import Doctor
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.online_queue import OnlineQueueEntry, DailyQueue
from app.models.doctor_price_override import DoctorPriceOverride
from app.services.telegram.bot import TelegramBotService
from app.services.notification_service import NotificationService
from app.services.email_sms_enhanced import EmailSMSEnhancedService
from app.services.doctor_info_service import get_doctor_info_service
from app.core.config import settings

logger = logging.getLogger(__name__)

class RegistrarNotificationService:
    """Централизованный сервис уведомлений для регистратуры"""
    
    def __init__(self, db: Session):
        self.db = db
        self.telegram_service = TelegramBotService()
        self.notification_service = NotificationService(db)
        self.email_sms_service = EmailSMSEnhancedService()
        self.doctor_info_service = get_doctor_info_service(db)
    
    # ===================== ПОЛУЧЕНИЕ РЕГИСТРАТОРОВ =====================
    
    def get_active_registrars(self) -> List[User]:
        """Получает список активных регистраторов"""
        return self.db.query(User).filter(
            and_(
                User.role == "Registrar",
                User.is_active == True
            )
        ).all()
    
    def get_registrars_by_department(self, department: str = None) -> List[User]:
        """Получает регистраторов по отделению"""
        query = self.db.query(User).filter(
            and_(
                User.role == "Registrar",
                User.is_active == True
            )
        )
        
        # Если указано отделение, фильтруем по нему
        if department:
            # Здесь можно добавить логику фильтрации по отделениям
            # Пока возвращаем всех регистраторов
            pass
        
        return query.all()
    
    # ===================== УВЕДОМЛЕНИЯ О ЗАПИСЯХ =====================
    
    async def notify_new_appointment(
        self, 
        appointment: Union[Appointment, Visit], 
        patient: Patient,
        services: List[Service] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Уведомляет регистраторов о новой записи"""
        try:
            registrars = self.get_active_registrars()
            if not registrars:
                logger.warning("Нет активных регистраторов для уведомления")
                return {"success": False, "error": "Нет активных регистраторов"}
            
            # Определяем тип записи
            appointment_type = "Визит" if isinstance(appointment, Visit) else "Запись"
            
            # Получаем информацию о враче
            doctor_info = None
            doctor_name = "Не назначен"
            department_name = "Не указано"
            
            if hasattr(appointment, 'doctor_id') and appointment.doctor_id:
                doctor_info = self.doctor_info_service.get_doctor_full_info(appointment.doctor_id)
                doctor_name = self.doctor_info_service.format_doctor_info_for_notification(doctor_info)
                department_name = doctor_info.get("department", "Не указано")
            
            # Получаем услуги
            services_text = "Не указаны"
            total_amount = 0
            if services:
                services_list = []
                for service in services:
                    services_list.append(f"• {service.name} ({service.code})")
                    total_amount += float(service.price) if service.price else 0
                services_text = "\n".join(services_list)
            elif isinstance(appointment, Visit):
                visit_services = self.db.query(VisitService).filter(VisitService.visit_id == appointment.id).all()
                if visit_services:
                    services_list = []
                    for vs in visit_services:
                        services_list.append(f"• {vs.name}")
                        total_amount += float(vs.price) if vs.price else 0
                    services_text = "\n".join(services_list)
            
            # Формируем сообщение
            priority_emoji = "🔴" if priority == "urgent" else "🟡" if priority == "high" else "🟢"
            
            message = f"""
{priority_emoji} НОВАЯ ЗАПИСЬ В КЛИНИКЕ

📋 Тип: {appointment_type}
👤 Пациент: {patient.full_name}
📞 Телефон: {patient.phone or 'Не указан'}
👨‍⚕️ Врач: {doctor_name}
🏥 Отделение: {department_name}
📅 Дата: {appointment.appointment_date.strftime('%d.%m.%Y') if hasattr(appointment, 'appointment_date') else 'Не указана'}
⏰ Время: {appointment.appointment_time.strftime('%H:%M') if hasattr(appointment, 'appointment_time') else 'Не указано'}

🔧 Услуги:
{services_text}

💰 Сумма: {total_amount} сум
🔄 Статус: {appointment.status if hasattr(appointment, 'status') else 'Новая'}

⏰ Создано: {datetime.now().strftime('%d.%m.%Y %H:%M')}
            """.strip()
            
            # Отправляем уведомления
            results = []
            for registrar in registrars:
                result = await self._send_notification_to_registrar(
                    registrar, message, "new_appointment"
                )
                results.append(result)
            
            return {
                "success": True,
                "message": f"Уведомления отправлены {len(registrars)} регистраторам",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о новой записи: {e}")
            return {"success": False, "error": str(e)}
    
    # ===================== УВЕДОМЛЕНИЯ О ЦЕНАХ =====================
    
    async def notify_price_change(
        self,
        price_override: DoctorPriceOverride,
        doctor: Doctor,
        service: Service,
        visit: Visit = None,
        patient: Patient = None
    ) -> Dict[str, Any]:
        """Уведомляет регистраторов об изменении цены"""
        try:
            registrars = self.get_active_registrars()
            if not registrars:
                logger.warning("Нет активных регистраторов для уведомления об изменении цены")
                return {"success": False, "error": "Нет активных регистраторов"}
            
            # Получаем полную информацию о враче
            doctor_info = self.doctor_info_service.get_doctor_full_info(doctor.id)
            doctor_name = self.doctor_info_service.format_doctor_info_for_notification(doctor_info)
            department_name = doctor_info.get("department", "Не указано")
            
            # Формируем информацию о пациенте
            patient_info = "Неизвестный пациент"
            if patient:
                patient_info = f"{patient.full_name} ({patient.phone or 'без телефона'})"
            elif visit:
                patient = self.db.query(Patient).filter(Patient.id == visit.patient_id).first()
                if patient:
                    patient_info = f"{patient.full_name} ({patient.phone or 'без телефона'})"
            
            message = f"""
🦷 ИЗМЕНЕНИЕ ЦЕНЫ ВРАЧОМ

👨‍⚕️ Врач: {doctor_name}
🏥 Отделение: {department_name}
👤 Пациент: {patient_info}
🔧 Услуга: {service.name} ({service.code})
💰 Цена: {price_override.original_price} → {price_override.new_price} сум
📝 Причина: {price_override.reason}
{f"📋 Детали: {price_override.details}" if price_override.details else ""}

⏰ Время: {price_override.created_at.strftime('%d.%m.%Y %H:%M')}
🔄 Статус: Ожидает одобрения

Для одобрения/отклонения перейдите в панель регистратора.
            """.strip()
            
            # Отправляем уведомления
            results = []
            for registrar in registrars:
                result = await self._send_notification_to_registrar(
                    registrar, message, "price_change"
                )
                results.append(result)
            
            # Обновляем статус уведомления
            price_override.notification_sent = True
            price_override.notification_sent_at = datetime.utcnow()
            self.db.commit()
            
            return {
                "success": True,
                "message": f"Уведомления об изменении цены отправлены {len(registrars)} регистраторам",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об изменении цены: {e}")
            return {"success": False, "error": str(e)}
    
    # ===================== УВЕДОМЛЕНИЯ ОБ ОЧЕРЕДИ =====================
    
    async def notify_queue_status(
        self,
        queue_entry: OnlineQueueEntry,
        status_change: str,
        additional_info: str = None
    ) -> Dict[str, Any]:
        """Уведомляет регистраторов о статусе очереди"""
        try:
            registrars = self.get_active_registrars()
            if not registrars:
                return {"success": False, "error": "Нет активных регистраторов"}
            
            # Получаем информацию о пациенте
            patient_info = f"Пациент #{queue_entry.patient_id}"
            if queue_entry.patient_name:
                patient_info = queue_entry.patient_name
            
            # Получаем информацию об очереди
            daily_queue = self.db.query(DailyQueue).filter(DailyQueue.id == queue_entry.queue_id).first()
            queue_info = f"Очередь #{queue_entry.queue_id}"
            department_name = "Не указано"
            doctor_name = "Не назначен"
            
            if daily_queue:
                department_name = daily_queue.department or "Не указано"
                
                # Получаем реальную информацию о враче
                if daily_queue.doctor_id:
                    doctor_info = self.doctor_info_service.get_doctor_full_info(daily_queue.doctor_id)
                    doctor_name = self.doctor_info_service.format_doctor_info_for_notification(doctor_info)
                    department_name = doctor_info.get("department", department_name)
                else:
                    doctor_name = daily_queue.doctor_name or "Не назначен"
                
                queue_info = f"{department_name} - {doctor_name}"
            
            status_messages = {
                "joined": "🟢 Присоединился к очереди",
                "confirmed": "✅ Подтвердил визит",
                "cancelled": "❌ Отменил визит",
                "no_show": "⚠️ Не явился",
                "completed": "✅ Визит завершен"
            }
            
            status_text = status_messages.get(status_change, f"Статус изменен: {status_change}")
            
            message = f"""
📋 ИЗМЕНЕНИЕ СТАТУСА ОЧЕРЕДИ

{status_text}

👤 {patient_info}
🏥 {queue_info}
🎫 Номер: {queue_entry.queue_number or 'Не назначен'}
📅 Дата: {queue_entry.visit_date.strftime('%d.%m.%Y') if queue_entry.visit_date else 'Не указана'}
⏰ Время: {datetime.now().strftime('%H:%M')}

{f"ℹ️ Дополнительно: {additional_info}" if additional_info else ""}
            """.strip()
            
            # Отправляем уведомления
            results = []
            for registrar in registrars:
                result = await self._send_notification_to_registrar(
                    registrar, message, "queue_status"
                )
                results.append(result)
            
            return {
                "success": True,
                "message": f"Уведомления о статусе очереди отправлены {len(registrars)} регистраторам",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о статусе очереди: {e}")
            return {"success": False, "error": str(e)}
    
    # ===================== СИСТЕМНЫЕ УВЕДОМЛЕНИЯ =====================
    
    async def notify_system_alert(
        self,
        alert_type: str,
        message: str,
        priority: str = "normal",
        department: str = None
    ) -> Dict[str, Any]:
        """Отправляет системные уведомления регистраторам"""
        try:
            registrars = self.get_registrars_by_department(department)
            if not registrars:
                return {"success": False, "error": "Нет активных регистраторов"}
            
            priority_emoji = "🔴" if priority == "critical" else "🟡" if priority == "warning" else "ℹ️"
            alert_emojis = {
                "system_error": "⚠️",
                "payment_issue": "💳",
                "queue_overflow": "📊",
                "equipment_failure": "🔧",
                "security_alert": "🔒",
                "maintenance": "🛠️"
            }
            
            alert_emoji = alert_emojis.get(alert_type, "📢")
            
            formatted_message = f"""
{priority_emoji} СИСТЕМНОЕ УВЕДОМЛЕНИЕ

{alert_emoji} Тип: {alert_type.replace('_', ' ').title()}
📝 Сообщение: {message}
⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}
{f"🏥 Отделение: {department}" if department else ""}

Требуется внимание регистратуры.
            """.strip()
            
            # Отправляем уведомления
            results = []
            for registrar in registrars:
                result = await self._send_notification_to_registrar(
                    registrar, formatted_message, "system_alert"
                )
                results.append(result)
            
            return {
                "success": True,
                "message": f"Системные уведомления отправлены {len(registrars)} регистраторам",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Ошибка отправки системного уведомления: {e}")
            return {"success": False, "error": str(e)}
    
    # ===================== ЕЖЕДНЕВНЫЕ ОТЧЕТЫ =====================
    
    async def send_daily_summary(self, target_date: date = None) -> Dict[str, Any]:
        """Отправляет ежедневную сводку регистраторам"""
        try:
            if not target_date:
                target_date = date.today()
            
            registrars = self.get_active_registrars()
            if not registrars:
                return {"success": False, "error": "Нет активных регистраторов"}
            
            # Собираем статистику за день
            stats = await self._collect_daily_stats(target_date)
            
            message = f"""
📊 ЕЖЕДНЕВНАЯ СВОДКА - {target_date.strftime('%d.%m.%Y')}

👥 Пациенты:
• Всего записей: {stats['total_appointments']}
• Новые пациенты: {stats['new_patients']}
• Подтвержденные визиты: {stats['confirmed_visits']}
• Отмененные: {stats['cancelled_appointments']}

💰 Финансы:
• Общая сумма: {stats['total_revenue']} сум
• Оплачено: {stats['paid_amount']} сум
• К доплате: {stats['pending_amount']} сум

🏥 Очереди:
• Активные очереди: {stats['active_queues']}
• Онлайн записи: {stats['online_entries']}
• Средняя загрузка: {stats['average_load']}%

⚠️ Требует внимания:
• Неподтвержденные визиты: {stats['unconfirmed_visits']}
• Изменения цен: {stats['pending_price_changes']}
• Системные ошибки: {stats['system_errors']}

📈 Сравнение с вчера: {stats['comparison_text']}

Хорошего рабочего дня! 🌟
            """.strip()
            
            # Отправляем сводку
            results = []
            for registrar in registrars:
                result = await self._send_notification_to_registrar(
                    registrar, message, "daily_summary"
                )
                results.append(result)
            
            return {
                "success": True,
                "message": f"Ежедневная сводка отправлена {len(registrars)} регистраторам",
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Ошибка отправки ежедневной сводки: {e}")
            return {"success": False, "error": str(e)}
    
    # ===================== УВЕДОМЛЕНИЯ О НАЗНАЧЕННЫХ УСЛУГАХ =====================
    
    async def notify_services_assigned(
        self,
        appointment: Appointment,
        services: List[Any],
        doctor: User,
        department: str = None
    ) -> Dict[str, Any]:
        """
        Уведомляет регистраторов о назначенных услугах
        
        Args:
            appointment: Запись на прием
            services: Список назначенных услуг
            doctor: Врач, который назначил услуги
            department: Отделение (опционально)
        """
        try:
            # Получаем список регистраторов
            if department:
                registrars = self.get_registrars_by_department(department)
            else:
                registrars = self.get_active_registrars()
            
            if not registrars:
                logger.warning("Нет активных регистраторов для отправки уведомления")
                return {"success": False, "error": "Нет активных регистраторов"}
            
            # Получаем информацию о пациенте
            patient = self.db.query(Patient).filter(Patient.id == appointment.patient_id).first()
            patient_name = patient.name if patient else f"Пациент ID: {appointment.patient_id}"
            
            # Формируем сообщение
            services_text = "\n".join([
                f"  • {service.name} - {service.price:.0f} сум (x{service.quantity})"
                for service in services
            ])
            
            total_price = sum(service.price * service.quantity for service in services)
            
            message = f"""
🏥 НОВЫЕ НАЗНАЧЕННЫЕ УСЛУГИ

📋 Пациент: {patient_name}
👨‍⚕️ Врач: {doctor.full_name if hasattr(doctor, 'full_name') else doctor.username}
📅 Дата записи: {appointment.appointment_date}
🕐 Время: {appointment.appointment_time or 'Не указано'}

💰 Назначенные услуги:
{services_text}

💵 Итого: {total_price:.0f} сум

⚠️ Требуется добавить услуги в регистратуре и произвести оплату.

📎 ID записи: {appointment.id}
            """.strip()
            
            results = []
            for registrar in registrars:
                try:
                    result = await self._send_notification_to_registrar(
                        registrar=registrar,
                        message=message,
                        notification_type="services_assigned"
                    )
                    results.append({
                        "registrar_id": registrar.id,
                        "registrar_name": registrar.full_name if hasattr(registrar, 'full_name') else registrar.username,
                        **result
                    })
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления регистратору {registrar.id}: {e}")
                    results.append({
                        "registrar_id": registrar.id,
                        "success": False,
                        "error": str(e)
                    })
            
            success_count = sum(1 for r in results if r.get("success", False))
            
            return {
                "success": True,
                "message": f"Уведомление отправлено {success_count} из {len(registrars)} регистраторов",
                "results": results,
                "appointment_id": appointment.id,
                "patient_name": patient_name,
                "doctor_name": doctor.full_name if hasattr(doctor, 'full_name') else doctor.username,
                "services_count": len(services),
                "total_price": total_price
            }
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомлений о назначенных услугах: {e}")
            return {"success": False, "error": str(e)}
    
    # ===================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====================
    
    async def _send_notification_to_registrar(
        self, 
        registrar: User, 
        message: str, 
        notification_type: str
    ) -> Dict[str, Any]:
        """Отправляет уведомление конкретному регистратору"""
        try:
            results = {"telegram": False, "email": False, "sms": False}
            
            # Проверяем настройки уведомлений пользователя
            notification_settings = getattr(registrar, 'notification_settings', None)
            
            # Отправляем через Telegram
            if hasattr(registrar, 'telegram_id') and registrar.telegram_id:
                try:
                    await self.telegram_service.send_message(
                        user_id=registrar.telegram_id,
                        text=message
                    )
                    results["telegram"] = True
                except Exception as e:
                    logger.error(f"Ошибка отправки Telegram уведомления регистратору {registrar.id}: {e}")
            
            # Отправляем email (если включено в настройках)
            if (registrar.email and 
                notification_settings and 
                getattr(notification_settings, 'email_system_updates', True)):
                try:
                    await self.email_sms_service.send_email(
                        to_email=registrar.email,
                        subject=f"Уведомление регистратуры - {notification_type}",
                        body=message,
                        is_html=False
                    )
                    results["email"] = True
                except Exception as e:
                    logger.error(f"Ошибка отправки email уведомления регистратору {registrar.id}: {e}")
            
            # Отправляем SMS для критических уведомлений
            if (notification_type in ["system_alert", "price_change"] and 
                hasattr(registrar, 'phone') and registrar.phone and
                notification_settings and 
                getattr(notification_settings, 'sms_emergency', True)):
                try:
                    # Сокращаем сообщение для SMS
                    sms_message = message[:160] + "..." if len(message) > 160 else message
                    await self.email_sms_service.send_sms(
                        phone_number=registrar.phone,
                        message=sms_message
                    )
                    results["sms"] = True
                except Exception as e:
                    logger.error(f"Ошибка отправки SMS уведомления регистратору {registrar.id}: {e}")
            
            return {
                "success": any(results.values()),
                "registrar_id": registrar.id,
                "channels": results
            }
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления регистратору {registrar.id}: {e}")
            return {
                "success": False,
                "registrar_id": registrar.id,
                "error": str(e)
            }
    
    async def _collect_daily_stats(self, target_date: date) -> Dict[str, Any]:
        """Собирает статистику за день"""
        try:
            # Базовая статистика (заглушки, можно расширить)
            stats = {
                "total_appointments": 0,
                "new_patients": 0,
                "confirmed_visits": 0,
                "cancelled_appointments": 0,
                "total_revenue": 0,
                "paid_amount": 0,
                "pending_amount": 0,
                "active_queues": 0,
                "online_entries": 0,
                "average_load": 0,
                "unconfirmed_visits": 0,
                "pending_price_changes": 0,
                "system_errors": 0,
                "comparison_text": "Данные обновляются"
            }
            
            # Подсчет записей за день
            from app.models.appointment import Appointment
            appointments_count = self.db.query(Appointment).filter(
                Appointment.appointment_date == target_date
            ).count()
            stats["total_appointments"] = appointments_count
            
            # Подсчет визитов за день
            visits_count = self.db.query(Visit).filter(
                Visit.visit_date == target_date
            ).count()
            stats["total_appointments"] += visits_count
            
            # Подсчет активных очередей
            active_queues_count = self.db.query(DailyQueue).filter(
                DailyQueue.queue_date == target_date
            ).count()
            stats["active_queues"] = active_queues_count
            
            # Подсчет онлайн записей
            online_entries_count = self.db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_date == target_date
            ).count()
            stats["online_entries"] = online_entries_count
            
            # Подсчет ожидающих изменений цен
            pending_price_changes = self.db.query(DoctorPriceOverride).filter(
                DoctorPriceOverride.status == "pending"
            ).count()
            stats["pending_price_changes"] = pending_price_changes
            
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка сбора статистики за день: {e}")
            # Возвращаем базовую статистику в случае ошибки
            return {
                "total_appointments": 0,
                "new_patients": 0,
                "confirmed_visits": 0,
                "cancelled_appointments": 0,
                "total_revenue": 0,
                "paid_amount": 0,
                "pending_amount": 0,
                "active_queues": 0,
                "online_entries": 0,
                "average_load": 0,
                "unconfirmed_visits": 0,
                "pending_price_changes": 0,
                "system_errors": 0,
                "comparison_text": "Ошибка сбора данных"
            }


# Глобальный экземпляр сервиса
def get_registrar_notification_service(db: Session) -> RegistrarNotificationService:
    """Получить экземпляр сервиса уведомлений регистратуры"""
    return RegistrarNotificationService(db)
