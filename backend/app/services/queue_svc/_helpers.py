"""Helpers mixin for QueueBusinessService.

Split from queue_service.py.
"""
from __future__ import annotations

from app.services.queue_svc._base import *  # noqa: F401, F403
from app.services.queue_svc._base import QueueBusinessServiceMixinBase


class HelpersMixin(QueueBusinessServiceMixinBase):
    """Helpers methods."""

    def _staff_action_result(
        self,
        entry: OnlineQueueEntry,
        *,
        action: str,
        previous_status: str,
        original_queue_time: datetime | None,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "action": action,
            "entry_id": entry.id,
            "queue_id": entry.queue_id,
            "visit_id": entry.visit_id,
            "number": entry.number,
            "previous_status": previous_status,
            "status": entry.status,
            "queue_time": entry.queue_time,
            "queue_time_preserved": entry.queue_time == original_queue_time,
            "called_at": entry.called_at,
        }


    def staff_call_next_patient(
        self,
        db: Session,
        *,
        queue_id: int | None = None,
        specialist_id: int | None = None,
        queue_tag: str | None = None,
        target_date: date | None = None,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        target_day = target_date or date.today()
        query = (
            db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                DailyQueue.day == target_day,
                DailyQueue.active.is_(True),
                OnlineQueueEntry.status == "waiting",
            )
        )
        if queue_id is not None:
            query = query.filter(OnlineQueueEntry.queue_id == queue_id)
        if specialist_id is not None:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        if queue_tag:
            query = query.filter(DailyQueue.queue_tag == queue_tag)

        entry = (
            query.order_by(
                OnlineQueueEntry.priority.desc(),
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
            .first()
        )
        if not entry:
            raise QueueNotFoundError("No waiting queue entry found for staff call")

        original_queue_time = entry.queue_time
        previous_status = entry.status
        changed_at = self.get_local_timestamp(db)
        entry.status = "called"
        entry.called_at = changed_at
        entry.updated_at = changed_at
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_call_next_patient",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )


    def staff_skip_queue_entry(
        self,
        db: Session,
        *,
        entry_id: int,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        entry = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == entry_id)
            .first()
        )
        if not entry:
            raise QueueNotFoundError(f"Queue entry {entry_id} not found")
        if entry.status not in {"waiting", "called"}:
            raise QueueConflictError(
                f"Queue entry {entry_id} cannot be skipped from status {entry.status}"
            )

        original_queue_time = entry.queue_time
        previous_status = entry.status
        entry.status = "no_show"
        entry.updated_at = self.get_local_timestamp(db)
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_skip_queue_entry",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )


    def _staff_visit_queue_link_entry(
        self,
        db: Session,
        *,
        visit_id: int,
    ) -> OnlineQueueEntry:
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise QueueNotFoundError(f"Visit {visit_id} not found")
        if visit.patient_id is None:
            raise QueueConflictError(f"Visit {visit_id} has no patient owner")

        active_statuses = {"waiting", "called", "in_service", "diagnostics"}
        entries = (
            db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.visit_id == visit_id,
                OnlineQueueEntry.patient_id == visit.patient_id,
                OnlineQueueEntry.status.in_(active_statuses),
            )
            .order_by(
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
            .all()
        )
        if not entries:
            raise QueueNotFoundError(f"Active queue link for visit {visit_id} not found")
        if len(entries) > 1:
            raise QueueConflictError(
                f"Visit {visit_id} has multiple active queue links"
            )
        return entries[0]


    def staff_cancel_visit_queue_link(
        self,
        db: Session,
        *,
        visit_id: int,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        entry = self._staff_visit_queue_link_entry(db, visit_id=visit_id)
        original_queue_time = entry.queue_time
        previous_status = entry.status
        entry.status = "cancelled"
        entry.updated_at = self.get_local_timestamp(db)
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_cancel_visit_queue_link",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )


    def staff_move_visit_queue_link(
        self,
        db: Session,
        *,
        visit_id: int,
        actor_user_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        entry = self._staff_visit_queue_link_entry(db, visit_id=visit_id)
        original_queue_time = entry.queue_time
        previous_status = entry.status
        entry.status = "rescheduled"
        entry.updated_at = self.get_local_timestamp(db)
        if commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()

        return self._staff_action_result(
            entry,
            action="staff_move_visit_queue_link",
            previous_status=previous_status,
            original_queue_time=original_queue_time,
        )


    def update_queue_status(
        self,
        db: Session,
        *,
        entry_id: int,
        new_status: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("update_queue_status is pending implementation")


    def validate_status_transition(self, current_status: str, new_status: str) -> None:
        raise NotImplementedError(
            "validate_status_transition is pending implementation"
        )


    def close_queue_entry(
        self,
        db: Session,
        *,
        entry_id: int,
        result_status: str = "served",
        closed_by: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("close_queue_entry is pending implementation")


    def calculate_wait_time(self, entry: OnlineQueueEntry) -> dict[str, Any]:
        raise NotImplementedError("calculate_wait_time is pending implementation")


    def get_visit_history(
        self, db: Session, *, patient_id: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("get_visit_history is pending implementation")


    def reorder_queue(
        self, db: Session, *, queue_id: int, entry_orders: list[dict[str, int]]
    ) -> dict[str, Any]:
        raise NotImplementedError("reorder_queue is pending implementation")


    def resolve_conflicts(
        self, db: Session, *, queue_id: int, strategy: str = "compact"
    ) -> dict[str, Any]:
        raise NotImplementedError("resolve_conflicts is pending implementation")


# Глобальный экземпляр сервиса


def get_queue_service() -> QueueBusinessService:
    """Получить экземпляр сервиса очереди"""
    return queue_service


