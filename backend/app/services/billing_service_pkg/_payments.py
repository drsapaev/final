"""Payments mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase
from decimal import Decimal


class PaymentsMixin(BillingServiceMixinBase):
    """Payments methods for BillingService."""

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

        # FOLLOWUP-6: authoritative state machine table extracted to
        # app.services.payment_state_checks (single source of truth).
        # Previously this was an inline dict duplicated only here.
        # The shared ALLOWED_PAYMENT_TRANSITIONS constant and
        # is_valid_payment_transition() function are now the SSOT.
        from app.services.payment_state_checks import (
            ALLOWED_PAYMENT_TRANSITIONS,
            is_valid_payment_transition,
        )

        # PAY-REAUDIT-28 P1-1: неизвестный current_status отклоняется явно.
        # Раньше если current_status не входил в allowed_transitions (None,
        # "", "voided", опечатка), валидация молча пропускалась и принимала
        # любой new_status (включая "" → "refunded").
        if current_status and current_status not in ALLOWED_PAYMENT_TRANSITIONS:
            raise ValueError(
                f"Неизвестный текущий статус '{current_status}' у платежа {payment_id}"
            )

        if current_status in ALLOWED_PAYMENT_TRANSITIONS:
            # Allow same-status transitions (idempotent updates)
            if new_status_lower == current_status:
                # No status change - just update metadata if provided
                pass
            elif not is_valid_payment_transition(current_status, new_status_lower):
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
        current_user: Any = None,
    ) -> Payment:
        """
        Записать платеж для счета.

        Delegates payment creation to
        ``PaymentInvariantService.create_payment_for_visit(commit=False)``.

        This provides:
        - ``with_for_update()`` lock on Visit row (serializes concurrent payments)
        - ``paid_amount`` vs ``total_cost`` check (prevents overpayment)
        - Overpayment policy (allow as advance/deposit, logged at WARNING)
        - ``IntegrityError`` defense-in-depth (degrades to 409)

        The Invoice update logic (paid_amount, balance, status) is preserved
        — ``create_payment_for_visit()`` does NOT touch Invoice, so we update
        it here in the same transaction.

        Args:
            invoice_id: ID of the Invoice to record payment against.
            amount: Payment amount (must be > 0).
            payment_method: PaymentMethod enum or string (cash, card, etc.).
            reference_number: Optional reference number (stored as provider_payment_id).
            description: Optional note for the payment.
            created_by: Optional user ID (deprecated, use current_user).
            current_user: The User object creating the payment (required for
                PaymentInvariantService audit logging). If None, a lightweight
                wrapper with .id=created_by is used for backward compatibility.

        Returns:
            Payment - созданный платеж

        Raises:
            ValueError: if invoice not found or invoice has no visit_id.
            HTTPException: 400/409 from PaymentInvariantService (overpayment,
                concurrent payment race, etc.).
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

        # Delegate to PaymentInvariantService for race-condition protection:
        #   - with_for_update() on Visit row
        #   - paid_amount vs total_cost check
        #   - overpayment policy
        #   - IntegrityError defense-in-depth
        #
        # commit=False because we need to update Invoice in the same transaction.
        # The Visit lock is held until we commit at the end of this method.
        #
        # Note: create_payment_for_visit() sets status='paid' and paid_at automatically.
        # It does not accept receipt_no and provider_payment_id, so we set them after.
        from app.services.payment_invariant_service import PaymentInvariantService

        # Build current_user object if only created_by (int) was provided
        # (backward compatibility for callers that haven't been updated)
        if current_user is None and created_by is not None:
            current_user = type("UserRef", (), {"id": created_by})()
        if current_user is None:
            current_user = type("UserRef", (), {"id": None})()

        payment_service = PaymentInvariantService(self.db)
        payment = payment_service.create_payment_for_visit(
            visit_id=invoice.visit_id,
            amount=Decimal(str(amount)),
            method=method_str,
            note=description,
            current_user=current_user,
            currency=currency,
            provider=None,
            commit=False,
        )

        # Set fields that create_payment_for_visit() doesn't accept
        # (receipt_no and provider_payment_id were in the deprecated method)
        payment.receipt_no = payment_number
        payment.provider_payment_id = reference_number

        # Обновляем статус счета (preserved from original record_payment)
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


