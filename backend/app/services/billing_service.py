"""
Сервис для автоматического выставления счетов
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import json
from jinja2 import Template

from app.models.billing import (
    Invoice, InvoiceItem, BillingPayment, InvoiceTemplate, BillingRule, 
    PaymentReminder, BillingSettings, InvoiceStatus, InvoiceType,
    PaymentMethod, RecurrenceType
)
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.user import User


class BillingService:
    """Сервис для управления счетами и автоматическим выставлением"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # === Создание счетов ===
    
    def create_invoice(
        self,
        patient_id: int,
        services: List[Dict[str, Any]],
        visit_id: int = None,
        appointment_id: int = None,
        invoice_type: InvoiceType = InvoiceType.STANDARD,
        due_days: int = 30,
        auto_send: bool = False,
        created_by: int = None
    ) -> Invoice:
        """Создать счет"""
        
        # Получаем настройки биллинга
        settings = self.get_billing_settings()
        
        # Генерируем номер счета
        invoice_number = self._generate_invoice_number(settings)
        
        # Рассчитываем суммы
        subtotal = sum(s.get('quantity', 1) * s.get('unit_price', 0) for s in services)
        tax_amount = subtotal * (settings.default_tax_rate / 100) if settings.default_tax_rate else 0
        total_amount = subtotal + tax_amount
        
        # Создаем счет
        invoice = Invoice(
            invoice_number=invoice_number,
            patient_id=patient_id,
            visit_id=visit_id,
            appointment_id=appointment_id,
            invoice_type=invoice_type,
            subtotal=subtotal,
            tax_rate=settings.default_tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            balance=total_amount,
            issue_date=datetime.now(),
            due_date=datetime.now() + timedelta(days=due_days),
            auto_send=auto_send,
            is_auto_generated=True,
            created_by=created_by
        )
        
        self.db.add(invoice)
        self.db.flush()
        
        # Добавляем позиции счета
        for i, service_data in enumerate(services):
            item = InvoiceItem(
                invoice_id=invoice.id,
                service_id=service_data.get('service_id'),
                description=service_data.get('description', ''),
                quantity=service_data.get('quantity', 1),
                unit_price=service_data.get('unit_price', 0),
                tax_rate=settings.default_tax_rate,
                tax_amount=service_data.get('unit_price', 0) * service_data.get('quantity', 1) * (settings.default_tax_rate / 100) if settings.default_tax_rate else 0,
                total_amount=service_data.get('unit_price', 0) * service_data.get('quantity', 1),
                sort_order=i
            )
            self.db.add(item)
        
        # Обновляем номер счета в настройках
        settings.next_invoice_number += 1
        
        self.db.commit()
        self.db.refresh(invoice)
        
        # Автоматически отправляем если нужно
        if auto_send:
            self.send_invoice(invoice.id)
        
        return invoice
    
    def auto_generate_invoice_for_visit(self, visit_id: int) -> Optional[Invoice]:
        """Автоматически создать счет для визита"""
        
        visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            return None
        
        # Проверяем правила биллинга
        applicable_rules = self._get_applicable_billing_rules('visit_completed', visit)
        if not applicable_rules:
            return None
        
        # Берем правило с наивысшим приоритетом
        rule = max(applicable_rules, key=lambda r: r.priority)
        
        # Получаем услуги из визита
        services = []
        for visit_service in visit.visit_services:
            service = self.db.query(Service).filter(Service.id == visit_service.service_id).first()
            if service:
                services.append({
                    'service_id': service.id,
                    'description': service.name,
                    'quantity': 1,
                    'unit_price': visit_service.price or service.price
                })
        
        if not services:
            return None
        
        # Создаем счет
        invoice = self.create_invoice(
            patient_id=visit.patient_id,
            services=services,
            visit_id=visit_id,
            due_days=rule.payment_terms_days,
            auto_send=rule.auto_send
        )
        
        return invoice
    
    def auto_generate_invoice_for_appointment(self, appointment_id: int) -> Optional[Invoice]:
        """Автоматически создать счет для записи"""
        
        appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return None
        
        # Проверяем правила биллинга
        applicable_rules = self._get_applicable_billing_rules('appointment_created', appointment)
        if not applicable_rules:
            return None
        
        # Берем правило с наивысшим приоритетом
        rule = max(applicable_rules, key=lambda r: r.priority)
        
        # Получаем услуги из записи
        services = []
        if appointment.service_id:
            service = self.db.query(Service).filter(Service.id == appointment.service_id).first()
            if service:
                services.append({
                    'service_id': service.id,
                    'description': service.name,
                    'quantity': 1,
                    'unit_price': service.price
                })
        
        if not services:
            return None
        
        # Создаем счет
        invoice = self.create_invoice(
            patient_id=appointment.patient_id,
            services=services,
            appointment_id=appointment_id,
            due_days=rule.payment_terms_days,
            auto_send=rule.auto_send
        )
        
        return invoice
    
    # === Управление платежами ===
    
    def record_payment(
        self,
        invoice_id: int,
        amount: float,
        payment_method: PaymentMethod,
        reference_number: str = None,
        description: str = None,
        created_by: int = None
    ) -> BillingPayment:
        """Записать платеж"""
        
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError("Счет не найден")
        
        # Генерируем номер платежа
        payment_number = self._generate_payment_number()
        
        # Создаем платеж
        payment = BillingPayment(
            payment_number=payment_number,
            invoice_id=invoice_id,
            patient_id=invoice.patient_id,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            description=description,
            created_by=created_by
        )
        
        self.db.add(payment)
        
        # Обновляем статус счета
        invoice.paid_amount += amount
        invoice.balance = invoice.total_amount - invoice.paid_amount
        
        if invoice.balance <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_date = datetime.now()
        elif invoice.paid_amount > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        
        self.db.commit()
        self.db.refresh(payment)
        
        return payment
    
    # === Шаблоны счетов ===
    
    def generate_invoice_html(self, invoice_id: int, template_id: int = None) -> str:
        """Сгенерировать HTML счета"""
        
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError("Счет не найден")
        
        # Получаем шаблон
        if template_id:
            template = self.db.query(InvoiceTemplate).filter(
                InvoiceTemplate.id == template_id
            ).first()
        else:
            template = self.db.query(InvoiceTemplate).filter(
                InvoiceTemplate.is_default == True,
                InvoiceTemplate.is_active == True
            ).first()
        
        if not template:
            # Используем базовый шаблон
            template_content = self._get_default_template()
        else:
            template_content = template.template_content
        
        # Подготавливаем данные для шаблона
        settings = self.get_billing_settings()
        
        template_data = {
            'invoice': invoice,
            'patient': invoice.patient,
            'items': invoice.invoice_items,
            'settings': settings,
            'company': {
                'name': settings.company_name,
                'address': settings.company_address,
                'phone': settings.company_phone,
                'email': settings.company_email,
                'website': settings.company_website
            },
            'total_in_words': self._amount_to_words(invoice.total_amount)
        }
        
        # Рендерим шаблон
        jinja_template = Template(template_content)
        html_content = jinja_template.render(**template_data)
        
        return html_content
    
    # === Напоминания ===
    
    def create_payment_reminders(self, invoice_id: int):
        """Создать напоминания об оплате для счета"""
        
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice or not invoice.send_reminders:
            return
        
        settings = self.get_billing_settings()
        
        # Напоминания до срока оплаты
        if settings.reminder_days_before:
            days_before = [int(d.strip()) for d in settings.reminder_days_before.split(',')]
            for days in days_before:
                reminder_date = invoice.due_date - timedelta(days=days)
                if reminder_date > datetime.now():
                    self._create_reminder(
                        invoice_id=invoice_id,
                        reminder_type='email',
                        scheduled_at=reminder_date,
                        days_before_due=days,
                        subject=f'Напоминание об оплате счета {invoice.invoice_number}',
                        message=f'Уважаемый пациент! Напоминаем, что через {days} дней истекает срок оплаты счета {invoice.invoice_number} на сумму {invoice.total_amount} {settings.currency_symbol}.'
                    )
        
        # Напоминания после просрочки
        if settings.reminder_days_after:
            days_after = [int(d.strip()) for d in settings.reminder_days_after.split(',')]
            for days in days_after:
                reminder_date = invoice.due_date + timedelta(days=days)
                self._create_reminder(
                    invoice_id=invoice_id,
                    reminder_type='email',
                    scheduled_at=reminder_date,
                    days_after_due=days,
                    subject=f'Просроченный счет {invoice.invoice_number}',
                    message=f'Уважаемый пациент! Счет {invoice.invoice_number} на сумму {invoice.total_amount} {settings.currency_symbol} просрочен на {days} дней. Просим погасить задолженность.'
                )
    
    def send_due_reminders(self) -> int:
        """Отправить напоминания, которые пора отправлять"""
        
        now = datetime.now()
        
        # Получаем напоминания к отправке
        reminders = self.db.query(PaymentReminder).filter(
            PaymentReminder.is_sent == False,
            PaymentReminder.scheduled_at <= now
        ).all()
        
        sent_count = 0
        
        for reminder in reminders:
            try:
                # Отправляем напоминание
                if reminder.reminder_type == 'email':
                    self._send_email_reminder(reminder)
                elif reminder.reminder_type == 'sms':
                    self._send_sms_reminder(reminder)
                
                # Отмечаем как отправленное
                reminder.is_sent = True
                reminder.sent_at = now
                reminder.delivery_status = 'delivered'
                sent_count += 1
                
            except Exception as e:
                reminder.delivery_status = 'failed'
                print(f"Ошибка отправки напоминания {reminder.id}: {e}")
        
        self.db.commit()
        return sent_count
    
    # === Периодические счета ===
    
    def create_recurring_invoices(self) -> int:
        """Создать периодические счета"""
        
        now = datetime.now()
        
        # Получаем счета для создания периодических
        recurring_invoices = self.db.query(Invoice).filter(
            Invoice.is_recurring == True,
            Invoice.next_invoice_date <= now,
            Invoice.status != InvoiceStatus.CANCELLED
        ).all()
        
        created_count = 0
        
        for parent_invoice in recurring_invoices:
            try:
                # Создаем новый счет на основе родительского
                new_invoice = Invoice(
                    invoice_number=self._generate_invoice_number(self.get_billing_settings()),
                    patient_id=parent_invoice.patient_id,
                    invoice_type=parent_invoice.invoice_type,
                    subtotal=parent_invoice.subtotal,
                    tax_rate=parent_invoice.tax_rate,
                    tax_amount=parent_invoice.tax_amount,
                    total_amount=parent_invoice.total_amount,
                    balance=parent_invoice.total_amount,
                    issue_date=now,
                    due_date=now + timedelta(days=30),
                    description=parent_invoice.description,
                    payment_terms=parent_invoice.payment_terms,
                    is_auto_generated=True,
                    auto_send=parent_invoice.auto_send,
                    send_reminders=parent_invoice.send_reminders,
                    parent_invoice_id=parent_invoice.id
                )
                
                self.db.add(new_invoice)
                self.db.flush()
                
                # Копируем позиции
                for item in parent_invoice.invoice_items:
                    new_item = InvoiceItem(
                        invoice_id=new_invoice.id,
                        service_id=item.service_id,
                        description=item.description,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        discount_rate=item.discount_rate,
                        discount_amount=item.discount_amount,
                        tax_rate=item.tax_rate,
                        tax_amount=item.tax_amount,
                        total_amount=item.total_amount,
                        sort_order=item.sort_order
                    )
                    self.db.add(new_item)
                
                # Обновляем дату следующего счета
                parent_invoice.next_invoice_date = self._calculate_next_recurrence_date(
                    parent_invoice.next_invoice_date,
                    parent_invoice.recurrence_type,
                    parent_invoice.recurrence_interval
                )
                
                created_count += 1
                
                # Автоматически отправляем если нужно
                if new_invoice.auto_send:
                    self.send_invoice(new_invoice.id)
                
            except Exception as e:
                print(f"Ошибка создания периодического счета для {parent_invoice.id}: {e}")
        
        self.db.commit()
        return created_count
    
    # === Утилиты ===
    
    def get_billing_settings(self) -> BillingSettings:
        """Получить настройки биллинга"""
        settings = self.db.query(BillingSettings).first()
        if not settings:
            # Создаем настройки по умолчанию
            settings = BillingSettings()
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        return settings
    
    def _generate_invoice_number(self, settings: BillingSettings) -> str:
        """Сгенерировать номер счета"""
        year = datetime.now().year
        number = settings.next_invoice_number
        
        return settings.invoice_number_format.format(
            prefix=settings.invoice_number_prefix,
            year=year,
            number=number
        )
    
    def _generate_payment_number(self) -> str:
        """Сгенерировать номер платежа"""
        now = datetime.now()
        return f"PAY-{now.year}-{now.month:02d}-{now.day:02d}-{now.hour:02d}{now.minute:02d}{now.second:02d}"
    
    def _get_applicable_billing_rules(self, trigger_event: str, entity) -> List[BillingRule]:
        """Получить применимые правила биллинга"""
        rules = self.db.query(BillingRule).filter(
            BillingRule.is_active == True,
            BillingRule.trigger_event == trigger_event
        ).all()
        
        applicable_rules = []
        
        for rule in rules:
            if self._rule_matches_entity(rule, entity):
                applicable_rules.append(rule)
        
        return applicable_rules
    
    def _rule_matches_entity(self, rule: BillingRule, entity) -> bool:
        """Проверить, подходит ли правило для сущности"""
        # Здесь можно добавить более сложную логику проверки
        # На основе типов услуг, категорий пациентов, сумм и т.д.
        return True
    
    def _create_reminder(self, invoice_id: int, reminder_type: str, scheduled_at: datetime, 
                        days_before_due: int = 0, days_after_due: int = 0, 
                        subject: str = '', message: str = ''):
        """Создать напоминание"""
        reminder = PaymentReminder(
            invoice_id=invoice_id,
            reminder_type=reminder_type,
            days_before_due=days_before_due,
            days_after_due=days_after_due,
            subject=subject,
            message=message,
            scheduled_at=scheduled_at
        )
        self.db.add(reminder)
    
    def _send_email_reminder(self, reminder: PaymentReminder):
        """Отправить напоминание по email"""
        # Здесь интеграция с email сервисом
        pass
    
    def _send_sms_reminder(self, reminder: PaymentReminder):
        """Отправить напоминание по SMS"""
        # Здесь интеграция с SMS сервисом
        pass
    
    def send_invoice(self, invoice_id: int):
        """Отправить счет пациенту"""
        # Здесь логика отправки счета
        pass
    
    def _calculate_next_recurrence_date(self, current_date: datetime, 
                                      recurrence_type: RecurrenceType, 
                                      interval: int) -> datetime:
        """Рассчитать дату следующего периодического счета"""
        if recurrence_type == RecurrenceType.DAILY:
            return current_date + timedelta(days=interval)
        elif recurrence_type == RecurrenceType.WEEKLY:
            return current_date + timedelta(weeks=interval)
        elif recurrence_type == RecurrenceType.MONTHLY:
            return current_date + timedelta(days=30 * interval)  # Упрощенно
        elif recurrence_type == RecurrenceType.QUARTERLY:
            return current_date + timedelta(days=90 * interval)  # Упрощенно
        elif recurrence_type == RecurrenceType.YEARLY:
            return current_date + timedelta(days=365 * interval)  # Упрощенно
        else:
            return current_date + timedelta(days=30)
    
    def _amount_to_words(self, amount: float) -> str:
        """Преобразовать сумму в слова"""
        # Упрощенная реализация
        return f"{int(amount)} сум"
    
    def _get_default_template(self) -> str:
        """Получить базовый шаблон счета"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Счет {{ invoice.invoice_number }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                .invoice-info { margin-bottom: 20px; }
                .table { width: 100%; border-collapse: collapse; }
                .table th, .table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                .table th { background-color: #f2f2f2; }
                .total { text-align: right; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{{ company.name }}</h1>
                <p>{{ company.address }}</p>
                <p>Тел: {{ company.phone }}, Email: {{ company.email }}</p>
            </div>
            
            <div class="invoice-info">
                <h2>Счет № {{ invoice.invoice_number }}</h2>
                <p>Дата: {{ invoice.issue_date.strftime('%d.%m.%Y') }}</p>
                <p>Срок оплаты: {{ invoice.due_date.strftime('%d.%m.%Y') }}</p>
                <p>Пациент: {{ patient.full_name }}</p>
            </div>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Услуга</th>
                        <th>Количество</th>
                        <th>Цена</th>
                        <th>Сумма</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in items %}
                    <tr>
                        <td>{{ item.description }}</td>
                        <td>{{ item.quantity }}</td>
                        <td>{{ item.unit_price }} {{ settings.currency_symbol }}</td>
                        <td>{{ item.total_amount }} {{ settings.currency_symbol }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            <div class="total">
                <p>Итого: {{ invoice.total_amount }} {{ settings.currency_symbol }}</p>
                <p>{{ total_in_words }}</p>
            </div>
        </body>
        </html>
        """
