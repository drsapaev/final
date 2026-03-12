from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.services.board_state_read_adapter import BoardStateReadAdapter
from app.services.online_queue import load_stats
from app.services.queue_stats_parity_harness import build_replacement_queues_stats

STRICT_QUEUE_FIELDS = ("department", "date_str", "last_ticket", "waiting", "serving", "done")
COMPATIBILITY_FIELDS = ("is_open", "start_number")
DISPLAY_DEFERRED_FIELDS = (
    "brand",
    "logo",
    "is_paused",
    "is_closed",
    "announcement",
    "announcement_ru",
    "announcement_uz",
    "announcement_en",
    "primary_color",
    "bg_color",
    "text_color",
    "contrast_default",
    "kiosk_default",
    "sound_default",
)


@dataclass(frozen=True)
class LegacyBoardStateSnapshot:
    department: str
    date_str: str
    is_open: bool | None
    start_number: int | None
    last_ticket: int
    waiting: int
    serving: int
    done: int


@dataclass(frozen=True)
class BoardStateParityResult:
    legacy: LegacyBoardStateSnapshot
    candidate: dict[str, Any]
    strict_queue_matches: dict[str, bool] = field(default_factory=dict)
    compatibility_matches: dict[str, bool] = field(default_factory=dict)
    noncomparable_display_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def strict_queue_mismatches(self) -> list[str]:
        return [field for field, matched in self.strict_queue_matches.items() if not matched]

    @property
    def compatibility_mismatches(self) -> list[str]:
        return [field for field, matched in self.compatibility_matches.items() if not matched]

    @property
    def strict_queue_parity_ok(self) -> bool:
        return not self.strict_queue_mismatches

    @property
    def compatibility_parity_ok(self) -> bool:
        return not self.compatibility_mismatches


def build_legacy_board_state_snapshot(
    db: Session, *, department: str, date_str: str
) -> LegacyBoardStateSnapshot:
    stats = load_stats(db, department=department, date_str=date_str)
    return LegacyBoardStateSnapshot(
        department=stats.department,
        date_str=stats.date_str,
        is_open=stats.is_open,
        start_number=stats.start_number,
        last_ticket=stats.last_ticket,
        waiting=stats.waiting,
        serving=stats.serving,
        done=stats.done,
    )


def compare_board_state(
    db: Session,
    *,
    department: str,
    date_str: str,
    display_board: Any | None = None,
    display_announcements: Sequence[Any] | None = None,
) -> BoardStateParityResult:
    legacy = build_legacy_board_state_snapshot(
        db, department=department.strip(), date_str=date_str.strip()
    )
    replacement = build_replacement_queues_stats(
        db, department=department.strip(), date_str=date_str.strip()
    )
    adapter = BoardStateReadAdapter()
    candidate_payload = adapter.assemble_candidate(
        display_board=display_board,
        display_announcements=display_announcements,
        queue_state=replacement,
        compatibility_fields={
            "is_open": legacy.is_open,
            "start_number": legacy.start_number,
        },
    )

    strict_queue_matches = {
        field: legacy_value == candidate_payload.queue_state.__dict__[field]
        for field, legacy_value in {
            "department": legacy.department,
            "date_str": legacy.date_str,
            "last_ticket": legacy.last_ticket,
            "waiting": legacy.waiting,
            "serving": legacy.serving,
            "done": legacy.done,
        }.items()
    }
    compatibility_matches = {
        field: legacy_value == candidate_payload.compatibility.__dict__[field]
        for field, legacy_value in {
            "is_open": legacy.is_open,
            "start_number": legacy.start_number,
        }.items()
    }

    display_metadata = candidate_payload.display_metadata.__dict__
    noncomparable_display_fields = [
        field
        for field in DISPLAY_DEFERRED_FIELDS
        if display_metadata.get(field) is not None
    ]
    notes: list[str] = []
    if noncomparable_display_fields:
        notes.append(
            "Display metadata fields are adapter-wired but not comparable to the "
            "legacy mounted contract because /board/state does not expose them."
        )

    return BoardStateParityResult(
        legacy=legacy,
        candidate=candidate_payload.to_dict(),
        strict_queue_matches=strict_queue_matches,
        compatibility_matches=compatibility_matches,
        noncomparable_display_fields=noncomparable_display_fields,
        notes=notes,
    )
