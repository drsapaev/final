"""Repository helpers for queue legacy endpoints."""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.crud import clinic as crud_clinic
from app.crud.queue_resource_routing import (
    find_active_tag_queue,
    lock_registry_tag_creation,
    resolve_tag_resource,
    resolve_tag_resource_locked,
    tag_routes_to_resource,
)
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User

logger = logging.getLogger(__name__)


class QueueApiRepository:
    """Encapsulates ORM operations used by legacy queue endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def get_doctor_user(self, specialist_id: int) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == specialist_id, User.role == "Doctor")
            .first()
        )

    def get_daily_queue(self, *, day: date, specialist_id: int) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id)
            .first()
        )

    def create_daily_queue(self, *, day: date, specialist_id: int) -> DailyQueue:
        daily_queue = DailyQueue(day=day, specialist_id=specialist_id, active=True)
        self.db.add(daily_queue)
        self.db.commit()
        self.db.refresh(daily_queue)
        return daily_queue

    def get_or_create_registry_queue(
        self, *, day: date, queue_tag: str
    ) -> DailyQueue | None:
        """QD-2C (Codex round-6 P1): the (day, tag) registry surface for
        the legacy doctor-keyed writers.

        ``POST /queue/legacy/open`` addresses a queue by the synthetic
        Doctor's id; left on the raw doctor path it creates an active
        UNTAGGED doctor-keyed row right next to the live resource queue
        (the shadow the token/status/open paths would then report). The
        registry surface wins instead: an existing surface is returned,
        an ACTIVE registry row gets the resource-owned queue created
        (specialist NULL — the same creation contract as every switched
        writer: lock + row-locked recheck, caps from the registry row),
        and a tag WITHOUT a registry row returns None so the caller
        keeps its legacy doctor path byte-identically.

        Flush-only (no commit): the caller's own commit (e.g.
        set_opened_at_now) covers the row, mirroring the
        visit-confirmation creation branch.
        """
        surface = tag_routes_to_resource(self.db, queue_tag, day)
        if surface is not None:
            return surface
        resource = resolve_tag_resource(self.db, queue_tag)
        if resource is None:
            return None
        lock_registry_tag_creation(self.db, queue_tag, day)
        # Codex round-6 P2: row-locked recheck with populate_existing
        resource = resolve_tag_resource_locked(self.db, queue_tag)
        if resource is None:
            return None
        existing = find_active_tag_queue(self.db, day, queue_tag)
        if existing is not None:
            return existing
        settings = crud_clinic.get_queue_settings(self.db)
        daily_queue = DailyQueue(
            day=day,
            specialist_id=None,
            queue_resource_id=int(resource.id),
            queue_tag=queue_tag,
            active=True,
            online_start_time=f"{int(settings.get('queue_start_hour', 7)):02d}:00",
            online_end_time=f"{int(settings.get('queue_end_hour', 9)):02d}:00",
            max_online_entries=resource.max_online_per_day,
            # Codex round-8 P2: канонический кабинет реестра — паритет
            # с queue_svc-конструктором (round-7)
            cabinet_number=resource.default_cabinet,
        )
        self.db.add(daily_queue)
        self.db.flush()
        logger.info(
            "[QD-2C] legacy writer created resource DailyQueue id=%s "
            "day=%s resource=%s queue_tag=%s",
            daily_queue.id,
            day,
            resource.id,
            queue_tag,
        )
        return daily_queue

    def set_opened_at_now(self, daily_queue: DailyQueue) -> None:
        daily_queue.opened_at = datetime.now()
        self.db.commit()

    # UX Audit Registrar #7: close_daily_queue — сброс opened_at.
    def set_opened_at_none(self, daily_queue: DailyQueue) -> None:
        daily_queue.opened_at = None
        self.db.commit()

    def get_doctor(self, specialist_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == specialist_id).first()

    def list_queue_entries(self, *, queue_id: int) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .order_by(OnlineQueueEntry.number)
            .all()
        )

    def get_queue_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == entry_id)
            .first()
        )

    def mark_entry_called(
        self, entry: OnlineQueueEntry, *, called_by_user_id: int | None = None
    ) -> None:
        entry.status = "called"
        entry.called_at = datetime.now()
        # QF-1 (operator attribution): caller identity threaded from the
        # endpoint (legacy POST /queue/call/{entry_id}); None keeps NULL.
        entry.called_by_user_id = called_by_user_id
        self.db.commit()
