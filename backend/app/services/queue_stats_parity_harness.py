from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.queue_profile import QueueProfile
from app.services.online_queue import load_stats

STRICT_PARITY_FIELDS = ("last_ticket", "waiting", "serving", "done")
COMPATIBILITY_FIELDS = ("is_open", "start_number")
WAITING_STATUSES = frozenset({"waiting"})
SERVING_STATUSES = frozenset({"called", "in_service", "diagnostics"})
DONE_STATUSES = frozenset({"served"})


@dataclass(frozen=True)
class QueuesStatsSnapshot:
    department: str
    date_str: str
    is_open: bool | None
    start_number: int | None
    last_ticket: int
    waiting: int
    serving: int
    done: int


@dataclass(frozen=True)
class QueuesStatsParityResult:
    department: str
    date_str: str
    legacy: QueuesStatsSnapshot
    candidate: QueuesStatsSnapshot
    matched_queue_ids: list[int] = field(default_factory=list)
    matched_queue_tags: list[str | None] = field(default_factory=list)
    mapping_notes: list[str] = field(default_factory=list)
    strict_matches: dict[str, bool] = field(default_factory=dict)
    compatibility_matches: dict[str, bool] = field(default_factory=dict)

    @property
    def strict_mismatches(self) -> list[str]:
        return [field for field, matched in self.strict_matches.items() if not matched]

    @property
    def compatibility_mismatches(self) -> list[str]:
        return [
            field for field, matched in self.compatibility_matches.items() if not matched
        ]

    @property
    def strict_parity_ok(self) -> bool:
        return not self.strict_mismatches


@dataclass(frozen=True)
class QueuesStatsReplacementResult:
    snapshot: QueuesStatsSnapshot
    strict_source: str
    matched_queue_ids: list[int] = field(default_factory=list)
    matched_queue_tags: list[str | None] = field(default_factory=list)
    mapping_notes: list[str] = field(default_factory=list)


def compare_queues_stats(
    db: Session, *, department: str, date_str: str
) -> QueuesStatsParityResult:
    normalized_department = department.strip()
    legacy = load_stats(db, department=normalized_department, date_str=date_str.strip())
    candidate, matched_queue_ids, matched_queue_tags, mapping_notes = (
        build_candidate_queues_stats(
            db, department=normalized_department, date_str=date_str.strip()
        )
    )

    strict_matches = {
        field: getattr(legacy, field) == getattr(candidate, field)
        for field in STRICT_PARITY_FIELDS
    }
    compatibility_matches = {
        field: getattr(legacy, field) == getattr(candidate, field)
        for field in COMPATIBILITY_FIELDS
    }

    return QueuesStatsParityResult(
        department=normalized_department,
        date_str=date_str.strip(),
        legacy=QueuesStatsSnapshot(
            department=legacy.department,
            date_str=legacy.date_str,
            is_open=legacy.is_open,
            start_number=legacy.start_number,
            last_ticket=legacy.last_ticket,
            waiting=legacy.waiting,
            serving=legacy.serving,
            done=legacy.done,
        ),
        candidate=candidate,
        matched_queue_ids=matched_queue_ids,
        matched_queue_tags=matched_queue_tags,
        mapping_notes=mapping_notes,
        strict_matches=strict_matches,
        compatibility_matches=compatibility_matches,
    )


def build_replacement_queues_stats(
    db: Session, *, department: str, date_str: str
) -> QueuesStatsReplacementResult:
    normalized_department = department.strip()
    normalized_date = date_str.strip()
    legacy = load_stats(db, department=normalized_department, date_str=normalized_date)
    candidate, matched_queue_ids, matched_queue_tags, mapping_notes = (
        build_candidate_queues_stats(
            db, department=normalized_department, date_str=normalized_date
        )
    )

    if matched_queue_ids:
        snapshot = QueuesStatsSnapshot(
            department=legacy.department,
            date_str=legacy.date_str,
            is_open=legacy.is_open,
            start_number=legacy.start_number,
            last_ticket=candidate.last_ticket,
            waiting=candidate.waiting,
            serving=candidate.serving,
            done=candidate.done,
        )
        strict_source = "ssot"
    else:
        snapshot = QueuesStatsSnapshot(
            department=legacy.department,
            date_str=legacy.date_str,
            is_open=legacy.is_open,
            start_number=legacy.start_number,
            last_ticket=legacy.last_ticket,
            waiting=legacy.waiting,
            serving=legacy.serving,
            done=legacy.done,
        )
        strict_source = "legacy_fallback"
        mapping_notes = [
            *mapping_notes,
            "No SSOT queue mapping resolved; preserved legacy strict counters.",
        ]

    return QueuesStatsReplacementResult(
        snapshot=snapshot,
        strict_source=strict_source,
        matched_queue_ids=matched_queue_ids,
        matched_queue_tags=matched_queue_tags,
        mapping_notes=mapping_notes,
    )


