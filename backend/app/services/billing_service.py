"""
Сервис для автоматического выставления счетов
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from jinja2 import Template
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.billing import (
    BillingRule,
    BillingSettings,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    InvoiceTemplate,
    InvoiceType,
    PaymentMethod,
    PaymentReminder,
    RecurrenceType,
)
from app.models.enums import PaymentStatus, VisitStatus

# ✅ ИСПРАВЛЕНО: BillingPayment удален из импортов - используем только Payment из app.models.payment (SSOT)
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.queue_service import queue_service
from app.services.service_mapping import normalize_service_code

logger = logging.getLogger(__name__)


class BillingService:
    """Сервис для управления счетами и автоматическим выставлением"""

    def __init__(self, db: Session):
        self.db = db

    # === Создание счетов ===

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
            issue_date=queue_service.get_local_timestamp(self.db),
            due_date=queue_service.get_local_timestamp(self.db)
            + timedelta(days=due_days),
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

    def create_payment(
        self,
        visit_id: int,
        amount: float,
        currency: str = "UZS",
        method: str = "cash",
        status: str = "paid",
        receipt_no: str | None = None,
        note: str | None = None,
        provider: str | None = None,
        provider_payment_id: str | None = None,
        commit: bool = True,
    ) -> Payment:
        """
        Создание платежа - единая функция для всех типов платежей (SSOT).

        Args:
            visit_id: ID визита
            amount: Сумма платежа
            currency: Валюта (по умолчанию "UZS")
            method: Метод оплаты (по умолчанию "cash")
            status: Статус платежа (по умолчанию "paid")
            receipt_no: Номер чека
            note: Примечание
            provider: Провайдер платежа (для онлайн-платежей)
            provider_payment_id: ID платежа у провайдера
            commit: Коммитить транзакцию (по умолчанию True)

        Returns:
            Payment - созданный платеж

        Raises:
            ValueError: Если визит не найден или данные некорректны
        """
        # Валидация визита
        visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise ValueError(f"Визит {visit_id} не найден")

        # Валидация суммы
        if amount <= 0:
            raise ValueError("Сумма платежа должна быть больше нуля")

        # Создаем платеж
        payment = Payment(
            visit_id=visit_id,
            amount=amount,
            currency=currency,
            method=method,
            status=status,
            receipt_no=receipt_no,
            note=note,
            provider=provider,
            provider_payment_id=provider_payment_id,
        )

        # Устанавливаем paid_at если статус "paid"
        if status == PaymentStatus.PAID.value:
            from app.services.queue_service import queue_service

            payment.paid_at = queue_service.get_local_timestamp(self.db)

        self.db.add(payment)

        if commit:
            self.db.commit()
            self.db.refresh(payment)
        else:
            self.db.flush()

        return payment

    def get_payments_list(
        self,
        visit_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Получить список платежей с обогащением данными (SSOT).

        Args:
            visit_id: Фильтр по ID визита
            date_from: Дата начала (YYYY-MM-DD)
            date_to: Дата окончания (YYYY-MM-DD)
            limit: Лимит записей
            offset: Смещение

        Returns:
            List[Dict[str, Any]] - список платежей с обогащёнными данными
        """
        # ✅ ИСПРАВЛЕНО: Фильтрация по датам теперь на уровне SQL (в crud_list_payments)
        # Получаем платежи через CRUD с фильтрацией по датам
        import logging

        from app.crud.payment import list_payments as crud_list_payments

        logger = logging.getLogger(__name__)

        logger.info(
            f"📊 get_payments_list: запрос с фильтрами visit_id={visit_id}, date_from={date_from}, date_to={date_to}, limit={limit}"
        )

        payments = crud_list_payments(
            self.db,
            visit_id=visit_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

        logger.info(f"📊 get_payments_list: получено платежей из БД: {len(payments)}")

        # ✅ УЛУЧШЕНИЕ: Фильтруем тестовые платежи - показываем только реальные платежи с реальными визитами
        # Исключаем платежи без визитов или с несуществующими визитами
        real_payments = []
        for payment in payments:
            if payment.visit_id:
                visit = (
                    self.db.query(Visit).filter(Visit.id == payment.visit_id).first()
                )
                if visit and visit.patient_id:
                    # Проверяем, что визит связан с реальным пациентом
                    patient = (
                        self.db.query(Patient)
                        .filter(Patient.id == visit.patient_id)
                        .first()
                    )
                    if patient:
                        real_payments.append(payment)
                    else:
                        logger.warning(
                            f"⚠️ Платеж {payment.id}: визит {payment.visit_id} не связан с реальным пациентом (patient_id={visit.patient_id})"
                        )
                else:
                    logger.warning(
                        f"⚠️ Платеж {payment.id}: визит {payment.visit_id} не найден или не имеет patient_id"
                    )
            else:
                logger.warning(f"⚠️ Платеж {payment.id}: не имеет visit_id")

        logger.info(
            f"📊 get_payments_list: после фильтрации реальных платежей: {len(real_payments)}"
        )
        payments = real_payments

        # Обогащаем данные
        from app.models.payment import PaymentVisit

        payment_responses = []
        for payment in payments:
            patient_name = None
            all_service_codes = []
            all_service_names = []
            # ✅ НОВОЕ: Проверяем, связан ли платёж с несколькими визитами через payment_visits
            payment_visits = (
                self.db.query(PaymentVisit)
                .filter(PaymentVisit.payment_id == payment.id)
                .all()
            )

            if payment_visits:
                # Платёж связан с несколькими визитами - собираем все услуги
                for pv in payment_visits:
                    visit = self.db.query(Visit).filter(Visit.id == pv.visit_id).first()
                    if visit:
                        # Получаем информацию о пациенте (из первого визита)
                        if not patient_name and visit.patient_id:
                            patient = (
                                self.db.query(Patient)
                                .filter(Patient.id == visit.patient_id)
                                .first()
                            )
                            if patient:
                                patient_name = (
                                    patient.short_name()
                                    or f"{patient.first_name or ''} {patient.last_name or ''}".strip()
                                )

                        # Собираем все услуги этого визита
                        visit_services = (
                            self.db.query(VisitService)
                            .filter(VisitService.visit_id == visit.id)
                            .all()
                        )
                        for vs in visit_services:
                            if vs.code:
                                # ✅ Нормализуем код через SSOT
                                normalized_code = normalize_service_code(vs.code)
                                all_service_codes.append(normalized_code)
                            if vs.name:
                                all_service_names.append(vs.name)
            else:
                # Старая схема: один платёж = один визит
                if payment.visit_id:
                    visit = (
                        self.db.query(Visit)
                        .filter(Visit.id == payment.visit_id)
                        .first()
                    )
                    if visit:
                        # Получаем информацию о пациенте
                        if visit.patient_id:
                            patient = (
                                self.db.query(Patient)
                                .filter(Patient.id == visit.patient_id)
                                .first()
                            )
                            if patient:
                                patient_name = (
                                    patient.short_name()
                                    or f"{patient.first_name or ''} {patient.last_name or ''}".strip()
                                )

                        # Получаем все услуги визита
                        visit_services = (
                            self.db.query(VisitService)
                            .filter(VisitService.visit_id == visit.id)
                            .all()
                        )
                        for vs in visit_services:
                            if vs.code:
                                # ✅ Нормализуем код через SSOT
                                normalized_code = normalize_service_code(vs.code)
                                all_service_codes.append(normalized_code)
                            if vs.name:
                                all_service_names.append(vs.name)

            # Определяем способ оплаты
            method = 'Наличные'
            if payment.provider:
                method = payment.provider.capitalize()
            elif payment.method:
                if payment.method.lower() == 'cash':
                    method = 'Наличные'
                elif payment.method.lower() == 'card':
                    method = 'Карта'
                else:
                    method = payment.method.capitalize()

            # Формируем строку с кодами услуг
            service_display = (
                ', '.join(all_service_codes) if all_service_codes else 'Услуга'
            )

            # Форматируем дату и время
            time_str = '—'
            date_str = '—'
            if payment.created_at:
                time_str = (
                    payment.created_at.strftime('%H:%M') if payment.created_at else '—'
                )
                date_str = (
                    payment.created_at.strftime('%d.%m.%Y')
                    if payment.created_at
                    else '—'
                )

            # Формируем ответ
            payment_data = {
                'id': payment.id,
                'payment_id': payment.id,
                'time': time_str,
                'date': date_str,  # Добавлено: дата платежа
                'patient': patient_name or 'Неизвестно',
                'service': service_display,
                'services': all_service_codes,  # Массив кодов для tooltip
                'services_names': all_service_names,  # Названия для tooltip
                'amount': float(payment.amount),
                'method': method,
                'status': payment.status,
                'currency': payment.currency,
                'created_at': (
                    payment.created_at.isoformat() if payment.created_at else None
                ),
                'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
                'visit_count': (
                    len(payment_visits) if payment_visits else 1
                ),  # Количество визитов
            }

            payment_responses.append(payment_data)

        return payment_responses

    def is_visit_paid(self, visit: Visit) -> bool:
        """
        Определить, оплачен ли визит (SSOT).

        Использует многоуровневую проверку признаков оплаты:
        1. Статус визита (paid, in_visit, in_progress, completed, done)
        2. payment_processed_at (явный признак оплаты)
        3. Записи в таблице payments (статус 'paid' или наличие paid_at)
        4. discount_mode='paid' в сочетании с другими признаками

        Args:
            visit: Объект Visit для проверки

        Returns:
            True если визит оплачен, False если нет
        """
        is_paid = False

        # Приоритет 1: Проверяем статус визита (используем enum)
        v_status = (getattr(visit, 'status', None) or '').lower()
        paid_statuses = [
            VisitStatus.PAID.value,
            VisitStatus.IN_VISIT.value,
            VisitStatus.IN_PROGRESS.value,
            VisitStatus.COMPLETED.value,
            VisitStatus.DONE.value,
        ]
        if v_status in paid_statuses:
            is_paid = True

        # Приоритет 2: Проверяем payment_processed_at (явный признак оплаты)
        if not is_paid and getattr(visit, 'payment_processed_at', None):
            is_paid = True

        # Приоритет 3: Проверка записей оплаты в таблице payments
        if not is_paid:
            payment_row = (
                self.db.query(Payment)
                .filter(Payment.visit_id == visit.id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            if payment_row:
                payment_status = (
                    str(payment_row.status).lower() if payment_row.status else ''
                )
                if payment_status == 'paid' or payment_row.paid_at:
                    is_paid = True

        # Приоритет 4: Проверяем discount_mode ТОЛЬКО если есть другие признаки оплаты
        if not is_paid:
            discount_mode_value = getattr(visit, 'discount_mode', None)
            v_status = (getattr(visit, 'status', None) or '').lower()

            if discount_mode_value == 'paid' and v_status in paid_statuses:
                is_paid = True
            elif discount_mode_value == 'paid' and getattr(
                visit, 'payment_processed_at', None
            ):
                is_paid = True

        return is_paid

    def get_discount_mode_for_visit(self, visit: Visit) -> str:
        """
        Получить discount_mode для визита (SSOT).

        Args:
            visit: Объект Visit

        Returns:
            discount_mode: none|repeat|benefit|all_free|paid
        """
        # Если визит оплачен, возвращаем 'paid'
        if self.is_visit_paid(visit):
            return 'paid'

        # Иначе возвращаем discount_mode из визита
        return getattr(visit, 'discount_mode', 'none') or 'none'

    def calculate_total(
        self,
        visit_id: int | None = None,
        services: list[dict[str, Any]] | None = None,
        discount_mode: str = "none",
    ) -> dict[str, Any]:
        """
        Расчёт общей суммы визита с учётом скидок (SSOT).

        Может работать с уже созданным визитом (visit_id) или с услугами до создания визита (services).

        Args:
            visit_id: ID визита (если визит уже создан)
            services: Список услуг в формате [{"service_id": int, "quantity": int, "custom_price": Optional[float]}] (если визит ещё не создан)
            discount_mode: Режим скидки (none|repeat|benefit|all_free)

        Returns:
            Dict с ключами: subtotal, discount, total, currency

        Raises:
            ValueError: Если визит не найден или не указаны ни visit_id, ни services
        """
        from decimal import Decimal

        subtotal = Decimal('0')
        original_total = Decimal('0')

        if visit_id:
            # Работаем с уже созданным визитом
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise ValueError(f"Визит {visit_id} не найден")

            # Получаем услуги визита
            visit_services = (
                self.db.query(VisitService)
                .filter(VisitService.visit_id == visit_id)
                .all()
            )

            for visit_service in visit_services:
                # Базовая цена услуги
                base_price = visit_service.price or Decimal('0')
                item_total = base_price * Decimal(visit_service.qty or 1)
                original_total += item_total

                # Применяем скидки
                if (
                    discount_mode == "repeat"
                    and visit_service.code
                    and "consultation" in visit_service.code.lower()
                ):
                    # Повторная консультация бесплатна
                    item_total = Decimal('0')
                elif (
                    discount_mode == "benefit"
                    and visit_service.code
                    and "consultation" in visit_service.code.lower()
                ):
                    # Льготная консультация бесплатна
                    item_total = Decimal('0')
                elif discount_mode == "all_free":
                    # Всё бесплатно
                    item_total = Decimal('0')

                subtotal += item_total

        elif services:
            # Работаем с услугами до создания визита
            for service_item in services:
                service_id = service_item.get('service_id')
                quantity = service_item.get('quantity', 1)
                custom_price = service_item.get('custom_price')

                # Получаем услугу из БД
                service = (
                    self.db.query(Service).filter(Service.id == service_id).first()
                )
                if not service:
                    continue

                # Базовая цена (кастомная или из справочника)
                base_price = (
                    Decimal(str(custom_price))
                    if custom_price
                    else (service.price or Decimal('0'))
                )
                item_total = base_price * Decimal(quantity)
                original_total += item_total

                # Применяем скидки
                if discount_mode == "repeat" and service.is_consultation:
                    # Повторная консультация бесплатна
                    item_total = Decimal('0')
                elif discount_mode == "benefit" and service.is_consultation:
                    # Льготная консультация бесплатна
                    item_total = Decimal('0')
                elif discount_mode == "all_free":
                    # Всё бесплатно
                    item_total = Decimal('0')

                subtotal += item_total
        else:
            raise ValueError("Необходимо указать либо visit_id, либо services")

        # Расчёт скидки
        discount = original_total - subtotal

        total = subtotal
        currency = "UZS"  # По умолчанию

        return {
            "subtotal": float(subtotal),
            "discount": float(discount),
            "total": float(total),
            "currency": currency,
        }

    def validate_payment_amount(
        self,
        visit_id: int,
        amount: float,
    ) -> bool:
        """
        Валидация суммы платежа (SSOT).

        Проверяет, что сумма платежа не превышает сумму визита.

        Args:
            visit_id: ID визита
            amount: Сумма платежа

        Returns:
            True если валидна, False если нет
        """
        try:
            total_info = self.calculate_total(visit_id, discount_mode="none")
            total_amount = total_info["total"]

            # Сумма платежа не должна превышать сумму визита
            if amount > total_amount:
                return False

            # Сумма платежа должна быть больше нуля
            if amount <= 0:
                return False

            return True
        except Exception:
            return False

    def update_payment_status(
        self,
        payment_id: int,
        new_status: str,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Payment:
        """
        Обновление статуса платежа (SSOT).

        Args:
            payment_id: ID платежа
            new_status: Новый статус (pending|processing|paid|failed|cancelled|refunded|void)
            meta: Метаданные (опционально)

        Returns:
            Payment - обновлённый платеж

        Raises:
            ValueError: Если платеж не найден или переход статуса недопустим
        """
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError(f"Платеж {payment_id} не найден")

        # Валидация перехода статуса
        current_status = payment.status.lower() if payment.status else ""
        new_status_lower = new_status.lower()

        # Разрешённые переходы (используем enum для валидации)
        allowed_transitions = {
            PaymentStatus.PENDING.value: [
                PaymentStatus.PROCESSING.value,
                PaymentStatus.PAID.value,
                PaymentStatus.FAILED.value,
                PaymentStatus.CANCELLED.value,
            ],
            PaymentStatus.PROCESSING.value: [
                PaymentStatus.PAID.value,
                PaymentStatus.FAILED.value,
                PaymentStatus.CANCELLED.value,
            ],
            PaymentStatus.PAID.value: [
                PaymentStatus.REFUNDED.value,
                PaymentStatus.VOID.value,
            ],
            PaymentStatus.FAILED.value: [
                PaymentStatus.PENDING.value,
                PaymentStatus.CANCELLED.value,
            ],
            PaymentStatus.CANCELLED.value: [],
            PaymentStatus.REFUNDED.value: [],
            PaymentStatus.VOID.value: [],
        }

        if current_status in allowed_transitions:
            # Allow same-status transitions (idempotent updates)
            if new_status_lower == current_status:
                # No status change - just update metadata if provided
                pass
            elif new_status_lower not in allowed_transitions[current_status]:
                raise ValueError(
                    f"Переход статуса с '{current_status}' на '{new_status}' недопустим"
                )

        # Обновляем статус
        payment.status = new_status

        # Устанавливаем paid_at если статус "paid"
        if new_status_lower == "paid" and not payment.paid_at:
            from app.services.queue_service import queue_service

            payment.paid_at = queue_service.get_local_timestamp(self.db)

        # Обновляем метаданные если переданы
        if meta:
            if payment.provider_data:
                payment.provider_data.update(meta)
            else:
                payment.provider_data = meta

        if commit:
            self.db.commit()
            self.db.refresh(payment)
        else:
            self.db.flush()

        return payment

    def update_visit_discount_mode(
        self,
        visit: Visit,
        force_update: bool = False,
    ) -> bool:
        """
        Обновить discount_mode визита на основе фактического статуса оплаты (SSOT).

        Если визит оплачен (по любым признакам), но discount_mode не установлен как 'paid',
        обновляет discount_mode в базе данных.

        Args:
            visit: Объект Visit для обновления
            force_update: Принудительно обновить даже если discount_mode уже 'paid'

        Returns:
            True если было выполнено обновление, False если нет
        """
        is_paid = self.is_visit_paid(visit)

        if is_paid:
            if visit.discount_mode != 'paid' or force_update:
                visit.discount_mode = 'paid'
                try:
                    self.db.commit()
                    self.db.refresh(visit)
                    return True
                except Exception as e:
                    self.db.rollback()
                    raise ValueError(
                        f"Не удалось сохранить discount_mode для Visit {visit.id}: {e}"
                    )

        return False

    def record_payment(
        self,
        invoice_id: int,
        amount: float,
        payment_method: PaymentMethod,
        reference_number: str = None,
        description: str = None,
        created_by: int = None,
    ) -> Payment:
        """
        Записать платеж для счета.

        Устаревший метод-обертка, теперь использует Payment (SSOT) вместо BillingPayment.
        Платеж привязывается к визиту, связанному с инвойсом (invoice.visit_id).

        Returns:
            Payment - созданный платеж
        """
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError("Счет не найден")

        if not invoice.visit_id:
            raise ValueError(
                "Невозможно записать платеж: у счета нет связанного визита (invoice.visit_id)"
            )

        # Генерируем номер платежа (используем как receipt_no)
        payment_number = self._generate_payment_number()

        # Определяем валюту из настроек биллинга
        settings = self.get_billing_settings()
        currency = settings.currency_code or "UZS"

        # ✅ FIX: Обрабатываем payment_method как enum или строку
        # Если это enum, извлекаем значение; если строка, используем как есть
        if hasattr(payment_method, 'value'):
            method_str = payment_method.value
        elif isinstance(payment_method, str):
            method_str = payment_method
        else:
            raise ValueError(
                f"payment_method must be PaymentMethod enum or string, got {type(payment_method)}"
            )

        # Создаем платеж через SSOT Payment
        payment = self.create_payment(
            visit_id=invoice.visit_id,
            amount=amount,
            currency=currency,
            method=method_str,
            status=PaymentStatus.PAID.value,
            receipt_no=payment_number,
            note=description,
            provider=None,
            provider_payment_id=reference_number,
            commit=False,
        )

        # Обновляем статус счета
        invoice.paid_amount += amount
        invoice.balance = invoice.total_amount - invoice.paid_amount

        if invoice.balance <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_date = queue_service.get_local_timestamp(self.db)
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
            days_before = [
                int(d.strip()) for d in settings.reminder_days_before.split(',')
            ]
            for days in days_before:
                reminder_date = invoice.due_date - timedelta(days=days)
                if reminder_date > queue_service.get_local_timestamp(self.db):
                    self._create_reminder(
                        invoice_id=invoice_id,
                        reminder_type='email',
                        scheduled_at=reminder_date,
                        days_before_due=days,
                        subject=f'Напоминание об оплате счета {invoice.invoice_number}',
                        message=f'Уважаемый пациент! Напоминаем, что через {days} дней истекает срок оплаты счета {invoice.invoice_number} на сумму {invoice.total_amount} {settings.currency_symbol}.',
                    )

        # Напоминания после просрочки
        if settings.reminder_days_after:
            days_after = [
                int(d.strip()) for d in settings.reminder_days_after.split(',')
            ]
            for days in days_after:
                reminder_date = invoice.due_date + timedelta(days=days)
                self._create_reminder(
                    invoice_id=invoice_id,
                    reminder_type='email',
                    scheduled_at=reminder_date,
                    days_after_due=days,
                    subject=f'Просроченный счет {invoice.invoice_number}',
                    message=f'Уважаемый пациент! Счет {invoice.invoice_number} на сумму {invoice.total_amount} {settings.currency_symbol} просрочен на {days} дней. Просим погасить задолженность.',
                )

    def send_due_reminders(self) -> int:
        """Отправить напоминания, которые пора отправлять"""

        now = queue_service.get_local_timestamp(self.db)

        # Получаем напоминания к отправке
        reminders = (
            self.db.query(PaymentReminder)
            .filter(
                PaymentReminder.is_sent == False, PaymentReminder.scheduled_at <= now
            )
            .all()
        )

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
                logger.error(
                    "Ошибка отправки напоминания %d: %s", reminder.id, e, exc_info=True
                )

        self.db.commit()
        return sent_count

    # === Периодические счета ===

    def create_recurring_invoices(self) -> int:
        """Создать периодические счета"""

        now = queue_service.get_local_timestamp(self.db)

        # Получаем счета для создания периодических
        recurring_invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.is_recurring == True,
                Invoice.next_invoice_date <= now,
                Invoice.status != InvoiceStatus.CANCELLED,
            )
            .all()
        )

        created_count = 0

        for parent_invoice in recurring_invoices:
            try:
                # Создаем новый счет на основе родительского
                new_invoice = Invoice(
                    invoice_number=self._generate_invoice_number(
                        self.get_billing_settings()
                    ),
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
                    parent_invoice_id=parent_invoice.id,
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
                        sort_order=item.sort_order,
                    )
                    self.db.add(new_item)

                # Обновляем дату следующего счета
                parent_invoice.next_invoice_date = self._calculate_next_recurrence_date(
                    parent_invoice.next_invoice_date,
                    parent_invoice.recurrence_type,
                    parent_invoice.recurrence_interval,
                )

                created_count += 1

                # Автоматически отправляем если нужно
                if new_invoice.auto_send:
                    self.send_invoice(new_invoice.id)

            except Exception as e:
                logger.error(
                    "Ошибка создания периодического счета для %d: %s",
                    parent_invoice.id,
                    e,
                    exc_info=True,
                )

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
        year = queue_service.get_local_timestamp(self.db).year
        number = settings.next_invoice_number

        return settings.invoice_number_format.format(
            prefix=settings.invoice_number_prefix, year=year, number=number
        )

    def _generate_payment_number(self) -> str:
        """Сгенерировать номер платежа"""
        now = queue_service.get_local_timestamp(self.db)
        return f"PAY-{now.year}-{now.month:02d}-{now.day:02d}-{now.hour:02d}{now.minute:02d}{now.second:02d}"

    def _get_applicable_billing_rules(
        self, trigger_event: str, entity
    ) -> list[BillingRule]:
        """Получить применимые правила биллинга"""
        rules = (
            self.db.query(BillingRule)
            .filter(
                BillingRule.is_active == True,
                BillingRule.trigger_event == trigger_event,
            )
            .all()
        )

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

    def _create_reminder(
        self,
        invoice_id: int,
        reminder_type: str,
        scheduled_at: datetime,
        days_before_due: int = 0,
        days_after_due: int = 0,
        subject: str = '',
        message: str = '',
    ):
        """Создать напоминание"""
        reminder = PaymentReminder(
            invoice_id=invoice_id,
            reminder_type=reminder_type,
            days_before_due=days_before_due,
            days_after_due=days_after_due,
            subject=subject,
            message=message,
            scheduled_at=scheduled_at,
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

    def _calculate_next_recurrence_date(
        self, current_date: datetime, recurrence_type: RecurrenceType, interval: int
    ) -> datetime:
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


# ===== Хелперы для работы с visit и appointment (SSOT) =====


def get_discount_mode_for_visit(db: Session, visit: Visit) -> str:
    """
    Получить discount_mode для визита (SSOT helper function).

    Args:
        db: Database session
        visit: Объект Visit

    Returns:
        discount_mode: none|repeat|benefit|all_free|paid
    """
    billing_service = BillingService(db)
    return billing_service.get_discount_mode_for_visit(visit)


def is_appointment_paid(db: Session, appointment) -> bool:
    """
    Проверить, оплачен ли appointment (SSOT helper function).

    Args:
        db: Database session
        appointment: Объект Appointment

    Returns:
        True если appointment оплачен, False если нет
    """
    # Проверяем payment_processed_at
    if getattr(appointment, 'payment_processed_at', None):
        return True

    # Проверяем visit_type
    visit_type = getattr(appointment, 'visit_type', None) or ''
    if visit_type.lower() == 'paid':
        return True

    # Проверяем статус
    status = getattr(appointment, 'status', None) or ''
    paid_statuses = ['paid', 'completed', 'done']
    if status.lower() in paid_statuses:
        return True

    # Проверяем наличие платежей
    from app.models.payment import Payment

    payment = (
        db.query(Payment)
        .filter(Payment.appointment_id == appointment.id)
        .order_by(Payment.created_at.desc())
        .first()
    )

    if payment:
        payment_status = str(payment.status).lower() if payment.status else ''
        if payment_status == 'paid' or payment.paid_at:
            return True

    return False


def update_appointment_payment_status(db: Session, appointment) -> bool:
    """
    Обновить статус оплаты appointment (SSOT helper function).

    Args:
        db: Database session
        appointment: Объект Appointment

    Returns:
        True если было выполнено обновление, False если нет
    """
    is_paid = is_appointment_paid(db, appointment)

    if is_paid and getattr(appointment, 'visit_type', None) != 'paid':
        appointment.visit_type = 'paid'
        try:
            db.commit()
            db.refresh(appointment)
            return True
        except Exception as e:
            db.rollback()
            raise ValueError(
                f"Не удалось сохранить visit_type для Appointment {appointment.id}: {e}"
            )

    return False


def get_discount_mode_for_appointment(db: Session, appointment) -> str:
    """
    Получить discount_mode для appointment (SSOT helper function).

    Args:
        db: Database session
        appointment: Объект Appointment

    Returns:
        discount_mode: none|repeat|benefit|all_free|paid
    """
    # Если appointment оплачен, возвращаем 'paid'
    if is_appointment_paid(db, appointment):
        return 'paid'

    # Иначе маппим visit_type в discount_mode
    visit_type = getattr(appointment, 'visit_type', None) or 'paid'
    visit_type_lower = visit_type.lower()

    if visit_type_lower == 'paid':
        return 'none'
    elif visit_type_lower == 'repeat':
        return 'repeat'
    elif visit_type_lower == 'free':
        return 'all_free'
    else:
        return 'none'
