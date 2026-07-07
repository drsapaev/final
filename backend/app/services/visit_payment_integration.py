# app/services/visit_payment_integration.py
import asyncio
import logging
from datetime import datetime, UTC
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import AppointmentStatus
from app.repositories.visit_payment_integration_repository import (
    VisitPaymentIntegrationRepository,
)
from app.schemas.payment_webhook import PaymentWebhookOut

logger = logging.getLogger(__name__)


class VisitPaymentIntegrationService:
    """Сервис для интеграции визитов с платежами"""

    IMMUTABLE_VISIT_PAYMENT_FIELDS = frozenset(
        {
            "id",
            "patient_id",
            "doctor_id",
            "created_at",
            "source",
        }
    )

    @staticmethod
    def _repo(db: Session) -> VisitPaymentIntegrationRepository:
        return VisitPaymentIntegrationRepository(db)

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _row_value(row: Any, field_name: str) -> Any:
        if row is None:
            return None
        if hasattr(row, field_name):
            return getattr(row, field_name)

        mapping = getattr(row, "_mapping", None)
        if mapping is not None:
            try:
                if field_name in mapping:
                    return mapping[field_name]
            except TypeError:
                pass

        return None

    @staticmethod
    def _format_webhook_amount(amount: Any) -> str | None:
        try:
            value = float(amount) / 100
        except (TypeError, ValueError):
            return None

        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"

    @staticmethod
    def _payment_status_event_type(payment_status: str) -> str:
        normalized = str(payment_status or "").strip().lower()
        if normalized in {"paid", "processed", "success", "completed"}:
            return "payment_paid"
        return "payment_notification"

    @staticmethod
    def _payment_status_metadata(
        payment_status: str, webhook: PaymentWebhookOut | None
    ) -> dict[str, str]:
        metadata = {"status": str(payment_status or "updated")}
        if webhook is None:
            return metadata

        amount = VisitPaymentIntegrationService._format_webhook_amount(
            getattr(webhook, "amount", None)
        )
        if amount is not None:
            metadata["amount"] = amount

        currency = str(getattr(webhook, "currency", "") or "").strip()
        if currency:
            metadata["currency"] = currency

        provider = str(getattr(webhook, "provider", "") or "").strip()
        if provider:
            metadata["provider"] = provider

        return metadata

    @staticmethod
    def _dispatch_patient_payment_status_notification(
        *,
        db: Session,
        patient_id: int | None,
        payment_status: str,
        webhook: PaymentWebhookOut | None,
    ) -> None:
        patient_id = VisitPaymentIntegrationService._safe_int(patient_id)
        if patient_id is None:
            return

        event_type = VisitPaymentIntegrationService._payment_status_event_type(
            payment_status
        )
        metadata = VisitPaymentIntegrationService._payment_status_metadata(
            payment_status, webhook
        )

        async def _send() -> None:
            from app.services.notifications import notification_sender_service

            await notification_sender_service.send_patient_telegram_event_notification(
                db=db,
                patient_id=patient_id,
                event_type=event_type,
                metadata=metadata,
            )

        def _log_failure(exc: BaseException) -> None:
            logger.warning(
                "Patient payment Telegram status notification failed",
                extra={
                    "event_type": event_type,
                    "payment_status": payment_status,
                    "error_type": type(exc).__name__,
                },
            )

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                asyncio.run(_send())
            except Exception as exc:
                _log_failure(exc)
            return

        async def _send_detached() -> None:
            from app.db.session import SessionLocal
            from app.services.notifications import notification_sender_service

            detached_db = SessionLocal()
            try:
                await notification_sender_service.send_patient_telegram_event_notification(
                    db=detached_db,
                    patient_id=patient_id,
                    event_type=event_type,
                    metadata=metadata,
                )
            finally:
                detached_db.close()

        task = running_loop.create_task(_send_detached())

        def _handle_task_result(done_task: asyncio.Task) -> None:
            try:
                done_task.result()
            except Exception as exc:
                _log_failure(exc)

        task.add_done_callback(_handle_task_result)

    @staticmethod
    def _resolve_appointment_patient_id(
        db: Session,
        appointment_id: int,
        webhook: PaymentWebhookOut | None,
    ) -> int | None:
        try:
            from app.models.appointment import Appointment

            patient_id = (
                db.query(Appointment.patient_id)
                .filter(Appointment.id == appointment_id)
                .scalar()
            )
            return VisitPaymentIntegrationService._safe_int(patient_id)
        except Exception as exc:
            logger.warning(
                "Appointment patient lookup for payment Telegram notification failed",
                extra={"error_type": type(exc).__name__},
            )
            return VisitPaymentIntegrationService._safe_int(
                getattr(webhook, "patient_id", None)
            )

    @staticmethod
    def create_visit_from_payment(
        db: Session,
        webhook: PaymentWebhookOut,
        patient_id: int | None = None,
        doctor_id: int | None = None,
        notes: str | None = None,
    ) -> tuple[bool, str, int | None]:
        """
        Создание визита на основе успешного платежа

        Args:
            db: Сессия базы данных
            webhook: Обработанный вебхук
            patient_id: ID пациента (если известен)
            doctor_id: ID врача (если известен)
            notes: Заметки к визиту

        Returns:
            (success, message, visit_id)
        """
        try:
            repo = VisitPaymentIntegrationService._repo(db)

            # Создаём визит с информацией о платеже
            visit_data = {
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "status": "open",  # Визит открыт после оплаты
                "notes": notes
                or f"Визит создан автоматически после оплаты через {webhook.provider}",
                "payment_status": "paid",
                "payment_amount": float(webhook.amount)
                / 100,  # Конвертируем из тийинов
                "payment_currency": webhook.currency,
                "payment_provider": webhook.provider,
                "payment_transaction_id": webhook.transaction_id,
                "payment_webhook_id": webhook.id,
                "payment_processed_at": datetime.now(UTC),
                "created_at": datetime.now(UTC),
            }

            visit_id = repo.insert_visit(visit_data)
            db.commit()

            # Обновляем статус вебхука
            repo.update_webhook_status(webhook_id=webhook.id, status="visit_created")

            return True, f"Визит {visit_id} создан успешно", visit_id

        except Exception as e:
            db.rollback()
            logger.warning(
                "Visit creation from payment failed webhook_id=%s provider=%s error_type=%s",
                getattr(webhook, "id", None),
                getattr(webhook, "provider", None),
                type(e).__name__,
            )
            return False, "Ошибка создания визита", None

    @staticmethod
    def update_visit_payment_status(
        db: Session,
        visit_id: int,
        payment_status: str,
        webhook: PaymentWebhookOut | None = None,
        additional_data: dict[str, Any] | None = None,
        *,
        notify_patient: bool = False,
    ) -> tuple[bool, str]:
        """
        Обновление статуса платежа для существующего визита

        Args:
            db: Сессия базы данных
            visit_id: ID визита
            payment_status: Новый статус платежа
            webhook: Вебхук (если есть)
            additional_data: Дополнительные данные для обновления

        Returns:
            (success, message)
        """
        try:
            repo = VisitPaymentIntegrationService._repo(db)

            # Проверяем существование визита
            visit = repo.get_visit(visit_id)

            if not visit:
                return False, f"Визит {visit_id} не найден"

            # Подготавливаем данные для обновления
            update_data = {
                "payment_status": payment_status,
                "payment_processed_at": datetime.now(UTC),
            }

            # Добавляем данные из вебхука, если есть
            if webhook:
                update_data.update(
                    {
                        "payment_amount": float(webhook.amount) / 100,
                        "payment_currency": webhook.currency,
                        "payment_provider": webhook.provider,
                        "payment_transaction_id": webhook.transaction_id,
                        "payment_webhook_id": webhook.id,
                    }
                )

            # Добавляем дополнительные данные
            if additional_data:
                forbidden_fields = (
                    set(additional_data)
                    & VisitPaymentIntegrationService.IMMUTABLE_VISIT_PAYMENT_FIELDS
                )
                if forbidden_fields:
                    logger.warning(
                        "Rejected visit payment ownership update visit_id=%s fields=%s",
                        visit_id,
                        sorted(forbidden_fields),
                    )
                    return (
                        False,
                        "Cannot change visit ownership through payment status update",
                    )
                update_data.update(additional_data)

            # Обновляем визит
            repo.update_visit(visit_id, update_data)
            db.commit()

            if notify_patient:
                patient_id = VisitPaymentIntegrationService._safe_int(
                    VisitPaymentIntegrationService._row_value(visit, "patient_id")
                )
                VisitPaymentIntegrationService._dispatch_patient_payment_status_notification(
                    db=db,
                    patient_id=patient_id,
                    payment_status=payment_status,
                    webhook=webhook,
                )

            return (
                True,
                f"Статус платежа визита {visit_id} обновлён на '{payment_status}'",
            )

        except Exception as e:
            db.rollback()
            logger.warning(
                "Visit payment status update failed visit_id=%s payment_status=%s error_type=%s",
                visit_id,
                payment_status,
                type(e).__name__,
            )
            return False, "Ошибка обновления статуса платежа"

    @staticmethod
    def get_visit_payment_info(
        db: Session, visit_id: int
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """
        Получение информации о платеже для визита

        Args:
            db: Сессия базы данных
            visit_id: ID визита

        Returns:
            (success, message, payment_info)
        """
        try:
            repo = VisitPaymentIntegrationService._repo(db)
            result = repo.get_visit_payment_projection(visit_id)

            if not result:
                return False, f"Визит {visit_id} не найден", None

            payment_info = {
                "visit_id": result.id,
                "payment_status": result.payment_status,
                "payment_amount": result.payment_amount,
                "payment_currency": result.payment_currency,
                "payment_provider": result.payment_provider,
                "payment_transaction_id": result.payment_transaction_id,
                "payment_processed_at": result.payment_processed_at,
            }

            return True, "Информация о платеже получена", payment_info

        except Exception as e:
            logger.warning(
                "Visit payment info lookup failed visit_id=%s error_type=%s",
                visit_id,
                type(e).__name__,
            )
            return False, "Ошибка получения информации о платеже", None

    @staticmethod
    def process_payment_for_existing_visit(
        db: Session, visit_id: int, webhook: PaymentWebhookOut
    ) -> tuple[bool, str]:
        """
        Обработка платежа для существующего визита

        Args:
            db: Сессия базы данных
            visit_id: ID визита
            webhook: Обработанный вебхук

        Returns:
            (success, message)
        """
        try:
            repo = VisitPaymentIntegrationService._repo(db)

            # Обновляем статус платежа
            success, message = (
                VisitPaymentIntegrationService.update_visit_payment_status(
                    db, visit_id, "paid", webhook, notify_patient=True
                )
            )

            if not success:
                return False, message

            # Ищем связанную запись (appointment) и обновляем её статус
            appointment_updated = (
                VisitPaymentIntegrationService.update_related_appointment_status(
                    db, visit_id, AppointmentStatus.PAID
                )
            )

            if appointment_updated:
                logger.info(
                    "Related appointment status updated after visit payment visit_id=%s status=%s",
                    visit_id,
                    AppointmentStatus.PAID.value,
                )

            # Обновляем статус вебхука
            repo.update_webhook_status(webhook_id=webhook.id, status="visit_updated")

            return True, f"Платёж для визита {visit_id} обработан успешно"

        except Exception as e:
            logger.warning(
                "Existing visit payment processing failed visit_id=%s webhook_id=%s error_type=%s",
                visit_id,
                getattr(webhook, "id", None),
                type(e).__name__,
            )
            return False, "Ошибка обработки платежа"

    @staticmethod
    def get_visits_by_payment_status(
        db: Session, payment_status: str, limit: int = 100, offset: int = 0
    ) -> tuple[bool, str, list]:
        """
        Получение визитов по статусу платежа

        Args:
            db: Сессия базы данных
            payment_status: Статус платежа для фильтрации
            limit: Лимит результатов
            offset: Смещение

        Returns:
            (success, message, visits)
        """
        try:
            repo = VisitPaymentIntegrationService._repo(db)
            results = repo.list_visits_by_payment_status(
                payment_status=payment_status,
                limit=limit,
                offset=offset,
            )

            visits = []
            for row in results:
                visit_data = dict(row._mapping)
                visits.append(visit_data)

            return (
                True,
                f"Найдено {len(visits)} визитов со статусом '{payment_status}'",
                visits,
            )

        except Exception as e:
            logger.warning(
                "Visit payment status listing failed payment_status=%s error_type=%s",
                payment_status,
                type(e).__name__,
            )
            return False, "Ошибка получения визитов", []

    @staticmethod
    def update_related_appointment_status(
        db: Session, visit_id: int, new_status: AppointmentStatus
    ) -> bool:
        """
        Обновление статуса связанной записи (appointment) по ID визита

        Args:
            db: Сессия базы данных
            visit_id: ID визита
            new_status: Новый статус записи

        Returns:
            True если запись найдена и обновлена, False иначе
        """
        try:
            repo = VisitPaymentIntegrationService._repo(db)
            appointment = repo.find_appointment_by_visit_id(visit_id)

            if appointment:
                return repo.update_appointment_status(
                    appointment_id=appointment.id,
                    new_status=new_status.value,
                    validate_transition=True,
                )

            return False

        except Exception as e:
            logger.warning(
                "Related appointment status update failed visit_id=%s error_type=%s",
                visit_id,
                type(e).__name__,
            )
            return False

    @staticmethod
    def create_appointment_from_payment(
        db: Session,
        webhook: PaymentWebhookOut,
        patient_id: int | None = None,
        doctor_id: int | None = None,
        department: str | None = None,
        appointment_date: str | None = None,
        appointment_time: str | None = None,
    ) -> tuple[bool, str, int | None]:
        """
        Создание записи (appointment) на основе успешного платежа

        Args:
            db: Сессия базы данных
            webhook: Обработанный вебхук
            patient_id: ID пациента
            doctor_id: ID врача
            department: Отделение
            appointment_date: Дата записи (YYYY-MM-DD)
            appointment_time: Время записи (HH:MM)

        Returns:
            (success, message, appointment_id)
        """
        try:
            from app.schemas.appointment import AppointmentCreate

            repo = VisitPaymentIntegrationService._repo(db)

            # Создаём запись со статусом "paid" (уже оплачена)
            appointment_data = AppointmentCreate(
                patient_id=patient_id,
                doctor_id=doctor_id,
                department=department or "General",
                appointment_date=appointment_date
                or datetime.now().strftime("%Y-%m-%d"),
                appointment_time=appointment_time or "09:00",
                status=AppointmentStatus.PAID.value,  # Сразу помечаем как оплаченную
                notes=f"Запись создана автоматически после оплаты через {webhook.provider}",
                payment_amount=float(webhook.amount) / 100,
                payment_currency=webhook.currency,
                payment_provider=webhook.provider,
                payment_transaction_id=webhook.transaction_id,
            )

            appointment = repo.create_appointment(appointment_data)

            # Обновляем статус вебхука
            repo.update_webhook_status(
                webhook_id=webhook.id, status="appointment_created"
            )

            return True, f"Запись {appointment.id} создана успешно", appointment.id

        except Exception as e:
            db.rollback()
            logger.warning(
                "Appointment creation from payment failed webhook_id=%s provider=%s error_type=%s",
                getattr(webhook, "id", None),
                getattr(webhook, "provider", None),
                type(e).__name__,
            )
            return False, "Ошибка создания записи", None

    @staticmethod
    def process_payment_for_appointment(
        db: Session, appointment_id: int, webhook: PaymentWebhookOut
    ) -> tuple[bool, str]:
        """
        Обработка платежа для существующей записи (appointment)

        Args:
            db: Сессия базы данных
            appointment_id: ID записи
            webhook: Обработанный вебхук

        Returns:
            (success, message)
        """
        try:
            repo = VisitPaymentIntegrationService._repo(db)

            # Обновляем статус записи на "paid"
            updated_appointment = repo.update_appointment_status(
                appointment_id=appointment_id,
                new_status=AppointmentStatus.PAID.value,
                validate_transition=True,
            )

            if not updated_appointment:
                return (
                    False,
                    f"Запись {appointment_id} не найдена или не может быть обновлена",
                )

            # Обновляем информацию о платеже в записи
            appointment_update_data = {
                "payment_amount": float(webhook.amount) / 100,
                "payment_currency": webhook.currency,
                "payment_provider": webhook.provider,
                "payment_transaction_id": webhook.transaction_id,
                "payment_webhook_id": webhook.id,
                "payment_processed_at": datetime.now(UTC),
            }

            repo.update_appointment_fields(
                appointment_id=appointment_id,
                values=appointment_update_data,
            )

            # Обновляем статус вебхука
            repo.update_webhook_status(webhook_id=webhook.id, status="appointment_updated")
            db.commit()

            patient_id = VisitPaymentIntegrationService._resolve_appointment_patient_id(
                db, appointment_id, webhook
            )
            VisitPaymentIntegrationService._dispatch_patient_payment_status_notification(
                db=db,
                patient_id=patient_id,
                payment_status="paid",
                webhook=webhook,
            )

            return True, f"Платёж для записи {appointment_id} обработан успешно"

        except Exception as e:
            logger.warning(
                "Appointment payment processing failed has_webhook=%s error_type=%s",
                webhook is not None,
                type(e).__name__,
            )
            return False, "Ошибка обработки платежа для записи"
