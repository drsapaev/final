"""Repository helpers for display_websocket endpoints."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.roles import DOCTOR_ROLE_SPELLINGS
from app.core.specialties import specialty_variants
from app.models.clinic import Doctor
from app.models.display_config import DisplayBoard
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User


def resolve_display_board_targets(
    db: Session, board_ids: list[int] | list[str]
) -> tuple[list[str], list[int]]:
    """DISPLAYTARGET-BE-001 (audit PR #3961): REST call/announcement
    ``board_ids`` arrive as integer DB ids, while the WebSocket manager keys
    rooms by the board *name* string (``DisplayBoard.name`` — e.g.
    ``"main_board"``). Map int ids to their name room keys; string elements
    (the quick-call plane passes board names directly) pass through
    unchanged.

    Returns ``(names, unknown_ids)`` — order-preserving. Ids with no
    ``DisplayBoard`` row land in ``unknown_ids`` so the caller can report
    them honestly; an explicit unresolvable request must NOT silently fall
    back to broadcasting on every live room.
    """
    int_ids = [b for b in board_ids if isinstance(b, int) and not isinstance(b, bool)]
    id_to_name: dict[int, str] = {}
    if int_ids:
        rows = db.query(DisplayBoard).filter(DisplayBoard.id.in_(int_ids)).all()
        id_to_name = {row.id: row.name for row in rows}

    names: list[str] = []
    unknown: list[int] = []
    for b in board_ids:
        if isinstance(b, str):
            names.append(b)
        elif isinstance(b, int) and not isinstance(b, bool):
            name = id_to_name.get(b)
            if name is None:
                unknown.append(b)
            else:
                names.append(name)
        else:
            unknown.append(b)
    return names, unknown


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

    def resolve_display_board_targets(
        self, board_ids: list[int] | list[str]
    ) -> tuple[list[str], list[int]]:
        """Delegate to the module-level resolver (DISPLAYTARGET-BE-001)."""
        return resolve_display_board_targets(self.db, board_ids)

    def save(self) -> None:
        self.db.commit()

    def list_active_entries_for_department(
        self, *, day: date, department: str
    ) -> list[OnlineQueueEntry]:
        """DISPLAYWS-BE-003 (audit PR #3961 round 30): the department queue
        snapshot is scoped to the requested department through the two SSOT
        ownership axes — never "every active queue of the day" again:

        - registry tag axis: ``DailyQueue.queue_tag`` equals any family
          spelling of the department key (doctorless resource surfaces:
          lab, ecg, ...);
        - doctor specialty axis: ``Doctor.specialty`` equals any family
          spelling (``specialty_variants`` — 'stomatology' reaches doctors
          stored as 'dentistry', D-1 canonical vocabulary).

        An unknown department resolves to zero matching queues and returns
        an honest empty list instead of mislabeled cross-department PHI.
        Comparisons are case-insensitive on both sides (legacy rows keep
        mixed-case stored spellings).
        """
        key = (department or "").strip().lower()
        if not key:
            return []
        spellings = {
            spelling.strip().lower()
            for spelling in specialty_variants(key)
            if spelling and spelling.strip()
        }
        spellings.add(key)
        return (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .outerjoin(Doctor, DailyQueue.specialist_id == Doctor.id)
            .filter(
                DailyQueue.day == day,
                DailyQueue.active.is_(True),
                or_(
                    func.lower(func.coalesce(DailyQueue.queue_tag, "")).in_(
                        sorted(spellings)
                    ),
                    func.lower(func.coalesce(Doctor.specialty, "")).in_(
                        sorted(spellings)
                    ),
                ),
            )
            .all()
        )

    def get_active_doctor_by_specialty(
        self, specialty: str, day: date | None = None
    ) -> Doctor | None:
        """Least-loaded quick-call target (D-2) over every family-spelling
        match (D-1): /queues/profiles/public still exposes the supported
        legacy profile key 'stomatology', so a quick call with any family
        spelling must resolve canonical 'dentistry' doctors after
        migration 0049 (Codex round-4 P1 — exact == returned 404/403).

        With several active doctors of the specialty, the display board
        calls next for the doctor whose ACTIVE queue (waiting+called
        entries) is shortest today; ties break to the lowest Doctor.id
        (deterministic).

        DISPLAYQUICK-BE-001 (audit PR #3961): the load-counting day is a
        canonical parameter — the service passes the CLINIC-local day
        (queue-settings timezone SSOT, the same day the queue lookup
        uses). ``day=None`` keeps the legacy host-local ``date.today()``
        fallback for old callers; no timezone logic lives here."""
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

        # DISPLAYQUICK-BE-001 (audit PR #3961): canonical day from the
        # service (clinic-local SSOT) — the host-local date disagreed with
        # the queue lookup across the clinic midnight window (UTC host
        # 19:00-24:00Z for Asia/Tashkent) and elected a doctor whose
        # current-clinic-day queue was empty/missing.
        effective_day = day if day is not None else date.today()
        doctor_ids = [d.id for d in doctors]
        load_rows = (
            self.db.query(
                DailyQueue.specialist_id,
                OnlineQueueEntry.status,
                func.count(OnlineQueueEntry.id),
            )
            .join(OnlineQueueEntry, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                DailyQueue.day == effective_day,
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
        candidates_with_waiting = [d for d in doctors if waiting_loads.get(d.id, 0) > 0]
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
        """DISPLAYCALL-BE-002 (audit PR #3961 round 30): quick-call 'next'
        follows the canonical staff fairness selector (queue_svc
        ``staff_call_next_patient``): priority DESC, then
        coalesce(queue_time, created_at) ASC, then id ASC as the
        deterministic tie-break — NOT the printed ticket number, which
        would bypass restored (priority=1) patients."""
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(
                OnlineQueueEntry.priority.desc(),
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
            .first()
        )

    def claim_waiting_entry(
        self,
        entry: OnlineQueueEntry,
        *,
        called_at: datetime,
        called_by_user_id: int | None,
    ) -> bool:
        """DISPLAYCALL-BE-003 (audit PR #3961 round 30): the waiting→called
        transition is ONE conditional UPDATE keyed on status='waiting' —
        two concurrent display quick-calls can never both claim the same
        entry. Returns True iff THIS caller won the row; the service turns
        a False return into a 409 without any broadcast.

        The ORM row is refreshed here so the caller reads committed state
        without touching the session directly (service/repository boundary
        guard)."""
        updated = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == entry.id,
                OnlineQueueEntry.status == "waiting",
            )
            .update(
                {
                    "status": "called",
                    "called_at": called_at,
                    "called_by_user_id": called_by_user_id,
                    "updated_at": called_at,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        if updated:
            self.db.refresh(entry)
        return updated == 1
