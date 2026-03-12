from __future__ import annotations

"""Internal skeleton for a future SSOT-backed board-state adapter."""

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


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
        display_announcements: Sequence[Any] | None = None,
        display_settings: Mapping[str, Any] | None = None,
        queue_state: Mapping[str, Any] | None = None,
        compatibility_fields: Mapping[str, Any] | None = None,
    ) -> BoardStateAdapterPayload:
        return BoardStateAdapterPayload(
            display_metadata=self._build_display_metadata(
                display_board=display_board,
                display_announcements=display_announcements,
                display_settings=display_settings,
            ),
            queue_state=self._build_queue_state(queue_state),
            compatibility=self._build_compatibility_fields(compatibility_fields),
        )

    def _build_display_metadata(
        self,
        *,
        display_board: Any | None,
        display_announcements: Sequence[Any] | None,
        display_settings: Mapping[str, Any] | None,
    ) -> BoardStateDisplayMetadata:
        colors = getattr(display_board, "colors", None) or {}
        display_name = getattr(display_board, "display_name", None) if display_board else None
        name = getattr(display_board, "name", None) if display_board else None
        announcements = self._build_announcement_fields(display_announcements)
        settings = display_settings or {}

        return BoardStateDisplayMetadata(
            brand=display_name or name,
            logo=self._coerce_str_setting(
                settings.get("logo"),
                fallback=settings.get("logo_url"),
            ),
            announcement=announcements["announcement"],
            announcement_ru=announcements["announcement_ru"],
            announcement_uz=announcements["announcement_uz"],
            announcement_en=announcements["announcement_en"],
            sound_default=getattr(display_board, "sound_enabled", None),
            primary_color=colors.get("primary"),
            bg_color=colors.get("background"),
            text_color=colors.get("text"),
            contrast_default=self._coerce_bool_setting(settings.get("contrast_default")),
            kiosk_default=self._coerce_bool_setting(settings.get("kiosk_default")),
        )

    def _build_announcement_fields(
        self, display_announcements: Sequence[Any] | None
    ) -> dict[str, str | None]:
        result = {
            "announcement": None,
            "announcement_ru": None,
            "announcement_uz": None,
            "announcement_en": None,
        }
        if not display_announcements:
            return result

        active_announcements = [
            announcement
            for announcement in display_announcements
            if getattr(announcement, "active", True)
        ]
        ordered_announcements = sorted(
            active_announcements,
            key=lambda announcement: getattr(announcement, "priority", 0),
            reverse=True,
        )
        if not ordered_announcements:
            return result

        result["announcement"] = getattr(ordered_announcements[0], "message", None)
        language_field_map = {
            "ru": "announcement_ru",
            "uz": "announcement_uz",
            "en": "announcement_en",
        }
        for announcement in ordered_announcements:
            language = getattr(announcement, "language", None)
            field_name = language_field_map.get(language)
            if field_name and result[field_name] is None:
                result[field_name] = getattr(announcement, "message", None)

        return result

    def _build_queue_state(
        self, queue_state: Any | None
    ) -> BoardStateQueueState:
        if not queue_state:
            return BoardStateQueueState()

        values = self._extract_queue_state_values(queue_state)

        return BoardStateQueueState(
            department=values.get("department"),
            date_str=values.get("date_str"),
            last_ticket=values.get("last_ticket"),
            waiting=values.get("waiting"),
            serving=values.get("serving"),
            done=values.get("done"),
        )

    def _extract_queue_state_values(self, queue_state: Any) -> dict[str, Any]:
        if isinstance(queue_state, Mapping):
            return dict(queue_state)

        snapshot = getattr(queue_state, "snapshot", queue_state)
        return {
            "department": getattr(snapshot, "department", None),
            "date_str": getattr(snapshot, "date_str", None),
            "last_ticket": getattr(snapshot, "last_ticket", None),
            "waiting": getattr(snapshot, "waiting", None),
            "serving": getattr(snapshot, "serving", None),
            "done": getattr(snapshot, "done", None),
        }

    def _build_compatibility_fields(
        self, compatibility_fields: Mapping[str, Any] | None
    ) -> BoardStateCompatibilityFields:
        if not compatibility_fields:
            return BoardStateCompatibilityFields()

        return BoardStateCompatibilityFields(
            is_open=compatibility_fields.get("is_open"),
            start_number=compatibility_fields.get("start_number"),
        )

    def _coerce_str_setting(
        self,
        value: Any,
        *,
        fallback: Any = None,
    ) -> str | None:
        for candidate in (value, fallback):
            if candidate is None:
                continue
            if isinstance(candidate, str):
                normalized = candidate.strip()
                if normalized:
                    return normalized
            else:
                return str(candidate)
        return None

    def _coerce_bool_setting(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return bool(value)

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None
