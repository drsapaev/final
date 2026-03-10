from __future__ import annotations

"""Internal skeleton for a future SSOT-backed board-state adapter."""

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BoardStateDisplayMetadata:
    brand: str | None = None
    logo: str | None = None
    is_paused: bool | None = None
    is_closed: bool | None = None
    announcement: str | None = None
    announcement_ru: str | None = None
    announcement_uz: str | None = None
    announcement_en: str | None = None
    primary_color: str | None = None
    bg_color: str | None = None
    text_color: str | None = None
    contrast_default: bool | None = None
    kiosk_default: bool | None = None
    sound_default: bool | None = None


@dataclass(frozen=True)
class BoardStateQueueState:
    department: str | None = None
    date_str: str | None = None
    last_ticket: int | None = None
    waiting: int | None = None
    serving: int | None = None
    done: int | None = None


@dataclass(frozen=True)
class BoardStateCompatibilityFields:
    is_open: bool | None = None
    start_number: int | None = None


@dataclass(frozen=True)
class BoardStateAdapterPayload:
    display_metadata: BoardStateDisplayMetadata
    queue_state: BoardStateQueueState
    compatibility: BoardStateCompatibilityFields

    def to_dict(self) -> dict[str, Any]:
        return {
            "display_metadata": asdict(self.display_metadata),
            "queue_state": asdict(self.queue_state),
            "compatibility": asdict(self.compatibility),
        }


class BoardStateReadAdapter:
    """Future composition seam for board metadata and queue-state inputs."""

    def build_skeleton(self) -> BoardStateAdapterPayload:
        return BoardStateAdapterPayload(
            display_metadata=BoardStateDisplayMetadata(),
            queue_state=BoardStateQueueState(),
            compatibility=BoardStateCompatibilityFields(),
        )

    def assemble_candidate(
        self,
        *,
        display_board: Any | None = None,
        queue_state: Mapping[str, Any] | None = None,
        compatibility_fields: Mapping[str, Any] | None = None,
    ) -> BoardStateAdapterPayload:
        return BoardStateAdapterPayload(
            display_metadata=self._build_display_metadata(display_board),
            queue_state=self._build_queue_state(queue_state),
            compatibility=self._build_compatibility_fields(compatibility_fields),
        )

    def _build_display_metadata(self, display_board: Any | None) -> BoardStateDisplayMetadata:
        if display_board is None:
            return BoardStateDisplayMetadata()

        colors = getattr(display_board, "colors", None) or {}
        display_name = getattr(display_board, "display_name", None)
        name = getattr(display_board, "name", None)

        return BoardStateDisplayMetadata(
            brand=display_name or name,
            sound_default=getattr(display_board, "sound_enabled", None),
            primary_color=colors.get("primary"),
            bg_color=colors.get("background"),
            text_color=colors.get("text"),
        )

    def _build_queue_state(
        self, queue_state: Mapping[str, Any] | None
    ) -> BoardStateQueueState:
        if not queue_state:
            return BoardStateQueueState()

        return BoardStateQueueState(
            department=queue_state.get("department"),
            date_str=queue_state.get("date_str"),
            last_ticket=queue_state.get("last_ticket"),
            waiting=queue_state.get("waiting"),
            serving=queue_state.get("serving"),
            done=queue_state.get("done"),
        )

    def _build_compatibility_fields(
        self, compatibility_fields: Mapping[str, Any] | None
    ) -> BoardStateCompatibilityFields:
        if not compatibility_fields:
            return BoardStateCompatibilityFields()

        return BoardStateCompatibilityFields(
            is_open=compatibility_fields.get("is_open"),
            start_number=compatibility_fields.get("start_number"),
        )
