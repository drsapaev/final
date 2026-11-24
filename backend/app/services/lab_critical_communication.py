"""Transactional critical task creation and retryable inbox recording."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.clinic import Doctor
from app.models.lab import LabReportInstance
from app.models.lab_critical_communication import (
    LabCriticalCommunication,
    LabCriticalCommunicationEvent,
)
from app.models.user import User
from app.models.visit import Visit
from app.services.lab_reporting import LabReportingDomainError


def _active_visit_doctor_query(
    visit_id, patient_id, *, eligible_roles: tuple[str, ...] = ("doctor",),
):
    return (
        select(User.id)
        .join(Doctor, Doctor.user_id == User.id)
        .join(Visit, Visit.doctor_id == Doctor.id)
        .where(
            Visit.id == visit_id,
            Visit.patient_id == patient_id,
            User.is_active.is_(True),
            func.lower(func.trim(User.role)).in_(eligible_roles),
            Doctor.active.is_(True),
        )
    )


def _responsible_user_id(
    db: Session,
    instance: LabReportInstance,
    *,
    lock_ownership: bool = False,
) -> int | None:
    query = _active_visit_doctor_query(instance.visit_id, instance.patient_id)
    if lock_ownership:
        query = query.with_for_update(read=True, of=(Visit, Doctor, User))
    return db.scalar(query)


def _first_attempt_at(doctor_id: int | None = None) -> datetime | None:
    if doctor_id is not None or settings.LAB_CRITICAL_ESCALATION_ADMIN_ID is not None:
        return datetime.now(UTC)
    return None


def _current_delivery_recipient(
    db: Session, task: LabCriticalCommunication,
) -> tuple[int | None, int | None]:
    """Resolve the clinical owner and the inbox target under the delivery lock."""
    if task.state == "escalated":
        doctor_id = task.recipient_user_id
    else:
        instance = db.get(LabReportInstance, task.report_instance_id)
        doctor_id = _responsible_user_id(db, instance, lock_ownership=True)
        if doctor_id is not None:
            return doctor_id, doctor_id
    admin_id = settings.LAB_CRITICAL_ESCALATION_ADMIN_ID
    if admin_id is None:
        return doctor_id, None
    return doctor_id, db.scalar(
        select(User.id).where(
            User.id == admin_id,
            User.is_active.is_(True),
            func.lower(func.trim(User.role)) == "admin",
        ).with_for_update(read=True)
    )


def _event(
    db: Session,
    task_id: int,
    event_type: str,
    *,
    actor_user_id: int | None = None,
    channel: str | None = None,
) -> None:
    db.add(
        LabCriticalCommunicationEvent(
            communication_id=task_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            channel=channel,
        )
    )


def record_released_report(
    db: Session,
    instance: LabReportInstance,
    *,
    actor_user_id: int | None = None,
) -> LabCriticalCommunication | None:
    """Called once under the canonical report lock, before release commits."""
    critical_keys = sorted(
        value.field_key
        for value in instance.values
        if (value.evaluation_snapshot or {}).get("interpretation") == "critical"
    )
    previous = (
        db.scalar(
            select(LabCriticalCommunication).where(
                LabCriticalCommunication.report_instance_id
                == instance.supersedes_instance_id,
            )
        )
        if instance.supersedes_instance_id
        else None
    )
    if not critical_keys and previous is None:
        return None

    existing = db.scalar(
        select(LabCriticalCommunication).where(
            LabCriticalCommunication.report_instance_id == instance.id,
        )
    )
    if existing is not None:
        return existing
    recipient_id = _responsible_user_id(db, instance)
    task = LabCriticalCommunication(
        report_instance_id=instance.id,
        supersedes_communication_id=previous.id if previous else None,
        field_keys=critical_keys,
        released_by_id=actor_user_id,
        recipient_user_id=recipient_id,
        state="pending" if recipient_id is not None else "needs_assignment",
        next_attempt_at=_first_attempt_at(recipient_id),
    )
    db.add(task)
    db.flush()
    _event(db, task.id, "created", actor_user_id=actor_user_id)
    if previous is not None and previous.acknowledged_at is None:
        previous = _locked_task(db, previous.id)
        if previous.acknowledged_at is None:
            previous.state = "superseded"
            previous.next_attempt_at = None
            _event(db, previous.id, "superseded", actor_user_id=actor_user_id)
    return task


def _locked_task(db: Session, task_id: int) -> LabCriticalCommunication:
    task = db.scalar(
        select(LabCriticalCommunication)
        .where(
            LabCriticalCommunication.id == task_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if task is None:
        raise LabReportingDomainError(404, "Critical communication not found")
    return task


def _set_task_recipient(
    db: Session,
    task: LabCriticalCommunication,
    recipient_id: int | None,
    *,
    actor_user_id: int | None = None,
) -> None:
    task.recipient_user_id = recipient_id
    task.inbox_recorded_at = None
    task.state = "pending" if recipient_id is not None else "needs_assignment"
    task.next_attempt_at = _first_attempt_at(recipient_id)
    _event(
        db,
        task.id,
        "assigned" if recipient_id is not None else "needs_assignment",
        actor_user_id=actor_user_id,
    )


def assign_responsible_doctor(
    db: Session,
    task_id: int,
    *,
    actor_user_id: int,
) -> LabCriticalCommunication:
    task = _locked_task(db, task_id)
    if task.state in {"acknowledged", "superseded"}:
        raise LabReportingDomainError(409, "Communication is closed")
    instance = db.get(LabReportInstance, task.report_instance_id)
    recipient_id = _responsible_user_id(db, instance, lock_ownership=True)
    if recipient_id is None:
        raise LabReportingDomainError(
            409, "No eligible doctor is assigned to this visit"
        )
    if task.recipient_user_id == recipient_id and task.state in {
        "pending",
        "inbox_recorded",
    }:
        return task
    _set_task_recipient(db, task, recipient_id, actor_user_id=actor_user_id)
    db.commit()
    return task


def escalate(
    db: Session,
    task_id: int,
    *,
    actor_user_id: int,
) -> LabCriticalCommunication:
    task = _locked_task(db, task_id)
    if task.state in {"acknowledged", "superseded"}:
        raise LabReportingDomainError(409, "Communication is closed")
    if task.state == "escalated":
        return task
    task.state = "escalated"
    task.escalated_at = datetime.now(UTC)
    task.next_attempt_at = _first_attempt_at()
    _event(db, task.id, "escalated", actor_user_id=actor_user_id)
    db.commit()
    return task


def acknowledge(
    db: Session,
    task_id: int,
    *,
    actor_user_id: int,
) -> LabCriticalCommunication:
    task = _locked_task(db, task_id)
    instance = db.get(LabReportInstance, task.report_instance_id)
    if (
        task.recipient_user_id != actor_user_id
        or _responsible_user_id(db, instance, lock_ownership=True) != actor_user_id
    ):
        raise LabReportingDomainError(404, "Critical communication not found")
    if task.state == "superseded":
        raise LabReportingDomainError(409, "Communication has been superseded")
    if task.acknowledged_at is not None:
        return task
    task.acknowledged_at = datetime.now(UTC)
    task.acknowledged_by_id = actor_user_id
    task.state = "acknowledged"
    task.next_attempt_at = None
    _event(db, task.id, "acknowledged", actor_user_id=actor_user_id)
    db.commit()
    return task


def _reconcile_doctor_assignments(db: Session, *, limit: int) -> None:
    # Recheck the exact visit after a missing or changed doctor assignment.
    # Operational inbox delivery never substitutes for clinical acknowledgment.
    current_owner = (
        _active_visit_doctor_query(
            LabReportInstance.visit_id, LabReportInstance.patient_id
        )
        .correlate(LabReportInstance)
        .scalar_subquery()
    )
    candidates = (
        select(LabCriticalCommunication)
        .join(
            LabReportInstance,
            LabReportInstance.id == LabCriticalCommunication.report_instance_id,
        )
        .where(
            LabCriticalCommunication.state.in_(("needs_assignment", "inbox_recorded")),
            LabCriticalCommunication.recipient_user_id.is_distinct_from(current_owner),
        )
        .order_by(LabCriticalCommunication.id)
        .limit(1)
        .with_for_update(of=LabCriticalCommunication, skip_locked=True)
        .execution_options(populate_existing=True)
    )
    for _ in range(limit):
        task = db.scalar(candidates)
        if task is None:
            db.rollback()
            break
        instance = db.get(LabReportInstance, task.report_instance_id)
        recipient_id = _responsible_user_id(db, instance, lock_ownership=True)
        if recipient_id != task.recipient_user_id:
            _set_task_recipient(db, task, recipient_id)
        db.commit()


async def dispatch_pending(db: Session, *, limit: int = 25) -> int:
    """Deliver due tasks to inbox via the canonical producer.

    Each task is leased under a row lock. The canonical event uses a stable
    entity key so retry after a crash reuses the same delivery.
    """
    from app.services.notifications import notification_sender_service

    _reconcile_doctor_assignments(db, limit=limit)
    recorded = 0
    for _ in range(limit):
        now = datetime.now(UTC)
        task = db.scalar(
            select(LabCriticalCommunication)
            .where(
                LabCriticalCommunication.state.in_(("pending", "needs_assignment", "escalated")),
                LabCriticalCommunication.next_attempt_at <= now,
            )
            .order_by(
                LabCriticalCommunication.next_attempt_at, LabCriticalCommunication.id
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if task is None:
            db.rollback()
            break
        delivery_state = task.state
        doctor_id, recipient_id = _current_delivery_recipient(db, task)
        if doctor_id != task.recipient_user_id or (
            delivery_state == "pending" and doctor_id is None
        ):
            _set_task_recipient(db, task, doctor_id)
            db.commit()
            continue
        if recipient_id is None:
            # Misconfigured or inactive operational account. Keep the task
            # visible and recheck later without counting a delivery attempt.
            task.next_attempt_at = (
                now + timedelta(minutes=30)
                if settings.LAB_CRITICAL_ESCALATION_ADMIN_ID is not None else None
            )
            db.commit()
            continue

        task_id = task.id
        actor_id = task.released_by_id
        is_correction = task.supersedes_communication_id is not None
        task.attempts += 1
        attempt_number = task.attempts
        task.next_attempt_at = now + timedelta(
            seconds=min(60 * 2 ** min(attempt_number - 1, 5), 1800)
        )
        _event(db, task.id, "attempted", channel="in_app_inbox")
        db.commit()

        task = _locked_task(db, task_id)
        if (
            task.state != delivery_state
            or task.attempts != attempt_number
            or task.recipient_user_id != doctor_id
        ):
            db.rollback()
            continue
        current_doctor_id, current_recipient_id = _current_delivery_recipient(db, task)
        if current_doctor_id != doctor_id:
            _set_task_recipient(db, task, current_doctor_id)
            db.commit()
            continue
        if current_recipient_id != recipient_id:
            db.rollback()
            continue

        recipient = db.get(User, recipient_id, populate_existing=True)
        if delivery_state == "pending":
            title = (
                "Исправлен критический лабораторный результат"
                if is_correction else "Критический результат анализа"
            )
            message = "Откройте выпущенный отчёт и подтвердите получение."
            entity_type = "lab_critical_communication"
            deep_link = "/doctor"
            receipt_event = "inbox_recorded"
        else:
            escalated = delivery_state == "escalated"
            title = (
                "Эскалация критического сообщения"
                if escalated else "Требуется назначить ответственного врача"
            )
            message = "Откройте рабочий список критических сообщений."
            entity_type = "lab_critical_escalation" if escalated else "lab_critical_assignment"
            deep_link = f"/lab?tab=operations&communication_id={task_id}"
            receipt_event = "escalation_notified" if escalated else "assignment_notified"
        delivered = (
            await notification_sender_service.send_canonical_notification_to_user(
                db=db,
                recipient=recipient,
                event_type="lab_critical_result",
                title=title,
                message=message,
                source_module="lab",
                severity="critical",
                priority="urgent",
                actor_id=actor_id,
                entity_type=entity_type,
                entity_id=task_id,
                deep_link=deep_link,
                metadata={"communication_id": task_id},
            )
        )
        db.rollback()
        task = _locked_task(db, task_id)
        if task.attempts != attempt_number or task.recipient_user_id != doctor_id:
            db.rollback()
            continue
        if delivered:
            if delivery_state == "pending":
                task.inbox_recorded_at = datetime.now(UTC)
            if task.state == delivery_state:
                if delivery_state == "pending":
                    task.state = "inbox_recorded"
                task.next_attempt_at = None
            _event(db, task.id, receipt_event, channel="in_app_inbox")
            recorded += 1
        else:
            _event(db, task.id, "delivery_failed", channel="in_app_inbox")
        db.commit()
    return recorded
