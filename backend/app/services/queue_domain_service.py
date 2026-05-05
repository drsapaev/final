"""Queue domain boundary introduced in Wave 2C Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.repositories.queue_read_repository import QueueReadRepository
from app.services.queue_service import queue_service
from app.services.queue_status import REORDER_ACTIVE_RAW_STATUSES


@dataclass
class QueueDomainReadError(Exception):
    status_code: int
    detail: str


@dataclass(frozen=True)
class QueueSnapshot:
    queue: object
    entries: list[object]


class QueueDomainService:
    """Owns queue-domain boundaries without migrating mutations yet."""

    def __init__(
        self,
        db: Session,
        read_repository: QueueReadRepository | None = None,
    ):
        self.read_repository = read_repository or QueueReadRepository(db)

    def get_queue_snapshot(self, *, queue_id: int) -> QueueSnapshot:
        queue = self.read_repository.get_queue(queue_id)
        if not queue:
            raise QueueDomainReadError(404, "Очередь не найдена")

        entries = self.read_repository.list_snapshot_entries(
            queue_id=queue_id,
            statuses=REORDER_ACTIVE_RAW_STATUSES,
        )
        return QueueSnapshot(queue=queue, entries=entries)

    def get_queue_snapshot_by_specialist_day(
        self,
        *,
        specialist_id: int,
        day: date,
    ) -> QueueSnapshot:
        queue = self.read_repository.get_queue_by_specialist_day(
            specialist_id=specialist_id,
            day=day,
        )
        if not queue:
            raise QueueDomainReadError(404, "Очередь не найдена")

        entries = self.read_repository.list_snapshot_entries(
            queue_id=queue.id,
            statuses=REORDER_ACTIVE_RAW_STATUSES,
        )
        return QueueSnapshot(queue=queue, entries=entries)

    def _resolve_specialist_name(self, specialist_id: int) -> str:
        specialist = self.read_repository.get_doctor(specialist_id)
        if specialist and specialist.user:
            user = specialist.user
            return user.full_name or user.username or f"Специалист #{specialist_id}"
        return f"Специалист #{specialist_id}"

    def _build_cabinet_payload(self, queue: object) -> dict[str, Any]:
        doctor = self.read_repository.get_doctor(queue.specialist_id)
        doctor_cabinet = getattr(doctor, "cabinet", None) if doctor else None
        linked_doctor_found = doctor is not None
        doctor_has_cabinet = bool(doctor_cabinet)
        queue_cabinet = queue.cabinet_number
        effective_cabinet = queue_cabinet or doctor_cabinet
        integrity_warnings: list[str] = []

        if not linked_doctor_found:
            sync_status = "missing_doctor"
            integrity_warnings.append("linked_doctor_missing")
        elif not doctor_has_cabinet:
            sync_status = "doctor_cabinet_missing"
            integrity_warnings.append("doctor_cabinet_missing")
        elif queue_cabinet != doctor_cabinet:
            sync_status = "stale"
            integrity_warnings.append("queue_cabinet_stale")
        else:
            sync_status = "synced"

        if not effective_cabinet:
            integrity_warnings.append("effective_cabinet_missing")

        return {
            "id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_id": queue.specialist_id,
            "specialist_name": self._resolve_specialist_name(queue.specialist_id),
            "queue_tag": queue.queue_tag,
            "cabinet_number": queue_cabinet,
            "doctor_cabinet": doctor_cabinet,
            "effective_cabinet": effective_cabinet,
            "cabinet_floor": queue.cabinet_floor,
            "cabinet_building": queue.cabinet_building,
            "entries_count": self.read_repository.count_entries(queue_id=queue.id),
            "active": queue.active,
            "linked_doctor_found": linked_doctor_found,
            "doctor_has_cabinet": doctor_has_cabinet,
            "sync_status": sync_status,
            "integrity_warnings": integrity_warnings,
        }

    def list_queue_cabinet_info(
        self,
        *,
        day: date | None,
        specialist_id: int | None,
        cabinet_number: str | None,
    ) -> list[dict[str, Any]]:
        queues = self.read_repository.list_daily_queues(
            day_obj=day,
            specialist_id=specialist_id,
            cabinet_number=cabinet_number,
        )
        return [self._build_cabinet_payload(queue) for queue in queues]

    def get_queue_cabinet_info(self, *, queue_id: int) -> dict[str, Any]:
        queue = self.read_repository.get_queue(queue_id)
        if not queue:
            raise QueueDomainReadError(404, "Очередь не найдена")
        return self._build_cabinet_payload(queue)

    def allocate_ticket(self, *, allocation_mode: str, **kwargs: Any) -> object:
        if allocation_mode != "create_entry":
            raise ValueError(f"Unsupported queue allocation mode: {allocation_mode}")
        db = self.read_repository.db
        return queue_service.create_queue_entry(db=db, **kwargs)

    def enqueue(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError("QueueDomainService.enqueue is a Phase 2 method")

    def call_next(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError("QueueDomainService.call_next is a Phase 2 method")

    def mark_in_service(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.mark_in_service is a Phase 2 method"
        )

    def complete_visit(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.complete_visit is a Phase 2 method"
        )

    def cancel_queue_link(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.cancel_queue_link is a Phase 2 method"
        )

    def reschedule_queue_link(self, **_: Any) -> QueueSnapshot:
        raise NotImplementedError(
            "QueueDomainService.reschedule_queue_link is a Phase 2 method"
        )
