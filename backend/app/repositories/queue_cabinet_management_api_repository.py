"""Repository helpers for queue cabinet management endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service_execution import STATUS_IN_PROGRESS, ServiceExecution


class QueueCabinetManagementApiRepository:
    """Encapsulates ORM operations for queue cabinet management API."""

    def __init__(self, db: Session):
        self.db = db

    def list_daily_queues(
        self,
        *,
        day_obj: date | None = None,
        specialist_id: int | None = None,
        cabinet_number: str | None = None,
    ) -> list[DailyQueue]:
        query = self.db.query(DailyQueue)
        if day_obj:
            query = query.filter(DailyQueue.day == day_obj)
        if specialist_id:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        if cabinet_number:
            query = query.filter(DailyQueue.cabinet_number == cabinet_number)
        return query.order_by(DailyQueue.day.desc(), DailyQueue.specialist_id).all()

    def get_daily_queue(self, queue_id: int) -> DailyQueue | None:
        return self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

    def list_daily_queues_by_ids(self, *, queue_ids: list[int]) -> list[DailyQueue]:
        """Load explicit queue targets and their typed owners in one query."""
        if not queue_ids:
            return []
        return (
            self.db.query(DailyQueue)
            .options(
                joinedload(DailyQueue.specialist).joinedload(Doctor.user),
                joinedload(DailyQueue.queue_resource),
            )
            .filter(DailyQueue.id.in_(queue_ids))
            .all()
        )

    def count_waiting_entries_by_queue_ids(
        self, *, queue_ids: list[int]
    ) -> dict[int, int]:
        if not queue_ids:
            return {}
        rows = (
            self.db.query(OnlineQueueEntry.queue_id, func.count(OnlineQueueEntry.id))
            .filter(
                OnlineQueueEntry.queue_id.in_(queue_ids),
                OnlineQueueEntry.status == "waiting",
            )
            .group_by(OnlineQueueEntry.queue_id)
            .all()
        )
        return dict(rows)

    def list_entry_statuses_by_queue_ids(
        self, *, queue_ids: list[int], statuses: tuple[str, ...]
    ) -> dict[int, set[str]]:
        if not queue_ids or not statuses:
            return {}
        rows = (
            self.db.query(OnlineQueueEntry.queue_id, OnlineQueueEntry.status)
            .filter(
                OnlineQueueEntry.queue_id.in_(queue_ids),
                OnlineQueueEntry.status.in_(statuses),
            )
            .distinct()
            .all()
        )
        result: dict[int, set[str]] = {}
        for queue_id, entry_status in rows:
            result.setdefault(queue_id, set()).add(entry_status)
        return result

    def list_queue_ids_with_active_service_execution(
        self, *, queue_ids: list[int]
    ) -> set[int]:
        if not queue_ids:
            return set()
        rows = (
            self.db.query(OnlineQueueEntry.queue_id)
            .join(
                ServiceExecution,
                ServiceExecution.queue_entry_id == OnlineQueueEntry.id,
            )
            .filter(
                OnlineQueueEntry.queue_id.in_(queue_ids),
                ServiceExecution.status == STATUS_IN_PROGRESS,
            )
            .distinct()
            .all()
        )
        return {queue_id for (queue_id,) in rows}

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def count_entries(self, *, queue_id: int) -> int:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
        )

    def list_queues_for_day(
        self,
        *,
        day_obj: date,
        specialist_id: int | None = None,
    ) -> list[DailyQueue]:
        query = self.db.query(DailyQueue).filter(DailyQueue.day == day_obj)
        if specialist_id:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        return query.all()

    def list_queues_for_period(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> list[DailyQueue]:
        query = self.db.query(DailyQueue)
        if date_from:
            query = query.filter(DailyQueue.day >= date_from)
        if date_to:
            query = query.filter(DailyQueue.day <= date_to)
        return query.all()

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()
