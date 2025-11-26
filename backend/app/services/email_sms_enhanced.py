"""
Расширенный сервис для Email и SMS уведомлений
Поддержка HTML шаблонов, массовых рассылок и аналитики
"""
import asyncio
import logging
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import Any, Dict, List, Optional, Tuple
from jinja2 import Template, Environment, FileSystemLoader
import requests
import json
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import notification as crud_notification
from app.models.notification import NotificationHistory

logger = logging.getLogger(__name__)

class EmailSMSEnhancedService:
    """Расширенный сервис для Email и SMS уведомлений"""

    def __init__(self):
        # Email настройки
        self.smtp_server = getattr(settings, "SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "SMTP_USERNAME", None)
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", None)
        self.smtp_use_tls = getattr(settings, "SMTP_USE_TLS", True)
        
        # SMS настройки
        self.sms_api_key = getattr(settings, "SMS_API_KEY", None)
        self.sms_api_url = getattr(settings, "SMS_API_URL", None)
        self.sms_sender = getattr(settings, "SMS_SENDER", "Clinic")
        
        # Шаблоны
        self.template_env = Environment(
            loader=FileSystemLoader('templates/email'),
            autoescape=True
        )
        
        # Статистика
        self.stats = {
            'emails_sent': 0,
            'emails_failed': 0,
            'sms_sent': 0,
            'sms_failed': 0,
            'last_reset': datetime.now()
        }

    async def send_email_enhanced(
        self,
        to_email: str,
        subject: str,
        template_name: str = None,
        template_data: Dict[str, Any] = None,
        html_content: str = None,
        text_content: str = None,
        attachments: List[Dict[str, Any]] = None,
        priority: str = "normal"
    ) -> Tuple[bool, str]:
        """Расширенная отправка email с поддержкой шаблонов"""
        try:
            if not all([self.smtp_username, self.smtp_password]):
                logger.warning("SMTP credentials не настроены")
                return False, "SMTP credentials не настроены"

            # Создаем сообщение
            msg = MIMEMultipart("alternative")
            msg["From"] = f"Programma Clinic <{self.smtp_username}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg["X-Priority"] = "1" if priority == "high" else "3"

            # Генерируем контент
            if template_name and template_data:
                html_content, text_content = await self._render_email_template(
                    template_name, template_data
                )
            elif not html_content and not text_content:
                return False, "Не указан контент или шаблон"

            # Добавляем текстовую версию
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                msg.attach(text_part)

            # Добавляем HTML версию
            if html_content:
                html_part = MIMEText(html_content, "html", "utf-8")
                msg.attach(html_part)

            # Добавляем вложения
            if attachments:
                for attachment in attachments:
                    await self._add_attachment(msg, attachment)

            # Отправляем письмо
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            self.stats['emails_sent'] += 1
            logger.info(f"Email отправлен на {to_email}: {subject}")
            return True, "Email отправлен успешно"

        except Exception as e:
            self.stats['emails_failed'] += 1
            logger.error(f"Ошибка отправки email: {e}")
            return False, str(e)

    async def send_sms_enhanced(
        self,
        phone: str,
        message: str,
        template_name: str = None,
        template_data: Dict[str, Any] = None,
        sender: str = None,
        priority: str = "normal"
    ) -> Tuple[bool, str]:
        """Расширенная отправка SMS с поддержкой шаблонов"""
        try:
            if not all([self.sms_api_key, self.sms_api_url]):
                logger.warning("SMS API credentials не настроены")
                return False, "SMS API credentials не настроены"

            # Генерируем сообщение
            if template_name and template_data:
                message = await self._render_sms_template(template_name, template_data)
            elif not message:
                return False, "Не указано сообщение или шаблон"

            # Подготавливаем данные для отправки
            data = {
                "api_key": self.sms_api_key,
                "phone": self._format_phone(phone),
                "message": message,
                "sender": sender or self.sms_sender,
                "priority": priority
            }

            # Отправляем SMS
            response = requests.post(
                self.sms_api_url,
                json=data,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            result = response.json()
            if result.get('success', False):
                self.stats['sms_sent'] += 1
                logger.info(f"SMS отправлено на {phone}")
                return True, "SMS отправлено успешно"
            else:
                self.stats['sms_failed'] += 1
                error_msg = result.get('error', 'Неизвестная ошибка')
                logger.error(f"Ошибка отправки SMS: {error_msg}")
                return False, error_msg

        except Exception as e:
            self.stats['sms_failed'] += 1
            logger.error(f"Ошибка отправки SMS: {e}")
            return False, str(e)

    async def send_bulk_email(
        self,
        recipients: List[Dict[str, Any]],
        subject: str,
        template_name: str = None,
        template_data: Dict[str, Any] = None,
        html_content: str = None,
        text_content: str = None,
        batch_size: int = 50,
        delay_between_batches: float = 1.0
    ) -> Dict[str, Any]:
        """Массовая отправка email"""
        results = {
            'total': len(recipients),
            'sent': 0,
            'failed': 0,
            'errors': []
        }

        # Разбиваем на батчи
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            # Отправляем батч
            tasks = []
            for recipient in batch:
                task = self.send_email_enhanced(
                    to_email=recipient['email'],
                    subject=subject,
                    template_name=template_name,
                    template_data={**template_data, **recipient} if template_data else recipient,
                    html_content=html_content,
                    text_content=text_content
                )
                tasks.append(task)

            # Ждем завершения батча
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем результаты
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results['failed'] += 1
                    results['errors'].append(f"Ошибка для {batch[j]['email']}: {str(result)}")
                elif result[0]:  # success
                    results['sent'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Ошибка для {batch[j]['email']}: {result[1]}")

            # Задержка между батчами
            if i + batch_size < len(recipients):
                await asyncio.sleep(delay_between_batches)

        return results

    async def send_bulk_sms(
        self,
        recipients: List[Dict[str, Any]],
        message: str = None,
        template_name: str = None,
        template_data: Dict[str, Any] = None,
        batch_size: int = 100,
        delay_between_batches: float = 0.5
    ) -> Dict[str, Any]:
        """Массовая отправка SMS"""
        results = {
            'total': len(recipients),
            'sent': 0,
            'failed': 0,
            'errors': []
        }

        # Разбиваем на батчи
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            # Отправляем батч
            tasks = []
            for recipient in batch:
                task = self.send_sms_enhanced(
                    phone=recipient['phone'],
                    message=message,
                    template_name=template_name,
                    template_data={**template_data, **recipient} if template_data else recipient
                )
                tasks.append(task)

            # Ждем завершения батча
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем результаты
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results['failed'] += 1
                    results['errors'].append(f"Ошибка для {batch[j]['phone']}: {str(result)}")
                elif result[0]:  # success
                    results['sent'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Ошибка для {batch[j]['phone']}: {result[1]}")

            # Задержка между батчами
            if i + batch_size < len(recipients):
                await asyncio.sleep(delay_between_batches)

        return results

    async def send_appointment_reminder_enhanced(
        self,
        patient_data: Dict[str, Any],
        appointment_data: Dict[str, Any],
        channels: List[str] = None,
        template_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Расширенное напоминание о записи"""
        if channels is None:
            channels = ['email', 'sms']

        results = {
            'patient_id': patient_data.get('id'),
            'appointment_id': appointment_data.get('id'),
            'channels': {},
            'success': True
        }

        # Подготавливаем данные для шаблона
        template_data = template_data or {}
        template_data.update({
            'patient_name': patient_data.get('full_name', 'Пациент'),
            'patient_phone': patient_data.get('phone', ''),
            'patient_email': patient_data.get('email', ''),
            'doctor_name': appointment_data.get('doctor_name', 'Врач'),
            'specialty': appointment_data.get('specialty', 'Специалист'),
            'appointment_date': appointment_data.get('date', ''),
            'appointment_time': appointment_data.get('time', ''),
            'cabinet': appointment_data.get('cabinet', 'Уточните в регистратуре'),
            'clinic_name': 'Programma Clinic',
            'clinic_address': 'г. Ташкент, ул. Медицинская, 15',
            'clinic_phone': '+998 71 123-45-67'
        })

        # Отправляем по каналам
        for channel in channels:
            if channel == 'email' and patient_data.get('email'):
                success, message = await self.send_email_enhanced(
                    to_email=patient_data['email'],
                    subject=f"Напоминание о записи - {template_data['appointment_date']}",
                    template_name='appointment_reminder',
                    template_data=template_data
                )
                results['channels']['email'] = {'success': success, 'message': message}
            
            elif channel == 'sms' and patient_data.get('phone'):
                success, message = await self.send_sms_enhanced(
                    phone=patient_data['phone'],
                    template_name='appointment_reminder_sms',
                    template_data=template_data
                )
                results['channels']['sms'] = {'success': success, 'message': message}

        # Определяем общий успех
        results['success'] = all(
            result.get('success', False) 
            for result in results['channels'].values()
        )

        return results

    async def send_lab_results_enhanced(
        self,
        patient_data: Dict[str, Any],
        lab_data: Dict[str, Any],
        channels: List[str] = None,
        template_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Расширенная отправка результатов анализов"""
        if channels is None:
            channels = ['email', 'sms']

        results = {
            'patient_id': patient_data.get('id'),
            'lab_results_id': lab_data.get('id'),
            'channels': {},
            'success': True
        }

        # Подготавливаем данные для шаблона
        template_data = template_data or {}
        template_data.update({
            'patient_name': patient_data.get('full_name', 'Пациент'),
            'patient_phone': patient_data.get('phone', ''),
            'patient_email': patient_data.get('email', ''),
            'test_type': lab_data.get('test_type', 'Лабораторное исследование'),
            'collection_date': lab_data.get('collection_date', ''),
            'ready_date': datetime.now().strftime('%d.%m.%Y'),
            'has_abnormalities': lab_data.get('has_abnormalities', False),
            'download_link': f"https://clinic.example.com/lab-results/{patient_data.get('id')}",
            'clinic_name': 'Programma Clinic',
            'clinic_phone': '+998 71 123-45-67'
        })

        # Отправляем по каналам
        for channel in channels:
            if channel == 'email' and patient_data.get('email'):
                success, message = await self.send_email_enhanced(
                    to_email=patient_data['email'],
                    subject=f"Результаты анализов готовы - {template_data['ready_date']}",
                    template_name='lab_results_ready',
                    template_data=template_data
                )
                results['channels']['email'] = {'success': success, 'message': message}
            
            elif channel == 'sms' and patient_data.get('phone'):
                success, message = await self.send_sms_enhanced(
                    phone=patient_data['phone'],
                    template_name='lab_results_ready_sms',
                    template_data=template_data
                )
                results['channels']['sms'] = {'success': success, 'message': message}

        # Определяем общий успех
        results['success'] = all(
            result.get('success', False) 
            for result in results['channels'].values()
        )

        return results

    async def send_payment_confirmation_enhanced(
        self,
        patient_data: Dict[str, Any],
        payment_data: Dict[str, Any],
        channels: List[str] = None,
        template_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Расширенное подтверждение платежа"""
        if channels is None:
            channels = ['email', 'sms']

        results = {
            'patient_id': patient_data.get('id'),
            'payment_id': payment_data.get('id'),
            'channels': {},
            'success': True
        }

        # Подготавливаем данные для шаблона
        template_data = template_data or {}
        template_data.update({
            'patient_name': patient_data.get('full_name', 'Пациент'),
            'patient_phone': patient_data.get('phone', ''),
            'patient_email': patient_data.get('email', ''),
            'amount': payment_data.get('amount', 0),
            'currency': payment_data.get('currency', 'UZS'),
            'formatted_amount': f"{payment_data.get('amount', 0):,.0f} {payment_data.get('currency', 'UZS')}",
            'payment_method': payment_data.get('payment_method', 'Карта'),
            'payment_date': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'transaction_id': payment_data.get('transaction_id', ''),
            'receipt_link': f"https://clinic.example.com/receipt/{payment_data.get('transaction_id')}",
            'clinic_name': 'Programma Clinic',
            'clinic_phone': '+998 71 123-45-67'
        })

        # Отправляем по каналам
        for channel in channels:
            if channel == 'email' and patient_data.get('email'):
                success, message = await self.send_email_enhanced(
                    to_email=patient_data['email'],
                    subject=f"Подтверждение платежа - {template_data['formatted_amount']}",
                    template_name='payment_confirmation',
                    template_data=template_data
                )
                results['channels']['email'] = {'success': success, 'message': message}
            
            elif channel == 'sms' and patient_data.get('phone'):
                success, message = await self.send_sms_enhanced(
                    phone=patient_data['phone'],
                    template_name='payment_confirmation_sms',
                    template_data=template_data
                )
                results['channels']['sms'] = {'success': success, 'message': message}

        # Определяем общий успех
        results['success'] = all(
            result.get('success', False) 
            for result in results['channels'].values()
        )

        return results

    async def _render_email_template(
        self, 
        template_name: str, 
        template_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Рендеринг HTML и текстового шаблона email"""
        try:
            # HTML шаблон
            html_template = self.template_env.get_template(f"{template_name}.html")
            html_content = html_template.render(**template_data)
            
            # Текстовый шаблон
            text_template = self.template_env.get_template(f"{template_name}.txt")
            text_content = text_template.render(**template_data)
            
            return html_content, text_content
        except Exception as e:
            logger.error(f"Ошибка рендеринга email шаблона {template_name}: {e}")
            # Возвращаем базовый шаблон
            return self._get_basic_email_template(template_data)

    async def _render_sms_template(
        self, 
        template_name: str, 
        template_data: Dict[str, Any]
    ) -> str:
        """Рендеринг SMS шаблона"""
        try:
            template = self.template_env.get_template(f"sms/{template_name}.txt")
            return template.render(**template_data)
        except Exception as e:
            logger.error(f"Ошибка рендеринга SMS шаблона {template_name}: {e}")
            # Возвращаем базовый шаблон
            return self._get_basic_sms_template(template_data)

    def _format_phone(self, phone: str) -> str:
        """Форматирование номера телефона"""
        # Убираем все нецифровые символы
        phone = ''.join(filter(str.isdigit, phone))
        
        # Добавляем код страны если нужно
        if phone.startswith('998'):
            return f"+{phone}"
        elif phone.startswith('9') and len(phone) == 9:
            return f"+998{phone}"
        elif not phone.startswith('+'):
            return f"+{phone}"
        
        return phone

    async def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Добавление вложения к email"""
        try:
            if attachment.get('type') == 'image':
                with open(attachment['path'], 'rb') as f:
                    img_data = f.read()
                image = MIMEImage(img_data)
                image.add_header('Content-Disposition', 
                               f'attachment; filename={attachment["filename"]}')
                msg.attach(image)
        except Exception as e:
            logger.error(f"Ошибка добавления вложения: {e}")

    def _get_basic_email_template(self, data: Dict[str, Any]) -> Tuple[str, str]:
        """Базовый HTML шаблон email"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Programma Clinic</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c5aa0;">Programma Clinic</h2>
                <p>Здравствуйте, {data.get('patient_name', 'Пациент')}!</p>
                <p>{data.get('message', 'Уведомление от клиники')}</p>
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">
                    Programma Clinic<br>
                    г. Ташкент, ул. Медицинская, 15<br>
                    Телефон: +998 71 123-45-67
                </p>
            </div>
        </body>
        </html>
        """
        
        text = f"""
        Programma Clinic
        
        Здравствуйте, {data.get('patient_name', 'Пациент')}!
        
        {data.get('message', 'Уведомление от клиники')}
        
        ---
        Programma Clinic
        г. Ташкент, ул. Медицинская, 15
        Телефон: +998 71 123-45-67
        """
        
        return html, text

    def _get_basic_sms_template(self, data: Dict[str, Any]) -> str:
        """Базовый SMS шаблон"""
        return f"Programma Clinic: {data.get('message', 'Уведомление от клиники')}"

    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики отправки"""
        return {
            **self.stats,
            'email_success_rate': (
                self.stats['emails_sent'] / 
                (self.stats['emails_sent'] + self.stats['emails_failed']) * 100
                if (self.stats['emails_sent'] + self.stats['emails_failed']) > 0 else 0
            ),
            'sms_success_rate': (
                self.stats['sms_sent'] / 
                (self.stats['sms_sent'] + self.stats['sms_failed']) * 100
                if (self.stats['sms_sent'] + self.stats['sms_failed']) > 0 else 0
            )
        }

    def reset_statistics(self):
        """Сброс статистики"""
        self.stats = {
            'emails_sent': 0,
            'emails_failed': 0,
            'sms_sent': 0,
            'sms_failed': 0,
            'last_reset': datetime.now()
        }

# Глобальный экземпляр сервиса
email_sms_enhanced_service = EmailSMSEnhancedService()

def get_email_sms_enhanced_service() -> EmailSMSEnhancedService:
    """Получить экземпляр расширенного Email/SMS сервиса"""
    return email_sms_enhanced_service
