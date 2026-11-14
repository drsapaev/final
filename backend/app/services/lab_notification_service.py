"""
Lab Results Auto-Notification Service
Сервис автоматических уведомлений о готовности анализов
"""
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.lab import LabOrder, LabResult
from app.models.notification import (
    NotificationDelivery,
    NotificationEvent,
    NotificationHistory,
)
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.notifications import notification_sender_service

logger = logging.getLogger(__name__)


def _as_aware_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    SQLAlchemy ``DateTime(timezone=True)`` columns return aware datetimes on
    PostgreSQL but naive datetimes on SQLite (used by the test suite). Mixing
    naive and aware datetimes in comparisons or arithmetic raises
    ``TypeError``. Normalize every datetime read from the database to aware
    UTC before comparing with ``datetime.now(UTC)``.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class LabNotificationService:
    """
    Сервис автоматических уведомлений о результатах анализов

    Функции:
    - Уведомление пациента о готовности результатов
    - Уведомление врача о критических значениях
    - Напоминание о повторных анализах
    - Уведомление о просроченных результатах
    """

    # Критические значения для основных показателей
    CRITICAL_VALUES = {
        "glucose": {"low": 3.0, "high": 20.0, "unit": "mmol/L"},
        "hemoglobin": {"low": 70, "high": 200, "unit": "g/L"},
        "potassium": {"low": 2.5, "high": 6.5, "unit": "mmol/L"},
        "sodium": {"low": 120, "high": 160, "unit": "mmol/L"},
        "creatinine": {"low": 20, "high": 500, "unit": "umol/L"},
        "wbc": {"low": 2.0, "high": 30.0, "unit": "10^9/L"},
        "platelets": {"low": 50, "high": 1000, "unit": "10^9/L"},
        "inr": {"low": 0.5, "high": 5.0, "unit": ""},
    }

    def __init__(self, db: Session):
        self.db = db

    def _lab_inbox_delivery_exists(
        self,
        *,
        event_type: str,
        recipient_id: int,
        entity_id: int,
        expected_value: float | None = None,
    ) -> bool:
        snapshots = (
            self.db.query(NotificationEvent.payload_snapshot)
            .select_from(NotificationEvent)
            .join(
                NotificationDelivery,
                NotificationDelivery.event_id == NotificationEvent.id,
            )
            .filter(
                NotificationDelivery.recipient_type == "user",
                NotificationDelivery.recipient_id == recipient_id,
                NotificationDelivery.channel == "in_app_inbox",
                NotificationEvent.event_type == event_type,
                NotificationEvent.source_module == "lab",
                NotificationEvent.entity_type == "lab_result",
                NotificationEvent.entity_id == str(entity_id),
            )
            .all()
        )
        if expected_value is None:
            return bool(snapshots)
        return any(
            ((snapshot or {}).get("metadata") or {}).get("value") == expected_value
            for (snapshot,) in snapshots
        )

    def _lab_sms_delivery_exists(self, *, patient_id: int, order_id: int) -> bool:
        return (
            self.db.query(NotificationHistory.id)
            .filter(
                NotificationHistory.recipient_type == "patient",
                NotificationHistory.recipient_id == patient_id,
                NotificationHistory.notification_type == "lab_results",
                NotificationHistory.channel == "sms",
                NotificationHistory.related_entity_type == "lab_order",
                NotificationHistory.related_entity_id == order_id,
                NotificationHistory.status.in_(["sent", "delivered"]),
            )
            .first()
            is not None
        )

    async def check_and_notify_ready_results(self) -> dict[str, Any]:
        """
        Проверяет готовые результаты и отправляет уведомления пациентам

        Returns:
            Статистика отправленных уведомлений
        """
        try:
            # Existing inbox/SMS history records are the durable dedup markers;
            # this scheduler can safely revisit completed orders after retries.
            ready_orders = self.db.query(LabOrder).filter(LabOrder.status == "completed").all()

            notifications_sent = 0
            errors = []

            for order in ready_orders:
                try:
                    if await self._notify_patient_results_ready(order):
                        notifications_sent += 1
                except Exception as e:
                    errors.append({"order_id": order.id, "error": str(e)})

            self.db.commit()

            return {
                "total_checked": len(ready_orders),
                "notifications_sent": notifications_sent,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Error checking ready results: {e}")
            return {"error": str(e)}

    async def _notify_patient_results_ready(self, order: LabOrder) -> bool:
        """Отправляет уведомление пациенту о готовности результатов"""
        patient = self.db.query(Patient).filter(Patient.id == order.patient_id).first()

        if not patient:
            return False

        newly_delivered = False

        # Получаем пользователя пациента
        user = None
        if patient.user_id:
            user = self.db.query(User).filter(User.id == patient.user_id).first()

        # Отправляем через доступные каналы
        if user:
            canonical_recorded = self._lab_inbox_delivery_exists(
                event_type="lab_results",
                recipient_id=user.id,
                entity_id=order.id,
            )
            if canonical_recorded:
                logger.debug(
                    "Lab result inbox delivery already exists for order %s",
                    order.id,
                )
            else:
                canonical_recorded = await notification_sender_service.send_lab_event_notification(
                    db=self.db,
                    recipient=user,
                    event_type="lab_results",
                    title="Результаты анализов готовы",
                    message=f"Результаты лабораторных исследований по заказу #{order.id} готовы.",
                    metadata={
                        "order_id": order.id,
                        "patient_id": order.patient_id,
                        "result_id": None,
                    },
                )
                newly_delivered = canonical_recorded
                if not canonical_recorded:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] lab_results canonical delivery failed",
                        extra={"order_id": order.id, "patient_user_id": user.id},
                    )
            if canonical_recorded and not self._lab_inbox_delivery_exists(
                event_type="lab_result_sent_confirmation",
                recipient_id=user.id,
                entity_id=order.id,
            ):
                confirmation_created = await notification_sender_service.send_lab_event_notification(
                    db=self.db,
                    recipient=user,
                    event_type="lab_result_sent_confirmation",
                    title="Результат исследования отправлен",
                    message=f"Результаты по заказу #{order.id} отправлены в личный кабинет.",
                    metadata={
                        "order_id": order.id,
                        "patient_id": order.patient_id,
                        "result_id": None,
                    },
                )
                newly_delivered = newly_delivered or confirmation_created
                if not confirmation_created:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] lab_result_sent_confirmation canonical delivery failed",
                        extra={"order_id": order.id, "patient_user_id": user.id},
                    )

        # SMS если есть телефон
        sms_opted_in = patient.phone and notification_sender_service._patient_channel_opted_in(
            db=self.db,
            patient_id=patient.id,
            channel="sms",
            event_type="lab_results",
        )
        sms_already_delivered = bool(
            patient.phone
            and self._lab_sms_delivery_exists(
                patient_id=patient.id,
                order_id=order.id,
            )
        )
        if sms_opted_in:
            _short_message = f"Ваши анализы готовы! Заказ #{order.id}. Просмотр в личном кабинете."
            if sms_already_delivered:
                logger.debug(
                    "Lab result SMS delivery already exists for order %s",
                    order.id,
                )
            else:
                # NOTIF-REAUDIT-28 P1-5: patients without a linked app still
                # receive SMS, while persisted history prevents scheduler repeats.
                try:
                    sms_sent = await notification_sender_service.send_sms(
                        patient.phone, _short_message
                    )
                    if sms_sent:
                        self.db.add(
                            NotificationHistory(
                                recipient_type="patient",
                                recipient_id=patient.id,
                                recipient_contact=patient.phone,
                                notification_type="lab_results",
                                channel="sms",
                                subject="Результаты анализов готовы",
                                content=_short_message,
                                status="sent",
                                related_entity_type="lab_order",
                                related_entity_id=order.id,
                                notification_metadata={"order_id": order.id},
                                sent_at=datetime.now(UTC).replace(tzinfo=None),
                            )
                        )
                        self.db.flush()
                        newly_delivered = True
                    else:
                        logger.warning(
                            "Lab result SMS delivery failed for patient %s",
                            patient.id,
                        )
                except Exception as sms_err:
                    logger.warning(
                        "Lab result SMS delivery failed for patient %s: %s",
                        patient.id,
                        sms_err,
                    )
        elif patient.phone:
            logger.info(
                "Lab result SMS skipped by patient preferences for patient %s",
                patient.id,
            )

        if newly_delivered:
            logger.info(
                "Lab result notification delivered for order %s",
                order.id,
            )
        elif not user and not sms_already_delivered:
            logger.warning(
                "Lab result notification was not delivered for order %s",
                order.id,
            )
        return newly_delivered

    async def check_critical_values(self) -> dict[str, Any]:
        """
        Проверяет результаты на критические значения и уведомляет врачей

        Returns:
            Список критических результатов
        """
        try:
            # Находим результаты за последние 24 часа
            yesterday = datetime.now(UTC) - timedelta(hours=24)

            recent_results = self.db.query(LabResult).filter(LabResult.created_at >= yesterday).all()

            critical_found = []

            for result in recent_results:
                # Проверяем на критические значения
                test_name = result.test_name.lower() if result.test_name else ""

                for marker, thresholds in self.CRITICAL_VALUES.items():
                    if marker in test_name:
                        try:
                            value = float(result.value)
                            if value < thresholds["low"] or value > thresholds["high"]:
                                order = self.db.query(LabOrder).filter(LabOrder.id == result.order_id).first()
                                patient_id = order.patient_id if order else None
                                critical_found.append({
                                    "result_id": result.id,
                                    "patient_id": patient_id,
                                    "test_name": result.test_name,
                                    "value": value,
                                    "unit": thresholds["unit"],
                                    "is_low": value < thresholds["low"],
                                    "is_high": value > thresholds["high"],
                                })

                                # Уведомляем врача
                                await self._notify_doctor_critical_value(result, value, thresholds)
                        except (ValueError, TypeError):
                            pass

            self.db.commit()

            return {
                "checked": len(recent_results),
                "critical_found": len(critical_found),
                "critical_results": critical_found,
            }

        except Exception as e:
            logger.error(f"Error checking critical values: {e}")
            return {"error": str(e)}

    async def _notify_doctor_critical_value(
        self,
        result: LabResult,
        value: float,
        thresholds: dict,
    ):
        """Уведомляет врача о критическом значении"""
        order = self.db.query(LabOrder).filter(LabOrder.id == result.order_id).first()
        if not order:
            return

        visit = None
        if order.visit_id:
            visit = self.db.query(Visit).filter(Visit.id == order.visit_id).first()
        if not visit or not visit.doctor_id:
            return

        doctor = self.db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
        if not doctor or not doctor.user_id:
            return

        # Отправляем врачу в защищённый inbox.
        doctor_user = self.db.query(User).filter(User.id == doctor.user_id).first()
        if not doctor_user:
            logger.warning(
                "Critical value alert skipped: doctor account missing for result %s",
                result.id,
            )
            return

        metadata = {
            "result_id": result.id,
            "order_id": result.order_id,
            "patient_id": order.patient_id,
            "test_name": result.test_name,
            "value": value,
            "unit": thresholds.get("unit", ""),
            "critical_low": thresholds["low"],
            "critical_high": thresholds["high"],
            "is_critical": True,
        }
        canonical_recorded = self._lab_inbox_delivery_exists(
            event_type="lab_critical_result",
            recipient_id=doctor_user.id,
            entity_id=result.id,
            expected_value=value,
        )
        newly_recorded = False
        if canonical_recorded:
            logger.debug(
                "Critical result inbox delivery already exists for result %s",
                result.id,
            )
        else:
            canonical_recorded = await notification_sender_service.send_lab_event_notification(
                db=self.db,
                recipient=doctor_user,
                event_type="lab_critical_result",
                title="Критический результат анализа",
                message=f"{result.test_name}: {value} {thresholds.get('unit', '')} у пациента #{order.patient_id}.",
                metadata=metadata,
            )
            newly_recorded = canonical_recorded
        if not canonical_recorded:
            logger.error(
                "[FIX:NOTIFICATIONS] lab_critical_result canonical delivery failed",
                extra={
                    "result_id": result.id,
                    "doctor_user_id": doctor_user.id,
                    "order_id": result.order_id,
                },
            )
            return

        finding_recorded = self._lab_inbox_delivery_exists(
            event_type="lab_critical_finding",
            recipient_id=doctor_user.id,
            entity_id=result.id,
            expected_value=value,
        )
        if not finding_recorded:
            finding_recorded = await notification_sender_service.send_lab_event_notification(
                db=self.db,
                recipient=doctor_user,
                event_type="lab_critical_finding",
                title="Критическая находка в исследовании",
                message=f"В анализе {result.test_name} у пациента #{order.patient_id} обнаружена критическая находка.",
                metadata=metadata,
            )
            newly_recorded = newly_recorded or finding_recorded
        if not finding_recorded:
            logger.warning(
                "[FIX:NOTIFICATIONS] lab_critical_finding canonical delivery failed",
                extra={
                    "result_id": result.id,
                    "doctor_user_id": doctor_user.id,
                    "order_id": result.order_id,
                },
            )

        if newly_recorded:
            logger.info(
                "Critical value alert recorded in doctor inbox for result %s",
                result.id,
            )

    async def send_follow_up_reminders(self, days_before: int = 3) -> dict[str, Any]:
        """
        Отправляет напоминания о повторных анализах

        Args:
            days_before: За сколько дней до даты напоминать

        Returns:
            Статистика отправленных напоминаний
        """
        # FEATURE WITHOUT DATA LAYER: LabOrder.follow_up_date /
        # follow_up_reminded никогда не существовали — ни в модели, ни в
        # одной миграции. Пока планировщик падал до запуска (ghost-метод,
        # #2849), баг был латентным; рабочий тик стал ловить AttributeError
        # на каждом прогоне (Sentry). Повторные напоминания требуют сначала
        # продуктового решения и колонки/миграции — учёт в #2775.
        logger.info(
            "Follow-up reminders skipped: no data layer "
            "(LabOrder.follow_up_date does not exist)"
        )
        return {"skipped": "LabOrder.follow_up_date column does not exist"}


async def run_lab_notifications(db: Session) -> dict[str, Any]:
    """
    Запускает все проверки уведомлений по анализам
    Может использоваться в cron job или scheduled task
    """
    service = LabNotificationService(db)

    results = {
        "ready_results": await service.check_and_notify_ready_results(),
        "critical_values": await service.check_critical_values(),
        "follow_up_reminders": await service.send_follow_up_reminders(),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    logger.info(f"Lab notifications run completed: {results}")
    return results
