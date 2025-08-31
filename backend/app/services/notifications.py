from datetime import datetime
from typing import Optional, Dict, Any, List
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """Сервис для отправки уведомлений"""
    
    def __init__(self):
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', None)
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
        
        self.telegram_bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.telegram_chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
        
        self.sms_api_key = getattr(settings, 'SMS_API_KEY', None)
        self.sms_api_url = getattr(settings, 'SMS_API_URL', None)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Отправка email уведомления"""
        if not all([self.smtp_username, self.smtp_password]):
            logger.warning("SMTP credentials не настроены")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Добавляем текстовую версию
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Добавляем HTML версию, если есть
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
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
    
    async def send_telegram(
        self,
        message: str,
        chat_id: Optional[str] = None
    ) -> bool:
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
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Telegram уведомление отправлено в чат {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки Telegram: {e}")
            return False
    
    async def send_sms(
        self,
        phone: str,
        message: str
    ) -> bool:
        """Отправка SMS уведомления"""
        if not all([self.sms_api_key, self.sms_api_url]):
            logger.warning("SMS API credentials не настроены")
            return False
        
        try:
            data = {
                "api_key": self.sms_api_key,
                "phone": phone,
                "message": message
            }
            
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
        department: str
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
            results['email'] = await self.send_email(
                patient_email, subject, email_body
            )
        
        if patient_phone:
            results['sms'] = await self.send_sms(patient_phone, sms_message)
        
        results['telegram'] = await self.send_telegram(telegram_message)
        
        return results
    
    async def send_visit_confirmation(
        self,
        patient_email: str,
        patient_phone: str,
        visit_date: datetime,
        doctor_name: str,
        department: str,
        queue_number: Optional[int] = None
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
        
        sms_message = f"Визит к {doctor_name} подтверждён {visit_date.strftime('%d.%m в %H:%M')}"
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
            results['email'] = await self.send_email(
                patient_email, subject, email_body
            )
        
        if patient_phone:
            results['sms'] = await self.send_sms(patient_phone, sms_message)
        
        results['telegram'] = await self.send_telegram(telegram_message)
        
        return results
    
    async def send_payment_notification(
        self,
        patient_email: str,
        patient_phone: str,
        amount: float,
        currency: str,
        visit_date: datetime,
        doctor_name: str
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
            results['email'] = await self.send_email(
                patient_email, subject, email_body
            )
        
        if patient_phone:
            results['sms'] = await self.send_sms(patient_phone, sms_message)
        
        results['telegram'] = await self.send_telegram(telegram_message)
        
        return results
    
    async def send_queue_update(
        self,
        department: str,
        current_number: int,
        estimated_wait: str
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
        self,
        alert_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
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

# Создаём глобальный экземпляр сервиса
notification_service = NotificationService()

