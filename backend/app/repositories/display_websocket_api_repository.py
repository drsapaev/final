"""Repository helpers for display_websocket endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.roles import DOCTOR_ROLE_SPELLINGS
from app.core.specialties import specialty_variants
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User


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
            .join(User, Doctor.user_id == User.id)
            .filter(
                Doctor.specialty.in_(specialty_variants(specialty)),
                Doctor.active.is_(True),
                # Codex round-5 P2: same owner-eligibility contract as the
                # clinic-wide join — an active legacy ghost (owner missing
                # per decision #13, deactivated or demoted to a non-doctor
                # role) must not be quick-callable either.
                User.is_active.is_(True),
                func.lower(User.role).in_(sorted(DOCTOR_ROLE_SPELLINGS)),
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
                OnlineQueueEntry.status,
                func.count(OnlineQueueEntry.id),
            )
            .join(OnlineQueueEntry, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                DailyQueue.day == today,
                DailyQueue.specialist_id.in_(doctor_ids),
                # Codex round-2 P1: an active doctor may retain a same-day
                # INACTIVE queue with waiting entries — counting them can
                # hand the call to that doctor while a sibling holds the
                # live active queue, and quick_call_next would then fetch
                # the inactive row. Only active queues are quick-call
                # candidates (selection AND the later lookup agree).
                DailyQueue.active.is_(True),
                OnlineQueueEntry.status.in_(["waiting", "called"]),
            )
            .group_by(DailyQueue.specialist_id, OnlineQueueEntry.status)
            .all()
        )
        active_loads: dict[int, int] = {}
        waiting_loads: dict[int, int] = {}
        for specialist_id, status_value, count in load_rows:
            active_loads[specialist_id] = active_loads.get(specialist_id, 0) + count
            if status_value == "waiting":
                waiting_loads[specialist_id] = count

        # Codex round-1 P1: quick-call must actually CALL someone. A doctor
        # whose queue holds NO waiting entries (no queue row / empty queue /
        # only already-called entries) has "load 0" in the raw least-loaded
        # ranking and used to win the pick while another doctor's patients
        # stayed uncalled — quick_call_next then answered 404/queue_empty.
        # Route among doctors whose queue REALLY has waiting entries first;
        # Codex round-5 P2: those candidates are still ranked by the
        # documented D-2 load metric (waiting+called = active_loads), NOT
        # by the waiting count alone — 1 waiting + 10 called loses to
        # 2 waiting + 0 called. Only when NO candidate has waiting entries
        # does the legacy least-active-load pick stand (the downstream
        # 404/queue_empty is then the same signal the single-doctor flow
        # produced).
        candidates_with_waiting = [
            d for d in doctors if waiting_loads.get(d.id, 0) > 0
        ]
        if candidates_with_waiting:
            return min(
                candidates_with_waiting,
                key=lambda d: (active_loads.get(d.id, 0), d.id),
            )
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
        """The doctor's ACTIVE same-day queue that quick-call will actually
        serve (Codex round-2 P1: active-only; Codex round-4 P1: when the
        doctor holds several active queues under different tags, the lookup
        must agree with the selection half — the queue holding WAITING
        entries wins (most waiting first, tie to the lowest queue id), so
        the picker can never elect a doctor "because tag A has waiting
        patients" and then fetch their empty tag B queue)."""
        return (
            self.db.query(DailyQueue)
            .outerjoin(
                OnlineQueueEntry,
                and_(
                    OnlineQueueEntry.queue_id == DailyQueue.id,
                    OnlineQueueEntry.status == "waiting",
                ),
            )
            .filter(
                DailyQueue.day == day,
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.active.is_(True),
            )
            .group_by(DailyQueue.id)
            .order_by(
                func.count(OnlineQueueEntry.id).desc(),
                DailyQueue.id.asc(),
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
