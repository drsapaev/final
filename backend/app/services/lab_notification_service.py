"""
Lab Results Auto-Notification Service
Сервис автоматических уведомлений о готовности анализов
"""
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.lab import LabOrder, LabResult
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

    async def check_and_notify_ready_results(self) -> dict[str, Any]:
        """
        Проверяет готовые результаты и отправляет уведомления пациентам

        Returns:
            Статистика отправленных уведомлений
        """
        try:
            # Находим готовые результаты. Дедупликация здесь не хранится в модели,
            # поэтому этот сервис отвечает только за canonical delivery.
            ready_orders = self.db.query(LabOrder).filter(LabOrder.status == "completed").all()

            notifications_sent = 0
            errors = []

            for order in ready_orders:
                try:
                    await self._notify_patient_results_ready(order)
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

    async def _notify_patient_results_ready(self, order: LabOrder):
        """Отправляет уведомление пациенту о готовности результатов"""
        patient = self.db.query(Patient).filter(Patient.id == order.patient_id).first()

        if not patient:
            return

        # Получаем пользователя пациента
        user = None
        if patient.user_id:
            user = self.db.query(User).filter(User.id == patient.user_id).first()

        message = f"""
✅ Результаты анализов готовы!

Уважаемый(ая) {patient.short_name()},

Ваши результаты лабораторных исследований готовы.
Номер заказа: {order.id}
Дата забора: {order.created_at.strftime('%d.%m.%Y')}

Вы можете просмотреть результаты в личном кабинете или получить их в регистратуре клиники.

С уважением,
Ваша клиника
        """.strip()

        # Отправляем через доступные каналы
        if user:
            canonical_created = await notification_sender_service.send_lab_event_notification(
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
            if not canonical_created:
                logger.warning(
                    "[FIX:NOTIFICATIONS] lab_results canonical delivery failed",
                    extra={"order_id": order.id, "patient_user_id": user.id},
                )
            else:
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
                if not confirmation_created:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] lab_result_sent_confirmation canonical delivery failed",
                        extra={"order_id": order.id, "patient_user_id": user.id},
                    )

            if hasattr(user, 'telegram_id') and user.telegram_id:
                await notification_sender_service.send_telegram_message(
                    user_id=user.telegram_id,
                    message=message,
                )

        # SMS если есть телефон
        if patient.phone:
            _short_message = f"Ваши анализы готовы! Заказ #{order.id}. Просмотр в личном кабинете."
            # NOTIF-REAUDIT-28 P1-5: uncommented — patients without app/Telegram
            # must receive lab result alerts via SMS. PR #1932 left this commented out.
            try:
                await notification_sender_service.send_sms(patient.phone, _short_message)
            except Exception as sms_err:
                logger.warning('Lab result SMS send failed for patient %s: %s', patient.id, sms_err)

        logger.info(f"Notification sent for order {order.id} to patient {patient.id}")

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

        patient = self.db.query(Patient).filter(Patient.id == order.patient_id).first()

        alert_type = "⬇️ КРИТИЧЕСКИ НИЗКОЕ" if value < thresholds["low"] else "⬆️ КРИТИЧЕСКИ ВЫСОКОЕ"

        message = f"""
🚨 КРИТИЧЕСКОЕ ЗНАЧЕНИЕ!

{alert_type} значение:

📊 Показатель: {result.test_name}
📈 Значение: {value} {thresholds.get('unit', '')}
📉 Норма: {thresholds['low']} - {thresholds['high']}

👤 Пациент: {patient.short_name() if patient else f'ID {order.patient_id}'}

Требуется срочное внимание!
        """.strip()

        # Отправляем врачу
        doctor_user = self.db.query(User).filter(User.id == doctor.user_id).first()
        if doctor_user:
            canonical_created = await notification_sender_service.send_lab_event_notification(
                db=self.db,
                recipient=doctor_user,
                event_type="lab_critical_result",
                title="Критический результат анализа",
                message=f"{result.test_name}: {value} {thresholds.get('unit', '')} у пациента #{order.patient_id}.",
                metadata={
                    "result_id": result.id,
                    "order_id": result.order_id,
                    "patient_id": order.patient_id,
                    "test_name": result.test_name,
                    "value": value,
                    "unit": thresholds.get("unit", ""),
                    "critical_low": thresholds["low"],
                    "critical_high": thresholds["high"],
                    "is_critical": True,
                },
            )
            if not canonical_created:
                logger.error(
                    "[FIX:NOTIFICATIONS] lab_critical_result canonical delivery failed",
                    extra={
                        "result_id": result.id,
                        "doctor_user_id": doctor_user.id,
                    "order_id": result.order_id,
                },
            )
            else:
                finding_created = await notification_sender_service.send_lab_event_notification(
                    db=self.db,
                    recipient=doctor_user,
                    event_type="lab_critical_finding",
                    title="Критическая находка в исследовании",
                    message=f"В анализе {result.test_name} у пациента #{order.patient_id} обнаружена критическая находка.",
                    metadata={
                        "result_id": result.id,
                        "order_id": result.order_id,
                        "patient_id": order.patient_id,
                        "test_name": result.test_name,
                        "value": value,
                        "unit": thresholds.get("unit", ""),
                        "critical_low": thresholds["low"],
                        "critical_high": thresholds["high"],
                        "is_critical": True,
                    },
                )
                if not finding_created:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] lab_critical_finding canonical delivery failed",
                        extra={
                            "result_id": result.id,
                            "doctor_user_id": doctor_user.id,
                            "order_id": result.order_id,
                        },
                    )

            if hasattr(doctor_user, 'telegram_id') and doctor_user.telegram_id:
                await notification_sender_service.send_telegram_message(
                    user_id=doctor_user.telegram_id,
                    message=message,
                )

        logger.warning(f"Critical value alert sent for result {result.id}")

    async def send_follow_up_reminders(self, days_before: int = 3) -> dict[str, Any]:
        """
        Отправляет напоминания о повторных анализах

        Args:
            days_before: За сколько дней до даты напоминать

        Returns:
            Статистика отправленных напоминаний
        """
        try:
            target_date = datetime.now(UTC) + timedelta(days=days_before)

            # Находим заказы с датой повторного анализа
            upcoming_followups = (
                self.db.query(LabOrder)
                .filter(
                    LabOrder.follow_up_date.isnot(None),
                    LabOrder.follow_up_date >= datetime.now(UTC),
                    LabOrder.follow_up_date <= target_date,
                    or_(
                        LabOrder.follow_up_reminded == False,
                        LabOrder.follow_up_reminded.is_(None),
                    ),
                )
                .all()
            )

            reminders_sent = 0

            for order in upcoming_followups:
                patient = self.db.query(Patient).filter(Patient.id == order.patient_id).first()

                if patient:
                    days_until = (_as_aware_utc(order.follow_up_date) - datetime.now(UTC)).days

                    message = f"""
📅 Напоминание о повторном анализе

Уважаемый(ая) {patient.short_name()},

Напоминаем, что через {days_until} дней ({order.follow_up_date.strftime('%d.%m.%Y')}) вам необходимо сдать повторный анализ.

Пожалуйста, запишитесь на приём заранее.

С уважением,
Ваша клиника
                    """.strip()

                    # Отправляем напоминание
                    if patient.user_id:
                        user = self.db.query(User).filter(User.id == patient.user_id).first()
                        if user:
                            canonical_created = await notification_sender_service.send_queue_position_event_notification(
                                db=self.db,
                                recipient=user,
                                event_type="diagnostics_return_needed",
                                title="Напоминание о повторном анализе",
                                message=f"Через {days_until} дней запланирован повторный анализ.",
                                metadata={
                                    "order_id": order.id,
                                    "patient_id": order.patient_id,
                                    "follow_up_date": order.follow_up_date.isoformat(),
                                    "days_until": days_until,
                                },
                            )

                            telegram_sent = False
                            if hasattr(user, 'telegram_id') and user.telegram_id:
                                tg_response = await notification_sender_service.send_telegram_message(
                                    user_id=user.telegram_id,
                                    message=message,
                                )
                                telegram_sent = bool(tg_response.get("success"))

                            if canonical_created or telegram_sent:
                                reminders_sent += 1

                    order.follow_up_reminded = True
                    order.follow_up_reminded_at = datetime.now(UTC)

            self.db.commit()

            return {
                "upcoming_followups": len(upcoming_followups),
                "reminders_sent": reminders_sent,
            }

        except Exception as e:
            logger.error(f"Error sending follow-up reminders: {e}")
            return {"error": str(e)}


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
