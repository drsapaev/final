"""Invoices mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase
from app.services.money_input import MoneyInputError, parse_money


def _snapshot_float(value: Decimal) -> float:
    """Fail closed if the current Float read model changes a cent value."""
    try:
        exact = parse_money(value)
        result = float(exact)
        if Decimal(str(result)) != exact:
            raise MoneyInputError("unrepresentable")
        return result
    except (MoneyInputError, InvalidOperation, ValueError, OverflowError):
        raise HTTPException(status_code=409, detail="Сумму счёта невозможно безопасно сохранить") from None


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
        _visit_snapshot_exact: bool = False,
        *,
        commit: bool = True,
        send_reminders: bool = True,
    ) -> Invoice:
        """Create an invoice. With commit=False, the caller stages and commits it."""

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

        if _visit_snapshot_exact or not commit:
            # Keep first-time settings creation and the number increment in
            # the invoice transaction. Refresh the counter after a PG wait.
            settings_query = self.db.query(BillingSettings).order_by(BillingSettings.id).populate_existing()
            if self.db.get_bind().dialect.name == "postgresql":
                settings_query = settings_query.with_for_update(nowait=_visit_snapshot_exact)
            settings = settings_query.first()
            if settings is None:
                settings = BillingSettings()
                self.db.add(settings)
                self.db.flush()
        else:
            settings = self.get_billing_settings()

        # Генерируем номер счета
        invoice_number = self._generate_invoice_number(settings)

        # Рассчитываем суммы
        if _visit_snapshot_exact:
            try:
                rate = Decimal(str(settings.default_tax_rate or 0))
                if not rate.is_finite() or rate < 0:
                    raise ValueError("invalid tax rate")
                gross_values = [parse_money(s['unit_price']) * s['quantity'] for s in services]
                item_taxes = [gross * rate / Decimal(100) for gross in gross_values]
                exact_subtotal = sum(gross_values, Decimal(0))
                exact_tax = exact_subtotal * rate / Decimal(100)
                subtotal = _snapshot_float(exact_subtotal)
                tax_amount = _snapshot_float(exact_tax)
                total_amount = _snapshot_float(exact_subtotal + exact_tax)
                for gross, tax in zip(gross_values, item_taxes, strict=True):
                    _snapshot_float(gross)
                    _snapshot_float(tax)
            except (MoneyInputError, InvalidOperation, ValueError, ArithmeticError):
                raise HTTPException(status_code=409, detail="Сумму счёта невозможно безопасно сохранить") from None
        else:
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
            send_reminders=send_reminders,
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
                unit_price=(_snapshot_float(service_data['unit_price']) if _visit_snapshot_exact
                            else service_data.get('unit_price', 0)),
                tax_rate=settings.default_tax_rate,
                tax_amount=(_snapshot_float(item_taxes[i]) if _visit_snapshot_exact else (
                    service_data.get('unit_price', 0)
                    * service_data.get('quantity', 1)
                    * (settings.default_tax_rate / 100)
                    if settings.default_tax_rate
                    else 0
                )),
                total_amount=(_snapshot_float(gross_values[i]) if _visit_snapshot_exact else
                              service_data.get('unit_price', 0) * service_data.get('quantity', 1)),
                sort_order=i,
            )
            self.db.add(item)

        # Обновляем номер счета в настройках
        settings.next_invoice_number += 1

        if commit:
            self.db.commit()
            self.db.refresh(invoice)
            if auto_send:
                self.send_invoice(invoice.id)

        return invoice


    def auto_generate_invoice_for_visit(self, visit_id: int) -> Invoice | None:
        """Create an invoice from a transaction-fenced visit snapshot.

        This protects creation, not later price changes: all financial and
        VisitService writers still need the shared re-quote protocol.
        """
        try:
            if self.db.get_bind().dialect.name == "sqlite":
                self.db.execute(text("UPDATE visits SET id=id WHERE 0"))
            visit = (self.db.query(Visit).filter(Visit.id == visit_id)
                     .with_for_update().populate_existing().first())
            if not visit:
                return None
            patient_query = self.db.query(Patient).filter(Patient.id == visit.patient_id)
            if self.db.get_bind().dialect.name == "postgresql":
                # Invoice.patient_id is an FK: fail fast if deletion already
                # holds Patient while its visit FK checks wait on our Visit.
                patient_query = patient_query.with_for_update(read=True, key_share=True, nowait=True)
            if patient_query.first() is None:
                raise HTTPException(status_code=409, detail="Пациент визита недоступен")
            applicable_rules = self._get_applicable_billing_rules('visit_completed', visit)
            if not applicable_rules:
                return None
            rule = max(applicable_rules, key=lambda r: r.priority)

            query = (self.db.query(VisitService).filter(VisitService.visit_id == visit.id)
                     .order_by(VisitService.id).populate_existing())
            if self.db.get_bind().dialect.name == "postgresql":
                # A child UPDATE/DELETE can already hold its row and wait on
                # the visit via 0102. Never wait for that child after Visit.
                query = query.with_for_update(nowait=True)
            lines = query.all()
            if not lines:
                return None
            service_ids = {line.service_id for line in lines}
            service_query = (self.db.query(Service).filter(Service.id.in_(service_ids))
                             .order_by(Service.id).populate_existing())
            if self.db.get_bind().dialect.name == "postgresql":
                # InvoiceItem.service_id is an FK; take the compatible FK
                # key locks without waiting behind a concurrent deletion.
                service_query = service_query.with_for_update(read=True, key_share=True, nowait=True)
            services_by_id = {service.id: service for service in service_query.all()}
            if len(services_by_id) != len(service_ids):
                raise HTTPException(status_code=409, detail="Услуга визита недоступна")
            services = []
            for line in lines:
                if type(line.qty) is not int or line.qty < 1 or line.qty > 2147483647:
                    raise HTTPException(status_code=409, detail="Количество услуги визита недоступно")
                try:
                    price = parse_money(line.price)
                except MoneyInputError:
                    raise HTTPException(status_code=409, detail="Цена услуги визита недоступна") from None
                services.append({
                    'service_id': line.service_id,
                    'description': line.name,
                    'quantity': line.qty,
                    'unit_price': price,
                })
            return self.create_invoice(
                patient_id=visit.patient_id, services=services, visit_id=visit_id,
                due_days=rule.payment_terms_days, auto_send=rule.auto_send,
                _visit_snapshot_exact=True,
            )
        except DBAPIError as exc:
            self.db.rollback()
            dialect = self.db.get_bind().dialect.name
            pg_code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            sqlite_code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
            if ((dialect == "postgresql" and pg_code == "55P03")
                or (dialect == "sqlite" and sqlite_code & 255 in (5, 6))):
                raise HTTPException(status_code=409, detail="Данные визита изменяются, повторите запрос") from None
            raise
        except Exception:
            self.db.rollback()
            raise


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