def build_candidate_queues_stats(
    db: Session, *, department: str, date_str: str
) -> tuple[QueuesStatsSnapshot, list[int], list[str | None], list[str]]:
    target_day = date.fromisoformat(date_str)
    queues, mapping_notes = _resolve_department_queues(
        db, department=department, target_day=target_day
    )

    if not queues:
        return (
            QueuesStatsSnapshot(
                department=department,
                date_str=date_str,
                is_open=None,
                start_number=None,
                last_ticket=0,
                waiting=0,
                serving=0,
                done=0,
            ),
            [],
            [],
            mapping_notes,
        )

    queue_ids = [queue.id for queue in queues]
    queue_tags = [queue.queue_tag for queue in queues]
    entries = (
        db.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id.in_(queue_ids))
        .all()
    )

    candidate = QueuesStatsSnapshot(
        department=department,
        date_str=date_str,
        is_open=None,
        start_number=None,
        last_ticket=max((entry.number or 0 for entry in entries), default=0),
        waiting=sum(1 for entry in entries if entry.status in WAITING_STATUSES),
        serving=sum(1 for entry in entries if entry.status in SERVING_STATUSES),
        done=sum(1 for entry in entries if entry.status in DONE_STATUSES),
    )
    return candidate, queue_ids, queue_tags, mapping_notes


def _resolve_department_queues(
    db: Session, *, department: str, target_day: date
) -> tuple[list[DailyQueue], list[str]]:
    normalized_department = department.strip().lower()
    profiles = (
        db.query(QueueProfile)
        .filter(
            QueueProfile.is_active.is_(True),
            QueueProfile.department_key == normalized_department,
        )
        .all()
    )
    mapped_queue_tags = _collect_profile_queue_tags(profiles)
    mapping_notes: list[str] = []
    if mapped_queue_tags:
        mapping_notes.append(
            "Matched queues via QueueProfile.department_key -> queue_tags mapping."
        )
    else:
        mapping_notes.append(
            "No QueueProfile.department_key mapping found; using doctor.department and "
            "queue_tag/specialty fallbacks."
        )

    queues = (
        db.query(DailyQueue)
        .options(joinedload(DailyQueue.specialist).joinedload(Doctor.department))
        .filter(DailyQueue.day == target_day)
        .order_by(DailyQueue.id.asc())
        .all()
    )

    matched: list[DailyQueue] = []
    for queue in queues:
        queue_tag = (queue.queue_tag or "").strip().lower()
        doctor = queue.specialist
        department_key = None
        specialty = None
        if doctor:
            specialty = (doctor.specialty or "").strip().lower()
            if doctor.department:
                department_key = (doctor.department.key or "").strip().lower()

        if queue_tag and queue_tag in mapped_queue_tags:
            matched.append(queue)
            continue
        if department_key == normalized_department:
            matched.append(queue)
            continue
        if queue_tag == normalized_department or specialty == normalized_department:
            matched.append(queue)

    # Preserve order but deduplicate if a queue matched by multiple heuristics.
    unique: list[DailyQueue] = []
    seen_ids: set[int] = set()
    for queue in matched:
        if queue.id in seen_ids:
            continue
        seen_ids.add(queue.id)
        unique.append(queue)
    return unique, mapping_notes


def _collect_profile_queue_tags(profiles: list[QueueProfile]) -> set[str]:
    mapped_queue_tags: set[str] = set()
    for profile in profiles:
        if profile.key:
            mapped_queue_tags.add(profile.key.strip().lower())
        for queue_tag in profile.queue_tags or []:
            if queue_tag:
                mapped_queue_tags.add(str(queue_tag).strip().lower())
    return mapped_queue_tags
