"""Payments mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase


class PaymentsMixin(BillingServiceMixinBase):
    """Payments methods for BillingService."""

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
            payment.paid_at = self._get_local_timestamp_naive()

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

        return is_paid


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
        payment = (
            self.db.query(Payment)
            .filter(Payment.id == payment_id)
            .with_for_update()  # PAY-REAUDIT-28 P0-7: SELECT FOR UPDATE — защита от race
            .first()
        )
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

        # PAY-REAUDIT-28 P1-1: неизвестный current_status отклоняется явно.
        # Раньше если current_status не входил в allowed_transitions (None,
        # "", "voided", опечатка), валидация молча пропускалась и принимала
        # любой new_status (включая "" → "refunded").
        if current_status and current_status not in allowed_transitions:
            raise ValueError(
                f"Неизвестный текущий статус '{current_status}' у платежа {payment_id}"
            )

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
            payment.paid_at = self._get_local_timestamp_naive()

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
            invoice.paid_date = self._get_local_timestamp_naive()
        elif invoice.paid_amount > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        self.db.commit()
        self.db.refresh(payment)

        return payment

    # === Шаблоны счетов ===


