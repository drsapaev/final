import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Union

import httpx
from jinja2 import Template
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.notification import (
    crud_notification_history,
    crud_notification_template,
)
from app.crud.user_management import user_notification_settings as crud_user_notification_settings
from app.models.notification import NotificationHistory
from app.schemas.notification import NotificationHistoryCreate
from app.models.notification import NotificationHistory
from app.schemas.notification import NotificationHistoryCreate
from app.services.telegram.bot import telegram_bot
from app.services.fcm_service import get_fcm_service
from app.models.user import User
from app.services.notification_websocket import get_notification_ws_manager

logger = logging.getLogger(__name__)


class NotificationSenderService:
    """Сервис для отправки уведомлений (Email, SMS, Telegram)"""

    def __init__(self):
        self.smtp_server = getattr(settings, "SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "SMTP_USERNAME", None)
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", None)

        self.telegram_bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        self.telegram_chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)

        self.sms_api_key = getattr(settings, "SMS_API_KEY", None)
        self.sms_api_url = getattr(settings, "SMS_API_URL", None)
        
        # Интеграция с Telegram ботом
        self.telegram_bot = telegram_bot
        
        # Интеграция с FCM
        self.fcm_service = get_fcm_service()

    async def send_email(
        self, to_email: str, subject: str, body: str, html_body: Optional[str] = None
    ) -> bool:
        """Отправка email уведомления"""
        if not all([self.smtp_username, self.smtp_password]):
            logger.warning("SMTP credentials не настроены")
            return False

        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._send_email_sync, to_email, subject, body, html_body
        )

    def _send_email_sync(
        self, to_email: str, subject: str, body: str, html_body: Optional[str] = None
    ) -> bool:
        """Синхронная отправка email (для запуска в executor)"""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.smtp_username
            msg["To"] = to_email
            msg["Subject"] = subject

            # Добавляем текстовую версию
            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)

            # Добавляем HTML версию, если есть
            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                msg.attach(html_part)

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)

            # Отправляем письмо
            server.send_message(msg)
            server.quit()

            logger.info(f"Email отправлен на {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return False

    async def send_telegram(self, message: str, chat_id: Optional[str] = None) -> bool:
        """Отправка уведомления в Telegram"""
        if not self.telegram_bot_token:
            logger.warning("Telegram bot token не настроен")
            return False

        chat_id = chat_id or self.telegram_chat_id
        if not chat_id:
            logger.warning("Telegram chat ID не настроен")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, timeout=10)
                response.raise_for_status()

            logger.info(f"Telegram уведомление отправлено в чат {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки Telegram: {e}")
            return False

    async def send_sms(self, phone: str, message: str) -> bool:
        """Отправка SMS уведомления"""
        try:
            from app.services.sms_providers import get_sms_manager
            
            sms_manager = get_sms_manager()
            response = await sms_manager.send_sms(phone, message)
            
            if response.success:
                logger.info(f"SMS отправлено на {phone} через {response.provider}")
                return True
            else:
                logger.error(f"Ошибка отправки SMS ({response.provider}): {response.error}")
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки SMS: {e}")
            return False

    async def send_push(
        self,
        user_id: int,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> bool:
        """Отправка Push-уведомления (Mobile + WebSocket)"""
        try:
            # --- WebSocket Integration ---
            # Attempt to send to connected WebSocket client (In-App Notification)
            # We try this regardless of DB/User presence if we have user_id, 
            # but user_id is integer so we can try.
            try:
                ws_manager = get_notification_ws_manager()
                ws_payload = {
                    "type": "notification",
                    "title": title,
                    "message": message,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await ws_manager.send_json(ws_payload, user_id)
            except Exception as ws_e:
                logger.warning(f"Failed to send WebSocket notification to user {user_id}: {ws_e}")
            # -----------------------------

            # Если передан db, пытаемся отправить Mobile Push и сохранить историю
            if db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return False
                
                # Сохраняем в историю
                try:
                    notification_data = {
                        "recipient_type": "patient", # Предполагаем пациента
                        "recipient_id": user_id,
                        "recipient_contact": "mobile_app",
                        "notification_type": data.get("type", "push") if data else "push",
                        "channel": "mobile",
                        "subject": title,
                        "content": message,
                        "status": "sent",
                    }
                    crud_notification_history.create(db, obj_in=NotificationHistoryCreate(**notification_data))
                except Exception as hist_e:
                    logger.error(f"Failed to save notification history: {hist_e}")

                # Отправляем FCM только если есть токен
                if user.device_token:
                    await self.fcm_service.send_notification(
                        device_token=user.device_token,
                        title=title,
                        body=message,
                        data=data or {},
                    )
            
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки Push: {e}")
            return False

    async def send_appointment_reminder(
        self,
        patient_email: str,
        patient_phone: str,
        appointment_date: datetime,
        doctor_name: str,
        department: str,
    ) -> Dict[str, bool]:
        """Отправка напоминания о записи"""
        subject = "Напоминание о записи к врачу"

        # Формируем сообщения
        email_body = f"""
        Здравствуйте!
        
        Напоминаем о записи к врачу {doctor_name} в отделении {department}.
        Дата и время: {appointment_date.strftime('%d.%m.%Y в %H:%M')}
        
        Пожалуйста, не забудьте взять с собой документы и прийти за 10 минут до приёма.
        
        С уважением,
        Администрация клиники
        """

        sms_message = f"Напоминание: запись к {doctor_name} {appointment_date.strftime('%d.%m в %H:%M')}"

        telegram_message = f"""
        📅 <b>Напоминание о записи</b>
        
        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        👨‍⚕️ Врач: {doctor_name}
        🏥 Отделение: {department}
        📅 Дата: {appointment_date.strftime('%d.%m.%Y в %H:%M')}
        """

        # Отправляем уведомления
        results = {}

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        results["telegram"] = await self.send_telegram(telegram_message)

        return results

    async def send_visit_confirmation(
        self,
        patient_email: str,
        patient_phone: str,
        visit_date: datetime,
        doctor_name: str,
        department: str,
        queue_number: Optional[int] = None,
    ) -> Dict[str, bool]:
        """Отправка подтверждения визита"""
        subject = "Подтверждение визита к врачу"

        email_body = f"""
        Здравствуйте!
        
        Ваш визит к врачу {doctor_name} в отделении {department} подтверждён.
        Дата и время: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        if queue_number:
            email_body += f"Номер в очереди: {queue_number}\n"

        email_body += """
        Пожалуйста, придите за 10 минут до назначенного времени.
        
        С уважением,
        Администрация клиники
        """

        sms_message = (
            f"Визит к {doctor_name} подтверждён {visit_date.strftime('%d.%m в %H:%M')}"
        )
        if queue_number:
            sms_message += f", очередь №{queue_number}"

        telegram_message = f"""
        ✅ <b>Подтверждение визита</b>
        
        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        👨‍⚕️ Врач: {doctor_name}
        🏥 Отделение: {department}
        📅 Дата: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        if queue_number:
            telegram_message += f"🎫 Номер в очереди: {queue_number}"

        # Отправляем уведомления
        results = {}

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        results["telegram"] = await self.send_telegram(telegram_message)

        return results

    async def send_appointment_confirmation(
        self,
        db: Session,
        appointment_id: int,
    ) -> Dict[str, bool]:
        """Отправка подтверждения записи (Unified: Push, Email, SMS, Telegram)"""
        from app.models.appointment import Appointment
        from app.models.user import User
        
        try:
            appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                return {}
                
            doctor_name = appointment.doctor.name if appointment.doctor else "Врач"
            specialty = appointment.doctor.specialty if appointment.doctor else ""
            visit_date_str = appointment.appointment_date.strftime('%d.%m.%Y в %H:%M')
            
            # --- Push Notification Logic ---
            if appointment.patient and appointment.patient.user_id:
                user = db.query(User).filter(User.id == appointment.patient.user_id).first()
                if user and user.device_token:
                    title = "Запись подтверждена"
                    message = f"Ваша запись к врачу {doctor_name} на {visit_date_str} подтверждена"
                    
                    await self.send_push(
                        user_id=user.id,
                        title=title,
                        message=message,
                        data={
                            "type": "appointment_confirmation",
                            "appointment_id": appointment_id,
                        },
                        db=db
                    )

            # --- Unified Channels Logic ---
            # Call the lower-level send_visit_confirmation for Email/SMS/Telegram
            # We need patient email/phone.
            patient_email = appointment.patient.email if appointment.patient else None
            patient_phone = appointment.patient.phone if appointment.patient else None
            
            # Use send_visit_confirmation which handles Email/SMS/Telegram template formatting
            # Note: send_visit_confirmation sends "confirmation" logic.
            # Ideally we reuse it.
            
            return await self.send_visit_confirmation(
                patient_email=patient_email,
                patient_phone=patient_phone,
                visit_date=appointment.appointment_date,
                doctor_name=doctor_name,
                department=specialty, # Using specialty as department for notification text
            )

        except Exception as e:
            logger.error(f"Error sending appointment confirmation: {e}")
            return {}

    async def send_payment_notification(
        self,
        patient_email: str,
        patient_phone: str,
        amount: float,
        currency: str,
        visit_date: datetime,
        doctor_name: str,
    ) -> Dict[str, bool]:
        """Отправка уведомления об оплате"""
        subject = "Подтверждение оплаты"

        email_body = f"""
        Здравствуйте!
        
        Получена оплата за визит к врачу {doctor_name}.
        Сумма: {amount} {currency}
        Дата визита: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        
        Спасибо за оплату!
        
        С уважением,
        Администрация клиники
        """

        sms_message = f"Оплата {amount} {currency} получена за визит к {doctor_name}"

        telegram_message = f"""
        💰 <b>Подтверждение оплаты</b>
        
        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        💵 Сумма: {amount} {currency}
        👨‍⚕️ Врач: {doctor_name}
        📅 Дата визита: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        # Отправляем уведомления
        results = {}

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        results["telegram"] = await self.send_telegram(telegram_message)

        return results

    async def send_queue_update(
        self,
        department: str,
        current_number: int,
        estimated_wait: str,
        patient_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> bool:
        """Отправка обновления очереди (Telegram + Push)"""
        message = f"""
        📊 <b>Обновление очереди</b>
        
        🏥 Отделение: {department}
        🎫 Текущий номер: {current_number}
        ⏱️ Примерное время ожидания: {estimated_wait}
        
        Обновлено: {datetime.now().strftime('%H:%M:%S')}
        """
        
        # Основная рассылка (в канал/чат отделения, если есть - пока только return telegram logic)
        # TODO: Если это обновление для КОНКРЕТНОГО пациента (mobile view), отправляем ему лично.
        
        if patient_id and db:
             # Отправка конкретному пациенту
             from app.models.user import User
             
             # Push logic if patient has user linked
             # Assuming patient_id is ID from Patient model
             # We need User object.
             # This method signature originally was for GENERAL update.
             # MobileNotificationService had send_queue_update(patient_id, queue_position, specialty)
             pass 

        return await self.send_telegram(message) 
        
    async def send_patient_queue_update(
        self,
        db: Session,
        patient_id: int,
        queue_position: int,
        specialty: str
    ) -> bool:
        """Отправка уведомления пациенту о позиции в очереди (Mobile/Push)"""
        try:
             # Находим пользователя через пациента
             from app.models.patient import Patient
             from app.models.user import User
             
             patient = db.query(Patient).filter(Patient.id == patient_id).first()
             if not patient or not patient.user_id:
                 return False
                 
             user = db.query(User).filter(User.id == patient.user_id).first()
             if not user:
                 return False

             title = "Обновление очереди"
             message = f"Ваша позиция в очереди к {specialty}: #{queue_position}"
             
             # Push
             if user.device_token:
                 await self.send_push(
                     user_id=user.id,
                     title=title,
                     message=message,
                     data={
                         "type": "queue_update",
                         "queue_position": queue_position,
                         "specialty": specialty,
                     },
                     db=db
                 )
             
             # Telegram (если есть)
             if user.telegram_id:
                 await self.send_telegram_message(
                     user.telegram_id,
                     f"🔢 <b>{title}</b>\n\n{message}"
                 )
                 
             return True
        except Exception as e:
            logger.error(f"Error sending patient queue update: {e}")
            return False

    async def send_system_alert(
        self, alert_type: str, message: str, details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Отправка системного оповещения"""
        alert_message = f"""
        🚨 <b>Системное оповещение</b>
        
        Тип: {alert_type}
        Сообщение: {message}
        """

        if details:
            alert_message += "\nДетали:\n"
            for key, value in details.items():
                alert_message += f"• {key}: {value}\n"

        alert_message += f"\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"

        return await self.send_telegram(alert_message)

    def render_template(self, template_text: str, data: Dict[str, Any]) -> str:
        """Рендеринг шаблона с данными"""
        try:
            template = Template(template_text)
            return template.render(**data)
        except Exception as e:
            logger.error(f"Ошибка рендеринга шаблона: {e}")
            return template_text

    async def send_templated_notification(
        self,
        db: Session,
        notification_type: str,
        channel: str,
        recipient_contact: str,
        template_data: Dict[str, Any],
        recipient_type: str = "patient",
        recipient_id: Optional[int] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[int] = None,
    ) -> NotificationHistory:
        """Отправка уведомления с использованием шаблона"""

        # Получаем шаблон
        template = crud_notification_template.get_by_type_and_channel(
            db, type=notification_type, channel=channel
        )

        if not template:
            logger.warning(f"Шаблон не найден: {notification_type}/{channel}")
            # Используем базовый шаблон
            subject = template_data.get("subject", "Уведомление")
            content = template_data.get("message", "Сообщение")
        else:
            subject = (
                self.render_template(template.subject or "", template_data)
                if template.subject
                else None
            )
            content = self.render_template(template.template, template_data)

        # Создаем запись в истории
        history_data = NotificationHistoryCreate(
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_contact=recipient_contact,
            notification_type=notification_type,
            channel=channel,
            template_id=template.id if template else None,
            subject=subject,
            content=content,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            metadata=template_data,
        )

        history = crud_notification_history.create(db, obj_in=history_data)

        # Отправляем уведомление
        success = False
        error_message = None

        try:
            if channel == "email":
                success = await self.send_email(
                    recipient_contact, subject or "Уведомление", content
                )
            elif channel == "sms":
                success = await self.send_sms(recipient_contact, content)
            elif channel == "telegram":
                success = await self.send_telegram(content, recipient_contact)
            else:
                error_message = f"Неподдерживаемый канал: {channel}"

        except Exception as e:
            error_message = str(e)
            logger.error(f"Ошибка отправки уведомления: {e}")

        # Обновляем статус в истории
        status = "sent" if success else "failed"
        crud_notification_history.update_status(
            db, notification_id=history.id, status=status, error_message=error_message
        )

        return history

    async def send_bulk_notification(
        self,
        db: Session,
        notification_type: str,
        channels: List[str],
        recipients: List[Dict[str, Any]],
        template_data: Dict[str, Any],
    ) -> List[NotificationHistory]:
        """Массовая отправка уведомлений с проверкой настроек пользователей"""
        results = []

        for recipient in recipients:
            for channel in channels:
                # Проверяем настройки пользователя
                settings = crud_user_notification_settings.get_by_user_id(
                    db, user_id=recipient["id"]
                )

                if settings:
                    # Проверяем конкретную настройку для этого типа уведомления и канала
                    # формат: email_appointment_reminder
                    # Если тип уведомления "appointment_reminder", то ищем "email_appointment_reminder"
                    
                    setting_key = f"{channel}_{notification_type}"
                    
                    # Проверяем наличие атрибута, если нет - считаем включенным по умолчанию (или глобальным)
                    if hasattr(settings, setting_key):
                        if not getattr(settings, setting_key):
                            continue # Выключено пользователем
                
                # Получаем контакт для канала
                contact = None
                if channel == "email":
                    contact = recipient.get("email")
                elif channel == "sms":
                    contact = recipient.get("phone")
                elif channel == "telegram":
                    contact = recipient.get("telegram")

                if not contact:
                    continue  # Пропускаем, если нет контакта

                # Объединяем данные получателя с общими данными шаблона
                merged_data = {**template_data, **recipient}

                # Отправляем уведомление
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=merged_data,
                    recipient_type=recipient["type"],
                    recipient_id=recipient["id"],
                )

                results.append(history)

        return results

    async def send_appointment_notification(
        self,
        db: Session,
        appointment_id: int,
        patient_id: int,
        notification_type: str = "appointment_reminder",
        channels: Optional[List[str]] = None,
    ) -> List[NotificationHistory]:
        """Отправка уведомления о записи"""
        from app.crud import patient as patient_crud
        from app.models.appointment import Appointment

        # Получаем данные записи
        appointment = (
            db.query(Appointment).filter(Appointment.id == appointment_id).first()
        )
        if not appointment:
            logger.warning(f"Запись не найдена: {appointment_id}")
            return []

        # Получаем данные пациента
        patient = patient_crud.get(db, id=patient_id)
        if not patient:
            logger.warning(f"Пациент не найден: {patient_id}")
            return []

        # Данные для шаблона
        template_data = {
            "patient_name": patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            "patient_phone": patient.phone,
            "appointment_date": appointment.appointment_date.strftime("%d.%m.%Y"),
            "appointment_time": (
                appointment.appointment_time.strftime("%H:%M")
                if appointment.appointment_time
                else ""
            ),
            "doctor_name": appointment.doctor_name or "врач",
            "department": appointment.department or "отделение",
            "clinic_name": "Медицинская клиника",
            "clinic_phone": "+998 90 123 45 67",
        }

        # Определяем каналы
        if channels is None:
            channels = ["email", "sms"]

        # Отправляем уведомления
        results = []
        for channel in channels:
            contact = None
            if channel == "email":
                contact = patient.email
            elif channel == "sms":
                contact = patient.phone

            if contact:
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=template_data,
                    recipient_type="patient",
                    recipient_id=patient_id,
                    related_entity_type="appointment",
                    related_entity_id=appointment_id,
                )
                results.append(history)

        return results

    async def send_payment_notification_by_id(
        self,
        db: Session,
        payment_id: int,
        patient_id: int,
        amount: float,
        currency: str = "UZS",
        notification_type: str = "payment_success",
        channels: Optional[List[str]] = None,
    ) -> List[NotificationHistory]:
        """Отправка уведомления об оплате"""
        from app.crud import patient as patient_crud

        # Получаем данные пациента
        patient = patient_crud.get(db, id=patient_id)
        if not patient:
            logger.warning(f"Пациент не найден: {patient_id}")
            return []

        # Данные для шаблона
        template_data = {
            "patient_name": patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            "amount": amount,
            "currency": currency,
            "formatted_amount": f"{amount:,.0f} {currency}",
            "payment_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "clinic_name": "Медицинская клиника",
            "clinic_phone": "+998 90 123 45 67",
        }

        # Определяем каналы
        if channels is None:
            channels = ["email", "sms"]

        # Отправляем уведомления
        results = []
        for channel in channels:
            contact = None
            if channel == "email":
                contact = patient.email
            elif channel == "sms":
                contact = patient.phone

            if contact:
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=template_data,
                    recipient_type="patient",
                    recipient_id=patient_id,
                    related_entity_type="payment",
                    related_entity_id=payment_id,
                )
                results.append(history)

        return results


        return results

    # === Business Logic Methods (Merged from Mobile/Telegram Services) ===

    async def send_lab_results_notification(
        self,
        db: Session,
        user_id: int,
        test_name: str,
        test_date: datetime,
        lab_result_id: Optional[int] = None,
    ) -> Dict[str, bool]:
        """Уведомление о готовности результатов анализов"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = "Результаты анализов готовы"
            message = f"Результаты анализа '{test_name}' от {test_date.strftime('%d.%m.%Y')} готовы к просмотру."
            
            results = {}
            
            # Telegram
            if user.telegram_id:
                tele_msg = f"🔬 <b>{subject}</b>\n\n{message}"
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)
            
            # Push
            if user.device_token:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "lab_results", "lab_result_id": lab_result_id},
                    db=db
                )
                
            return results
        except Exception as e:
            logger.error(f"Error sending lab results notification: {e}")
            return {}

    async def send_prescription_ready_notification(
        self,
        db: Session,
        user_id: int,
        prescription_id: int,
        doctor_name: str,
    ) -> Dict[str, bool]:
        """Уведомление о готовности рецепта"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = "Рецепт готов"
            message = f"Ваш рецепт №{prescription_id} от врача {doctor_name} готов."
            
            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"""
💊 <b>{subject}</b>

👨‍⚕️ Врач: {doctor_name}
📄 Рецепт №{prescription_id}
📅 Дата: {datetime.now().strftime("%d.%m.%Y")}

Рецепт доступен в приложении.
"""
                # TODO: Add download button if using pure telegram bot API manually, 
                # but send_telegram_message is simple text. 
                # For now keeping clear text.
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user.device_token:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "prescription_ready", "prescription_id": prescription_id},
                    db=db
                )
            
            return results
        except Exception as e:
            logger.error(f"Error sending prescription notification: {e}")
            return {}

    async def send_schedule_change_notification(
        self,
        db: Session,
        user_id: int,
        change_type: str,
        old_data: Dict[str, Any],
        new_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, bool]:
        """Уведомление об изменении в расписании"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            subject = ""
            message = ""
            
            if change_type == "cancelled":
                subject = "Визит отменен"
                message = f"Визит к врачу {old_data.get('doctor')} на {old_data.get('date')} {old_data.get('time')} отменен."
            elif change_type == "rescheduled":
                subject = "Визит перенесен"
                message = f"Визит перенесен на {new_data.get('date')} {new_data.get('time')}."
            elif change_type == "doctor_changed":
                subject = "Смена врача"
                message = f"Ваш лечащий врач изменен на {new_data.get('doctor')}."

            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"📅 <b>{subject}</b>\n\n{message}"
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user.device_token:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "schedule_change", "change_type": change_type},
                    db=db
                )
                
            return results
        except Exception as e:
            logger.error(f"Error sending schedule change notification: {e}")
            return {}
            
    async def send_appointment_cancellation(
        self,
        db: Session,
        appointment_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """Отправка уведомления об отмене записи (Wrapper logic)"""
        from app.models.appointment import Appointment
        
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return False
            
        old_data = {
            "doctor": appointment.doctor.name if appointment.doctor else "Врач",
            "date": appointment.appointment_date.strftime("%d.%m.%Y"),
            "time": appointment.appointment_date.strftime("%H:%M") # Assuming appointment_date has time or separate field
        }
        
        return await self.send_schedule_change_notification(
            db=db,
            user_id=appointment.patient_id,
            change_type="cancelled",
            old_data=old_data
        )

    async def send_visit_confirmation_invitation(
        self, db: Session, visit_id: int, channel: str = "auto"
    ) -> Dict[str, Any]:
        """
        Отправляет приглашение на подтверждение визита
        """
        from app.models.visit import Visit
        from app.models.patient import Patient

        try:
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                return {"success": False, "error": "Визит не найден"}

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            # Определяем канал автоматически если нужно
            if channel == "auto":
                channel = self._determine_best_channel(patient)

            # Формируем данные для уведомления
            notification_data = self._prepare_notification_data(db, visit, patient)

            # Отправляем уведомление по выбранному каналу
            if channel == "telegram":
                return await self._send_telegram_invitation(patient, notification_data)
            elif channel == "pwa":
                return await self._send_pwa_invitation(patient, notification_data)
            elif channel == "phone":
                return await self._send_phone_invitation(patient, notification_data)
            else:
                return {"success": False, "error": f"Неподдерживаемый канал: {channel}"}

        except Exception as e:
            logger.error(f"Ошибка отправки приглашения на подтверждение: {e}")
            return {"success": False, "error": str(e)}

    def _determine_best_channel(self, patient: Any) -> str:
        """Определяет лучший канал для отправки уведомления"""
        # Приоритет: Telegram > PWA > Phone
        if hasattr(patient, 'telegram_id') and patient.telegram_id:
            return "telegram"
        if patient.phone and patient.phone.startswith('+998'):
            return "pwa"
        return "phone"

    def _prepare_notification_data(
        self, db: Session, visit: Any, patient: Any
    ) -> Dict[str, Any]:
        """Подготавливает данные для уведомления"""
        from app.models.visit import VisitService
        from app.models.clinic import Doctor

        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        services_text = []
        total_amount = 0
        for vs in visit_services:
            services_text.append(f"• {vs.name} - {vs.price} сум")
            total_amount += float(vs.price) if vs.price else 0

        doctor_name = "Без врача"
        if visit.doctor_id:
            doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
            if doctor and doctor.user:
                doctor_name = doctor.user.full_name or doctor.user.username

        return {
            "visit_id": visit.id,
            "patient_name": patient.short_name() if hasattr(patient, 'short_name') else f"{patient.first_name} {patient.last_name}",
            "doctor_name": doctor_name,
            "visit_date": visit.visit_date.strftime("%d.%m.%Y"),
            "visit_time": visit.visit_time or "Время не указано",
            "services": services_text,
            "total_amount": total_amount,
            "confirmation_token": visit.confirmation_token,
            "expires_at": visit.confirmation_expires_at,
            "visit_type": self._get_visit_type_text(visit.discount_mode),
        }

    def _get_visit_type_text(self, discount_mode: Optional[str]) -> str:
        if discount_mode == "repeat":
            return "Повторный визит"
        elif discount_mode == "benefit":
            return "Льготный визит"
        elif discount_mode == "all_free":
            return "Бесплатный визит"
        else:
            return "Платный визит"

    async def _send_telegram_invitation(
        self, patient: Any, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Отправляет приглашение через Telegram"""
        try:
            if not hasattr(patient, 'telegram_id') or not patient.telegram_id:
                return {"success": False, "error": "У пациента нет Telegram ID"}

            message = self._format_telegram_message(data)
            keyboard = self._create_telegram_keyboard(data["confirmation_token"])

            # Используем telegram_bot для отправки
            result = await self.telegram_bot.send_confirmation_invitation(
                chat_id=patient.telegram_id, message=message, keyboard=keyboard
            )

            if result.get("success"):
                logger.info(f"Telegram приглашение отправлено пациенту {patient.id}")
                return {
                    "success": True,
                    "channel": "telegram",
                    "message_id": result.get("message_id"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Ошибка отправки Telegram"),
                }

        except Exception as e:
            logger.error(f"Ошибка отправки Telegram приглашения: {e}")
            return {"success": False, "error": str(e)}

    def _format_telegram_message(self, data: Dict[str, Any]) -> str:
        services_list = "\n".join(data["services"])
        message = f"""
🏥 **Подтверждение визита в клинику**

👤 **Пациент:** {data["patient_name"]}
👨‍⚕️ **Врач:** {data["doctor_name"]}
📅 **Дата:** {data["visit_date"]}
🕐 **Время:** {data["visit_time"]}
💰 **Тип:** {data["visit_type"]}

📋 **Услуги:**
{services_list}

💵 **Общая сумма:** {data["total_amount"]} сум

⏰ **Подтвердите визит до:** {data["expires_at"].strftime("%d.%m.%Y %H:%M") if data["expires_at"] else "Не указано"}

Нажмите кнопку ниже для подтверждения:
        """.strip()
        return message

    def _create_telegram_keyboard(
        self, confirmation_token: str
    ) -> List[List[Dict[str, str]]]:
        return [
            [
                {
                    "text": "✅ Подтвердить визит",
                    "callback_data": f"confirm_visit:{confirmation_token}",
                }
            ],
            [
                {
                    "text": "❌ Отменить визит",
                    "callback_data": f"cancel_visit:{confirmation_token}",
                }
            ],
            [
                {
                    "text": "📞 Связаться с клиникой",
                    "url": f"tel:{settings.CLINIC_PHONE}",
                }
            ],
        ]

    async def _send_pwa_invitation(
        self, patient: Any, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Отправляет приглашение через PWA (SMS с deep link)"""
        try:
            if not patient.phone:
                return {"success": False, "error": "У пациента нет номера телефона"}

            pwa_url = f"{settings.PWA_BASE_URL}/confirm-visit?token={data['confirmation_token']}"
            sms_text = self._format_sms_message(data, pwa_url)

            success = await self.send_sms(patient.phone, sms_text)

            if success:
                logger.info(f"PWA приглашение отправлено пациенту {patient.id}")
                return {"success": True, "channel": "pwa", "pwa_url": pwa_url}
            else:
                return {"success": False, "error": "Ошибка отправки SMS"}

        except Exception as e:
            logger.error(f"Ошибка отправки PWA приглашения: {e}")
            return {"success": False, "error": str(e)}

    def _format_sms_message(self, data: Dict[str, Any], pwa_url: str) -> str:
        return f"""
Клиника: Подтвердите визит на {data["visit_date"]} в {data["visit_time"]} к врачу {data["doctor_name"]}.
Сумма: {data["total_amount"]} сум.
Подтвердить: {pwa_url}
        """.strip()

    async def _send_phone_invitation(
        self, patient: Any, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Создает задачу для регистратуры - позвонить пациенту"""
        # Пока просто логируем, в будущем можно интегрировать с CRM/Task системой
        logger.info(f"Создано уведомление для регистратуры: позвонить пациенту {patient.id} для подтверждения визита {data['visit_id']}")
        return {
            "success": True,
            "channel": "phone",
            "message": "Создана задача для регистратуры",
        }

    async def send_confirmation_reminder(
        self, db: Session, visit_id: int, hours_before: int = 24
    ) -> Dict[str, Any]:
        """Отправляет напоминание о необходимости подтверждения"""
        from app.models.visit import Visit
        from app.models.patient import Patient

        try:
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                return {"success": False, "error": "Визит не найден"}

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            channel = self._determine_best_channel(patient)
            notification_data = self._prepare_notification_data(db, visit, patient)
            notification_data["is_reminder"] = True
            notification_data["hours_before"] = hours_before

            if channel == "telegram":
                # Упрощенная версия напоминания для Telegram (можно расширить)
                message = f"🔔 Напоминание! Пожалуйста, подтвердите визит к врачу {notification_data['doctor_name']} на {notification_data['visit_date']} {notification_data['visit_time']}."
                keyboard = self._create_telegram_keyboard(notification_data["confirmation_token"])
                result = await self.telegram_bot.send_confirmation_invitation(
                    chat_id=patient.telegram_id, message=message, keyboard=keyboard
                )
                return {"success": result.get("success"), "error": result.get("error")}
            elif channel == "pwa":
                 return await self._send_pwa_invitation(patient, notification_data)
            else:
                 return await self._send_phone_invitation(patient, notification_data)

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
            return {"success": False, "error": str(e)}

    async def send_telegram_message(
        self, user_id: Union[int, str], message: str, parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """
        Отправляет сообщение через Telegram бот.
        Метод-обертка для совместимости с кодом, использующим NotificationService.
        """
        try:
            if not self.telegram_bot:
                logger.warning("Telegram bot integration not initialized")
                return {"success": False, "error": "Telegram bot not initialized"}

            # Используем telegram_bot.send_message (предполагая что такой метод есть или будет добавлен)
            # Если в TelegramBotService нет send_message, используем telegram_bot.application.bot.send_message
            # Но лучше использовать методы сервиса.
            # Проверим есть ли метод send_message в TelegramBotService, 
            # если нет - используем send_message из bot instance
            
            # В TelegramBotService обычно есть send_message
            if hasattr(self.telegram_bot, "send_message"):
                 return await self.telegram_bot.send_message(user_id=user_id, text=message, parse_mode=parse_mode)
            else:
                 # Fallback
                 await self.telegram_bot.application.bot.send_message(chat_id=user_id, text=message, parse_mode=parse_mode)
                 return {"success": True}
                 
        except Exception as e:
            logger.error(f"Error sending telegram message: {e}")
            return {"success": False, "error": str(e)}

    # === End merged methods ===

# Создаём глобальный экземпляр сервиса
notification_sender_service = NotificationSenderService()
# Сохраняем старое имя для совместимости (пока не обновим все импорты)
notification_service = notification_sender_service
