"""Core mixin for NotificationPlatformService.

Split from notification_platform_service.py.
"""
from __future__ import annotations

from app.services.notification_platform._base import *  # noqa: F401, F403
from app.services.notification_platform._base import NotificationPlatformServiceMixinBase


class CoreMixin(NotificationPlatformServiceMixinBase):
    """Core methods."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = NotificationPlatformRepository(db)
        self.ws_manager = get_notification_ws_manager()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------


    def normalize_event_type(self, event_type: str | None) -> str:
        value = self.normalize_slug(event_type) or "notification"
        return self.LEGACY_EVENT_TYPE_ALIASES.get(value, value)


    def normalize_role(self, role: str | None) -> str | None:
        normalized = self.normalize_slug(role)
        if not normalized:
            return None
        return self.ROLE_ALIASES.get(normalized, normalized)


    def normalize_department_key(self, department_key: str | None) -> str | None:
        normalized = self.normalize_slug(department_key)
        if not normalized:
            return None
        return self.DEPARTMENT_ROLE_ALIASES.get(normalized, normalized)

    @staticmethod


    def normalize_slug(value: str | None) -> str | None:
        if value is None:
            return None
        text = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
        text = re.sub(r"_+", "_", text).strip("_")
        return text or None

    @staticmethod


    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod


    def _parse_hhmm(value: str | None, fallback: tuple[int, int]) -> tuple[int, int]:
        if not value:
            return fallback
        try:
            hour, minute = str(value).split(":", maxsplit=1)
            parsed_hour = max(0, min(23, int(hour)))
            parsed_minute = max(0, min(59, int(minute)))
            return parsed_hour, parsed_minute
        except (TypeError, ValueError):
            return fallback


    def _resolve_timezone_name_for_user(self, user: User) -> str:
        user_preferences = getattr(user, "preferences", None)
        user_profile = getattr(user, "profile", None)
        candidate = (
            getattr(user_preferences, "timezone", None)
            or getattr(user_profile, "timezone", None)
            or self.DEFAULT_TIMEZONE
        )
        try:
            ZoneInfo(candidate)
            return candidate
        except Exception:
            return self.DEFAULT_TIMEZONE


    def _is_within_quiet_hours(self, *, now_local: datetime, start: str | None, end: str | None) -> bool:
        start_h, start_m = self._parse_hhmm(start, (22, 0))
        end_h, end_m = self._parse_hhmm(end, (8, 0))
        now_minutes = now_local.hour * 60 + now_local.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        if start_minutes == end_minutes:
            return False
        if start_minutes < end_minutes:
            return start_minutes <= now_minutes < end_minutes
        return now_minutes >= start_minutes or now_minutes < end_minutes


    def _parse_policy_datetime(
        self,
        *,
        value: Any,
        timezone_name: str,
    ) -> datetime | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        target_tz = ZoneInfo(timezone_name)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=target_tz)
        return parsed.astimezone(target_tz)


