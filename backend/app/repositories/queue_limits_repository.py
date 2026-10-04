"""Repository helpers for queue_limits endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.specialties import specialty_variants
from app.crud.daily_queue_creation_policy import daily_queue_creation_snapshot
from app.crud.queue_resource_routing import lock_daily_queue_creation
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry


class QueueLimitsRepository:
    """Encapsulates doctor/queue lookups used by queue limit API."""

    def __init__(self, db: Session):
        self.db = db

    def list_active_doctors(self, *, specialty: str | None) -> list[Doctor]:
        query = self.db.query(Doctor).filter(Doctor.active.is_(True))
        if specialty:
            # D-1 canonical vocabulary: any dental-family spelling must
            # find canonical rows too (e.g. /admin/queue-limits filtered
            # by the legacy profile key "stomatology" must still see
            # "dentistry" doctors after migration 0049 — Codex round-3 P1).
            query = query.filter(Doctor.specialty.in_(specialty_variants(specialty)))
        return query.all()

    def get_daily_queue(self, *, day: date, specialist_id: int) -> DailyQueue | None:
        """The doctor's ACTIVE queue for ``day`` (Codex round-4 P2: an
        inactive historical row for the same day must not feed usage counts
        or the aggregate capacity — QR joins operate on active rows).
        Deterministic ordering when several rows match."""
        return (
            self.db.query(DailyQueue)
            .filter(
                and_(
                    DailyQueue.day == day,
                    DailyQueue.specialist_id == specialist_id,
                    DailyQueue.active.is_(True),
                )
            )
            .order_by(DailyQueue.id.asc())
            .first()
        )

    def count_entries(self, *, queue_id: int) -> int:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
        )

    def count_active_entries(self, *, queue_id: int) -> int:
        """Count queue length using the same active statuses as legacy admission."""
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.status.in_(("waiting", "called")),
            )
            .count()
        )

    def list_active_daily_queues(
        self, *, day: date, specialist_id: int
    ) -> list[DailyQueue]:
        """ALL active same-day queues of the doctor (Codex round-5 P2: a
        doctor may hold several active queues under different tags — the
        aggregate capacity must enumerate every enforced cap)."""
        return (
            self.db.query(DailyQueue)
            .filter(
                and_(
                    DailyQueue.day == day,
                    DailyQueue.specialist_id == specialist_id,
                    DailyQueue.active.is_(True),
                )
            )
            .order_by(DailyQueue.id.asc())
            .all()
        )

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_or_create_daily_queue(
        self,
        *,
        day: date,
        specialist_id: int,
        max_online_entries: int,
    ) -> DailyQueue:
        # Lock-parity follow-up to the #3511 review: serialize the
        # check-then-insert window below on the canonical (day, doctor)
        # advisory key — the same scope
        # queue_service.get_or_create_daily_queue holds. An admin limit
        # write racing a canonical writer (registrar cart, morning
        # assignment) for the same (day, doctor) could both observe no
        # queue and insert — the partial unique then fails the loser
        # with an unhandled IntegrityError instead of the clean
        # block → re-read → reuse this lock provides. Advisory-first:
        # nothing row-locked earlier in this flow; save()'s commit
        # releases the transaction-scoped lock.
        lock_daily_queue_creation(self.db, day, specialist_id)
        queue = self.get_daily_queue(day=day, specialist_id=specialist_id)
        if not queue:
            doctor = self.db.get(Doctor, specialist_id)
            queue = DailyQueue(
                day=day,
                specialist_id=specialist_id,
                active=True,
                max_online_entries=max_online_entries,
                **daily_queue_creation_snapshot(
                    self.db, day=day, doctor=doctor, queue_tag=None
                ),
            )
            self.db.add(queue)
        return queue

    def save(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
