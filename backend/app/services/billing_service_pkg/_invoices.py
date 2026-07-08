"""Invoices mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase


class InvoicesMixin(BillingServiceMixinBase):
    """Invoices methods for BillingService."""

    def create_invoice(
        self,
        patient_id: int,
        services: list[dict[str, Any]],
        visit_id: int = None,
        appointment_id: int = None,
        invoice_type: InvoiceType = InvoiceType.STANDARD,
        due_days: int = 30,
        auto_send: bool = False,
        created_by: int = None,
    ) -> Invoice:
        """Создать счет"""

        # Получаем настройки биллинга
        if visit_id is not None:
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise ValueError(f"Visit {visit_id} not found")
            if visit.patient_id != patient_id:
                raise ValueError(
                    "Invoice patient_id does not match visit ownership"
                )

        if appointment_id is not None:
            appointment = (
                self.db.query(Appointment)
                .filter(Appointment.id == appointment_id)
                .first()
            )
            if not appointment:
                raise ValueError(f"Appointment {appointment_id} not found")
            if appointment.patient_id != patient_id:
                raise ValueError(
                    "Invoice patient_id does not match appointment ownership"
                )

        settings = self.get_billing_settings()

        # Генерируем номер счета
        invoice_number = self._generate_invoice_number(settings)

        # Рассчитываем суммы
        subtotal = sum(s.get('quantity', 1) * s.get('unit_price', 0) for s in services)
        tax_amount = (
            subtotal * (settings.default_tax_rate / 100)
            if settings.default_tax_rate
            else 0
        )
        total_amount = subtotal + tax_amount
        now = self._get_local_timestamp_naive()

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
            issue_date=now,
            due_date=now + timedelta(days=due_days),
            auto_send=auto_send,
            is_auto_generated=True,
            created_by=created_by,
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
                tax_amount=(
                    service_data.get('unit_price', 0)
                    * service_data.get('quantity', 1)
                    * (settings.default_tax_rate / 100)
                    if settings.default_tax_rate
                    else 0
                ),
                total_amount=service_data.get('unit_price', 0)
                * service_data.get('quantity', 1),
                sort_order=i,
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


    def auto_generate_invoice_for_visit(self, visit_id: int) -> Invoice | None:
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
            service = (
                self.db.query(Service)
                .filter(Service.id == visit_service.service_id)
                .first()
            )
            if service:
                services.append(
                    {
                        'service_id': service.id,
                        'description': service.name,
                        'quantity': 1,
                        'unit_price': visit_service.price or service.price,
                    }
                )

        if not services:
            return None

        # Создаем счет
        invoice = self.create_invoice(
            patient_id=visit.patient_id,
            services=services,
            visit_id=visit_id,
            due_days=rule.payment_terms_days,
            auto_send=rule.auto_send,
        )

        return invoice


    def auto_generate_invoice_for_appointment(
        self, appointment_id: int
    ) -> Invoice | None:
        """Автоматически создать счет для записи"""

        appointment = (
            self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        )
        if not appointment:
            return None

        # Проверяем правила биллинга
        applicable_rules = self._get_applicable_billing_rules(
            'appointment_created', appointment
        )
        if not applicable_rules:
            return None

        # Берем правило с наивысшим приоритетом
        rule = max(applicable_rules, key=lambda r: r.priority)

        # Получаем услуги из записи
        services = []
        if appointment.service_id:
            service = (
                self.db.query(Service)
                .filter(Service.id == appointment.service_id)
                .first()
            )
            if service:
                services.append(
                    {
                        'service_id': service.id,
                        'description': service.name,
                        'quantity': 1,
                        'unit_price': service.price,
                    }
                )

        if not services:
            return None

        # Создаем счет
        invoice = self.create_invoice(
            patient_id=appointment.patient_id,
            services=services,
            appointment_id=appointment_id,
            due_days=rule.payment_terms_days,
            auto_send=rule.auto_send,
        )

        return invoice

    # === Управление платежами ===


    def generate_invoice_html(self, invoice_id: int, template_id: int = None) -> str:
        """Сгенерировать HTML счета"""

        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError("Счет не найден")

        # Получаем шаблон
        if template_id:
            template = (
                self.db.query(InvoiceTemplate)
                .filter(InvoiceTemplate.id == template_id)
                .first()
            )
        else:
            template = (
                self.db.query(InvoiceTemplate)
                .filter(
                    InvoiceTemplate.is_default == True,
                    InvoiceTemplate.is_active == True,
                )
                .first()
            )

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
                'website': settings.company_website,
            },
            'total_in_words': self._amount_to_words(invoice.total_amount),
        }

        # Рендерим шаблон (autoescape=True prevents SSTI/XSS from patient data)
        env = Environment(autoescape=select_autoescape(["html", "xml"]))
        jinja_template = env.from_string(template_content)
        html_content = jinja_template.render(**template_data)

        return html_content

    # === Напоминания ===


    def send_invoice(self, invoice_id: int):
        """Отправить счет пациенту"""
        # Здесь логика отправки счета
        pass


