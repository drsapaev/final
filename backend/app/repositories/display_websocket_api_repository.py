"""Repository helpers for display_websocket endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.specialties import specialty_variants
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry


class DisplayWebSocketApiRepository:
    """Encapsulates queue/doctor lookups used by display websocket API."""

    def __init__(self, db: Session):
        self.db = db

    def get_queue_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == entry_id)
            .first()
        )

    def save(self) -> None:
        self.db.commit()

    def list_active_entries_for_day(self, *, day: date) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue)
            .filter(DailyQueue.day == day, DailyQueue.active.is_(True))
            .all()
        )

    def get_active_doctor_by_specialty(self, specialty: str) -> Doctor | None:
        """Least-loaded quick-call target (D-2) over every family-spelling
        match (D-1): /queues/profiles/public still exposes the supported
        legacy profile key 'stomatology', so a quick call with any family
        spelling must resolve canonical 'dentistry' doctors after
        migration 0049 (Codex round-4 P1 — exact == returned 404/403).

        With several active doctors of the specialty, the display board
        calls next for the doctor whose ACTIVE queue (waiting+called
        entries) is shortest today; ties break to the lowest Doctor.id
        (deterministic)."""
        doctors = (
            self.db.query(Doctor)
            .filter(
                Doctor.specialty.in_(specialty_variants(specialty)),
                Doctor.active.is_(True),
            )
            .order_by(Doctor.id.asc())
            .all()
        )
        if not doctors:
            return None
        if len(doctors) == 1:
            return doctors[0]

        today = date.today()
        doctor_ids = [d.id for d in doctors]
        load_rows = (
            self.db.query(
                DailyQueue.specialist_id,
                func.count(OnlineQueueEntry.id),
            )
            .join(OnlineQueueEntry, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                DailyQueue.day == today,
                DailyQueue.specialist_id.in_(doctor_ids),
                OnlineQueueEntry.status.in_(["waiting", "called"]),
            )
            .group_by(DailyQueue.specialist_id)
            .all()
        )
        active_loads = {specialist_id: count for specialist_id, count in load_rows}
        return min(doctors, key=lambda d: (active_loads.get(d.id, 0), d.id))

    def get_active_doctor_by_user_id(self, user_id: int) -> Doctor | None:
        return (
            self.db.query(Doctor)
            .filter(Doctor.user_id == user_id, Doctor.active.is_(True))
            .first()
        )

    def get_daily_queue_for_specialist(
        self,
        *,
        day: date,
        specialist_id: int,
    ) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == day,
                DailyQueue.specialist_id == specialist_id,
            )
            .first()
        )

    def get_next_waiting_entry(self, *, queue_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(OnlineQueueEntry.number)
            .first()
        )
