"""
Lab Results Auto-Notification Service
Сервис автоматических уведомлений о готовности анализов
"""
import logging
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.roles import DOCTOR_FAMILY_GATE_ROLES
from app.models.clinic import Doctor
from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabOrder,
    LabReportInstance,
    LabReportValue,
    LabResult,
)
from app.models.lab_critical_communication import LabCriticalCommunication
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
        expected: dict[str, Any] | None = None,
        source: LabReportInstance | None = None,
    ) -> bool:
        snapshots = (
            self.db.query(NotificationEvent.payload_snapshot, NotificationEvent.created_at)
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
        if expected is None:
            return bool(snapshots)
        for snapshot, event_at in snapshots:
            metadata = (snapshot or {}).get("metadata") or {}
            if source is None:
                if metadata.get("value") == expected["value"]:
                    return True
                continue
            if metadata.get("report_instance_id") == source.id:
                return True
            if (
                "report_instance_id" not in metadata
                and expected["value"] is not None
                and metadata.get("value") == expected["value"]
                and metadata.get("patient_id") == source.patient_id
                and metadata.get("unit") == expected["unit"]
                and _as_aware_utc(event_at) >= _as_aware_utc(source.finalized_at)
            ):
                # Adopt an existing delivery for this release during rollout.
                return True
        return False

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

            recent_results = (
                self.db.query(LabResult, LabReportInstance, LabReportValue)
                .outerjoin(
                    LabReportInstance, LabReportInstance.id == LabResult.source_instance_id,
                )
                .outerjoin(
                    LabReportValue,
                    and_(
                        LabReportValue.instance_id == LabReportInstance.id,
                        LabReportValue.field_key == LabResult.test_code,
                    ),
                )
                .filter(
                    LabResult.value.is_not(None),
                    or_(
                        and_(
                            LabResult.source_instance_id.is_(None),
                            LabResult.source_root_instance_id.is_(None),
                            LabResult.created_at >= yesterday,
                        ),
                        and_(
                            LabReportInstance.managed_release.is_(False),
                            LabReportInstance.status.in_(FINAL_INSTANCE_STATUSES),
                            LabReportInstance.finalized_at >= yesterday,
                            # A released report with a durable communication
                            # is delivered by that task, not this legacy scan.
                            ~select(LabCriticalCommunication.id).where(
                                LabCriticalCommunication.report_instance_id == LabReportInstance.id,
                            ).exists(),
                        ),
                    ),
                )
                .all()
            )

            critical_found = []

            for result, source, report_value in recent_results:
                measurements = self._critical_measurements(result, source, report_value)
                if not measurements:
                    continue
                order = self.db.get(LabOrder, result.order_id)
                if source is not None and not self._source_context_matches(result, source, order):
                    continue
                for value, thresholds, direction in measurements:
                    critical_found.append({
                        "result_id": result.id,
                        "patient_id": source.patient_id if source else (order.patient_id if order else None),
                        "test_name": result.test_name,
                        "value": value,
                        "unit": thresholds["unit"],
                        "is_low": direction == "low",
                        "is_high": direction == "high",
                    })
                    await self._notify_doctor_critical_value(
                        result, value, thresholds, source=source,
                    )

            self.db.commit()

            return {
                "checked": len(recent_results),
                "critical_found": len(critical_found),
                "critical_results": critical_found,
            }

        except Exception as exc:
            self.db.rollback()
            logger.error("Error checking critical values: %s", type(exc).__name__)
            return {"error": "Critical value check failed"}

    def _critical_measurements(
        self,
        result: LabResult,
        source: LabReportInstance | None,
        report_value: LabReportValue | None,
    ) -> list[tuple[float | str | None, dict[str, Any], str | None]]:
        if source is None:
            if result.source_instance_id is not None or result.source_root_instance_id is not None:
                return []
            return self._historical_measurements(result)
        if (
            source.id != result.source_instance_id
            or source.order_id != result.order_id
            or result.source_root_instance_id is None
            or report_value is None
        ):
            return []

        snapshot = report_value.evaluation_snapshot
        payload = report_value.result_payload
        if snapshot is None and payload is None:
            # Published before typed snapshots existed. Match the exact source
            # value before reusing the historical scanner.
            if self._matches_source_value(result, report_value):
                return self._historical_measurements(result)
            return []
        if not isinstance(snapshot, dict) or not isinstance(payload, dict):
            return []
        unit = snapshot.get("unit") or ""
        if (
            snapshot.get("template_version_id") != source.template_version_id
            or snapshot.get("visible") is not True
            or snapshot.get("status") != "evaluated"
            or snapshot.get("interpretation") != "critical"
            or not isinstance(unit, str)
            or (unit[:32] or None) != result.unit
            or (snapshot.get("unit_code") and not unit)
            or payload.get("comparator") is not None
        ):
            return []

        kind = payload.get("kind")
        if (
            kind == "numeric"
            and report_value.value_numeric is not None
            and report_value.value_numeric.is_finite()
        ):
            value = float(report_value.value_numeric)
        elif kind == "coded_qualitative" and payload.get("qualitative_code") in (
            "positive", "negative", "indeterminate",
        ):
            value = payload["qualitative_code"]
        elif kind == "text" and report_value.value_numeric is None and report_value.value_text:
            # Route the doctor to the report without copying free text to the inbox.
            value = None
        else:
            return []

        from app.services.lab_reporting import LabReportingService

        # The legacy projection narrows both value and unit. Use the same
        # display formatter and widths when checking its link to the release.
        display = LabReportingService(self.db)._format_result_display(report_value)
        if not display or display[:128] != result.value:
            return []
        applied_thresholds = snapshot.get("thresholds") or {}
        if not isinstance(applied_thresholds, dict):
            return []
        flag_meta = report_value.resolved_flag_meta
        direction = flag_meta.get("direction") if isinstance(flag_meta, dict) else None
        thresholds = {
            "unit": unit,
            "low": applied_thresholds.get("critical_low"),
            "high": applied_thresholds.get("critical_high"),
            "analyte_code": snapshot.get("analyte_code"),
            "unit_code": snapshot.get("unit_code"),
        }
        return [(value, thresholds, direction)]

    @staticmethod
    def _matches_source_value(result: LabResult, report_value: LabReportValue) -> bool:
        if report_value.value_numeric is None:
            return bool(result.value and result.value == report_value.value_text)
        try:
            projected = Decimal(result.value)
        except (InvalidOperation, TypeError):
            return False
        return (
            projected.is_finite()
            and report_value.value_numeric.is_finite()
            and projected == report_value.value_numeric
        )

    def _historical_measurements(
        self, result: LabResult,
    ) -> list[tuple[float, dict[str, Any], str]]:
        if result.unit is None:
            return []
        try:
            value = float(result.value)
        except (ValueError, TypeError):
            return []
        if not math.isfinite(value):
            return []
        test_name = (result.test_name or "").lower()
        unit = (result.unit or "").strip()
        measurements = []
        for marker, thresholds in self.CRITICAL_VALUES.items():
            if marker not in test_name or unit != thresholds["unit"]:
                continue
            if value < thresholds["low"]:
                measurements.append((value, thresholds, "low"))
            elif value > thresholds["high"]:
                measurements.append((value, thresholds, "high"))
        return measurements

    def _source_context_matches(
        self, result: LabResult, source: LabReportInstance, order: LabOrder | None,
    ) -> bool:
        if order is None or (
            order.patient_id is not None and order.patient_id != source.patient_id
        ):
            return False
        if order.visit_id and source.visit_id and order.visit_id != source.visit_id:
            return False
        visit_id = order.visit_id or source.visit_id
        if visit_id is not None:
            visit = self.db.get(Visit, visit_id)
            if visit is None or visit.patient_id != source.patient_id:
                return False

        from app.services.lab_reporting import (
            LabReportingDomainError,
            LabReportingService,
        )

        try:
            root_id, _ = LabReportingService(self.db)._resolve_chain_root(source)
        except LabReportingDomainError:
            return False
        return root_id == result.source_root_instance_id

    def _lock_projected_release(self, result: LabResult, source: LabReportInstance) -> bool:
        # A correction can replace the projection after the scan. Serialize
        # delivery with its projection update and reject a stale scan.
        return self.db.query(LabResult.id).filter(
            LabResult.id == result.id,
            LabResult.source_instance_id == source.id,
            LabResult.value == result.value,
            LabResult.unit == result.unit,
        ).with_for_update(of=LabResult).first() is not None

    def _lock_linked_recipient_id(
        self, result: LabResult, source: LabReportInstance, visit_id: int,
    ) -> int | None:
        from app.services.lab_critical_communication import _active_visit_doctor_query

        # Take the projection lock before the same ownership locks used by
        # managed critical communication (Visit, Doctor, User).
        if not self._lock_projected_release(result, source):
            return None
        query = _active_visit_doctor_query(
            visit_id, source.patient_id, eligible_roles=DOCTOR_FAMILY_GATE_ROLES,
        )
        return self.db.scalar(query.with_for_update(read=True, of=(Visit, Doctor, User)))

    async def _notify_doctor_critical_value(
        self,
        result: LabResult,
        value: float | str | None,
        thresholds: dict,
        *,
        source: LabReportInstance | None = None,
    ):
        """Уведомляет врача о критическом значении"""
        order = self.db.query(LabOrder).filter(LabOrder.id == result.order_id).first()
        if not order:
            return
        visit_id = order.visit_id or (source.visit_id if source else None)
        if visit_id is None:
            return
        if source is not None:
            recipient_id = self._lock_linked_recipient_id(result, source, visit_id)
            if recipient_id is None:
                return
        else:
            visit = self.db.get(Visit, visit_id)
            if not visit or not visit.doctor_id:
                return
            doctor = self.db.get(Doctor, visit.doctor_id)
            if not doctor or not doctor.user_id:
                return
            recipient_id = doctor.user_id
        doctor_user = self.db.get(User, recipient_id, populate_existing=source is not None)
        if not doctor_user:
            logger.warning(
                "Critical value alert skipped: doctor account missing for result %s",
                result.id,
            )
            return

        patient_id = source.patient_id if source else order.patient_id
        metadata = {
            "result_id": result.id,
            "order_id": result.order_id,
            "patient_id": patient_id,
            "test_name": result.test_name,
            "value": value,
            "unit": thresholds.get("unit", ""),
            "critical_low": thresholds["low"],
            "critical_high": thresholds["high"],
            "is_critical": True,
        }
        if source is not None:
            metadata.update({
                "report_instance_id": source.id,
                "analyte_code": thresholds.get("analyte_code"),
                "unit_code": thresholds.get("unit_code"),
            })
            if value is not None:
                metadata["value_display"] = result.value
        if value is None:
            result_message = f"В анализе {result.test_name} у пациента #{patient_id} обнаружена критическая находка."
        else:
            display_value = metadata.get("value_display", value)
            result_message = f"{result.test_name}: {display_value} {metadata['unit']} у пациента #{patient_id}."
        canonical_recorded = self._lab_inbox_delivery_exists(
            event_type="lab_critical_result",
            recipient_id=recipient_id,
            entity_id=result.id,
            expected=metadata,
            source=source,
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
                message=result_message,
                metadata=metadata,
            )
            newly_recorded = canonical_recorded
        if not canonical_recorded:
            logger.error(
                "[FIX:NOTIFICATIONS] lab_critical_result canonical delivery failed",
                extra={
                    "result_id": result.id,
                    "doctor_user_id": recipient_id,
                    "order_id": result.order_id,
                },
            )
            return

        # The inbox sender commits. The companion event needs fresh release
        # and ownership locks, and the exact same recipient account.
        if source is not None and self._lock_linked_recipient_id(result, source, visit_id) != recipient_id:
            return
        finding_recorded = self._lab_inbox_delivery_exists(
            event_type="lab_critical_finding",
            recipient_id=recipient_id,
            entity_id=result.id,
            expected=metadata,
            source=source,
        )
        if not finding_recorded:
            finding_recorded = await notification_sender_service.send_lab_event_notification(
                db=self.db,
                recipient=doctor_user,
                event_type="lab_critical_finding",
                title="Критическая находка в исследовании",
                message=f"В анализе {result.test_name} у пациента #{patient_id} обнаружена критическая находка.",
                metadata=metadata,
            )
            newly_recorded = newly_recorded or finding_recorded
        if not finding_recorded:
            logger.warning(
                "[FIX:NOTIFICATIONS] lab_critical_finding canonical delivery failed",
                extra={
                    "result_id": result.id,
                    "doctor_user_id": recipient_id,
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

    logger.info(
        "Lab notifications run completed: %s ready, %s critical found",
        results["ready_results"].get("notifications_sent", 0),
        results["critical_values"].get("critical_found", 0),
    )
    return results
