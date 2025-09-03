import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import requests
from jinja2 import Template
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.notification import (
    crud_notification_history,
    crud_notification_settings,
    crud_notification_template,
)
from app.models.notification import NotificationHistory
from app.schemas.notification import NotificationHistoryCreate

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений"""

    def __init__(self):
        self.smtp_server = getattr(settings, "SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "SMTP_USERNAME", None)
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", None)

        self.telegram_bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        self.telegram_chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)

        self.sms_api_key = getattr(settings, "SMS_API_KEY", None)
        self.sms_api_url = getattr(settings, "SMS_API_URL", None)

    async def send_email(
        self, to_email: str, subject: str, body: str, html_body: Optional[str] = None
    ) -> bool:
        """Отправка email уведомления"""
        if not all([self.smtp_username, self.smtp_password]):
            logger.warning("SMTP credentials не настроены")
            return False

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

            # Подключаемся к SMTP серверу
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

            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()

            logger.info(f"Telegram уведомление отправлено в чат {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки Telegram: {e}")
            return False

    async def send_sms(self, phone: str, message: str) -> bool:
        """Отправка SMS уведомления"""
        if not all([self.sms_api_key, self.sms_api_url]):
            logger.warning("SMS API credentials не настроены")
            return False

        try:
            data = {"api_key": self.sms_api_key, "phone": phone, "message": message}

            response = requests.post(self.sms_api_url, json=data, timeout=10)
            response.raise_for_status()

            logger.info(f"SMS отправлено на {phone}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки SMS: {e}")
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
        self, department: str, current_number: int, estimated_wait: str
    ) -> bool:
        """Отправка обновления очереди в Telegram"""
        message = f"""
        📊 <b>Обновление очереди</b>
        
        🏥 Отделение: {department}
        🎫 Текущий номер: {current_number}
        ⏱️ Примерное время ожидания: {estimated_wait}
        
        Обновлено: {datetime.now().strftime('%H:%M:%S')}
        """

        return await self.send_telegram(message)

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
        """Массовая отправка уведомлений"""
        results = []

        for recipient in recipients:
            for channel in channels:
                # Проверяем настройки пользователя
                settings = crud_notification_settings.get_by_user(
                    db, user_id=recipient["id"], user_type=recipient["type"]
                )

                if settings and not getattr(settings, f"{channel}_enabled", True):
                    continue  # Пропускаем, если канал отключен

                # Получаем контакт для канала
                contact = None
                if channel == "email":
                    contact = (
                        settings.notification_email
                        if settings
                        else recipient.get("email")
                    )
                elif channel == "sms":
                    contact = (
                        settings.notification_phone
                        if settings
                        else recipient.get("phone")
                    )
                elif channel == "telegram":
                    contact = (
                        settings.telegram_chat_id
                        if settings
                        else recipient.get("telegram")
                    )

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


# Создаём глобальный экземпляр сервиса
notification_service = NotificationService()
