# app/services/visit_payment_integration.py
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import MetaData, select, Table, update
from sqlalchemy.orm import Session

from app.crud.appointment import appointment as crud_appointment
from app.crud.payment_webhook import get_webhook_by_id, update_webhook
from app.models.enums import AppointmentStatus
from app.schemas.payment_webhook import PaymentWebhookOut


class VisitPaymentIntegrationService:
    """Сервис для интеграции визитов с платежами"""

    @staticmethod
    def _visits_table(db: Session) -> Table:
        """Получение таблицы визитов"""
        md = MetaData()
        return Table("visits", md, autoload_with=db.get_bind())

    @staticmethod
    def _visit_services_table(db: Session) -> Table:
        """Получение таблицы услуг визита"""
        md = MetaData()
        return Table("visit_services", md, autoload_with=db.get_bind())

    @staticmethod
    def create_visit_from_payment(
        db: Session,
        webhook: PaymentWebhookOut,
        patient_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[int]]:
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
            visits_table = VisitPaymentIntegrationService._visits_table(db)

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
                "payment_processed_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
            }

            # Выполняем вставку
            result = db.execute(visits_table.insert().values(**visit_data))
            db.commit()

            visit_id = result.inserted_primary_key[0]

            # Обновляем статус вебхука
            update_webhook(
                db,
                webhook.id,
                {"status": "visit_created", "processed_at": datetime.utcnow()},
            )

            return True, f"Визит {visit_id} создан успешно", visit_id

        except Exception as e:
            db.rollback()
            return False, f"Ошибка создания визита: {str(e)}", None

    @staticmethod
    def update_visit_payment_status(
        db: Session,
        visit_id: int,
        payment_status: str,
        webhook: Optional[PaymentWebhookOut] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
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
            visits_table = VisitPaymentIntegrationService._visits_table(db)

            # Проверяем существование визита
            visit_query = select(visits_table).where(visits_table.c.id == visit_id)
            visit = db.execute(visit_query).first()

            if not visit:
                return False, f"Визит {visit_id} не найден"

            # Подготавливаем данные для обновления
            update_data = {
                "payment_status": payment_status,
                "payment_processed_at": datetime.utcnow(),
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
                update_data.update(additional_data)

            # Обновляем визит
            db.execute(
                update(visits_table)
                .where(visits_table.c.id == visit_id)
                .values(**update_data)
            )
            db.commit()

            return (
                True,
                f"Статус платежа визита {visit_id} обновлён на '{payment_status}'",
            )

        except Exception as e:
            db.rollback()
            return False, f"Ошибка обновления статуса платежа: {str(e)}"

    @staticmethod
    def get_visit_payment_info(
        db: Session, visit_id: int
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Получение информации о платеже для визита

        Args:
            db: Сессия базы данных
            visit_id: ID визита

        Returns:
            (success, message, payment_info)
        """
        try:
            visits_table = VisitPaymentIntegrationService._visits_table(db)

            # Получаем информацию о визите и платеже
            query = select(
                visits_table.c.id,
                visits_table.c.payment_status,
                visits_table.c.payment_amount,
                visits_table.c.payment_currency,
                visits_table.c.payment_provider,
                visits_table.c.payment_transaction_id,
                visits_table.c.payment_processed_at,
            ).where(visits_table.c.id == visit_id)

            result = db.execute(query).first()

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
            return False, f"Ошибка получения информации о платеже: {str(e)}", None

    @staticmethod
    def process_payment_for_existing_visit(
        db: Session, visit_id: int, webhook: PaymentWebhookOut
    ) -> Tuple[bool, str]:
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
            # Обновляем статус платежа
            success, message = (
                VisitPaymentIntegrationService.update_visit_payment_status(
                    db, visit_id, "paid", webhook
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
                print(f"✅ Статус записи обновлён на 'paid' для визита {visit_id}")

            # Обновляем статус вебхука
            update_webhook(
                db,
                webhook.id,
                {"status": "visit_updated", "processed_at": datetime.utcnow()},
            )

            return True, f"Платёж для визита {visit_id} обработан успешно"

        except Exception as e:
            return False, f"Ошибка обработки платежа: {str(e)}"

    @staticmethod
    def get_visits_by_payment_status(
        db: Session, payment_status: str, limit: int = 100, offset: int = 0
    ) -> Tuple[bool, str, list]:
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
            visits_table = VisitPaymentIntegrationService._visits_table(db)

            # Получаем визиты с указанным статусом платежа
            query = (
                select(visits_table)
                .where(visits_table.c.payment_status == payment_status)
                .order_by(visits_table.c.id.desc())
                .limit(limit)
                .offset(offset)
            )

            results = db.execute(query).fetchall()

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
            return False, f"Ошибка получения визитов: {str(e)}", []

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
            # Ищем запись по visit_id (предполагаем, что visit_id может быть в appointment)
            # Это зависит от структуры данных - возможно нужно добавить поле visit_id в appointments
            appointments_table = VisitPaymentIntegrationService._appointments_table(db)

            # Пытаемся найти запись по visit_id
            query = select(appointments_table).where(
                appointments_table.c.visit_id == visit_id
            )
            appointment = db.execute(query).first()

            if appointment:
                # Обновляем статус через CRUD
                updated_appointment = crud_appointment.update_status(
                    db,
                    appointment_id=appointment.id,
                    new_status=new_status.value,
                    validate_transition=True,
                )
                return updated_appointment is not None

            return False

        except Exception as e:
            print(f"⚠️ Ошибка обновления статуса записи: {e}")
            return False

    @staticmethod
    def _appointments_table(db: Session) -> Table:
        """Получение таблицы записей"""
        md = MetaData()
        return Table("appointments", md, autoload_with=db.get_bind())

    @staticmethod
    def create_appointment_from_payment(
        db: Session,
        webhook: PaymentWebhookOut,
        patient_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        department: Optional[str] = None,
        appointment_date: Optional[str] = None,
        appointment_time: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[int]]:
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

            # Создаём запись через CRUD
            appointment = crud_appointment.create(db, obj_in=appointment_data)

            # Обновляем статус вебхука
            update_webhook(
                db,
                webhook.id,
                {"status": "appointment_created", "processed_at": datetime.utcnow()},
            )

            return True, f"Запись {appointment.id} создана успешно", appointment.id

        except Exception as e:
            db.rollback()
            return False, f"Ошибка создания записи: {str(e)}", None

    @staticmethod
    def process_payment_for_appointment(
        db: Session, appointment_id: int, webhook: PaymentWebhookOut
    ) -> Tuple[bool, str]:
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
            # Обновляем статус записи на "paid"
            updated_appointment = crud_appointment.update_status(
                db,
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
                "payment_processed_at": datetime.utcnow(),
            }

            crud_appointment.update(
                db, db_obj=updated_appointment, obj_in=appointment_update_data
            )

            # Обновляем статус вебхука
            update_webhook(
                db,
                webhook.id,
                {"status": "appointment_updated", "processed_at": datetime.utcnow()},
            )

            return True, f"Платёж для записи {appointment_id} обработан успешно"

        except Exception as e:
            return False, f"Ошибка обработки платежа для записи: {str(e)}"
