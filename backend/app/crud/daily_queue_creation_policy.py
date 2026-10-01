"""Canonical policy and start-number snapshot for newly created day queues."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import time
from typing import Any

from sqlalchemy.orm import Session

from app.crud.queue_resource_routing import effective_day_start_number
from app.models.clinic import Doctor
from app.models.online_queue import QueueResource

LEGACY_POLICY_VERSION = "legacy"
ONLINE_ISSUANCES_V1_POLICY_VERSION = "daily_online_issuances_v1"
_V2_CREATION_FLAG = "QUEUE_POLICY_V2_CREATION_ENABLED"
_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})
_HH_MM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class OnlineAdmissionWindow:
    """The effective same-day admission window for one queue policy."""

    policy_version: str
    start_time: time
    end_time: time | None


def policy_version_for_new_queue() -> str:
    """Select the policy for a future DailyQueue using the creation flag."""
    flag_value = os.getenv(_V2_CREATION_FLAG, "").strip().lower()
    return (
        ONLINE_ISSUANCES_V1_POLICY_VERSION
        if flag_value in _TRUTHY_VALUES
        else LEGACY_POLICY_VERSION
    )


def parse_hhmm(value: Any, *, field_name: str) -> time:
    """Parse the persisted/admin contract's strict 24-hour ``HH:MM`` form."""
    if not isinstance(value, str) or not _HH_MM.fullmatch(value):
        raise ValueError(f"{field_name} must use HH:MM format")
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour, minute)


def _queue_start_time(settings: dict[str, Any]) -> time:
    raw_hour = settings.get("queue_start_hour", 7)
    if isinstance(raw_hour, bool):
        raise ValueError("queue_start_hour must be an hour from 0 to 23")
    try:
        hour = int(raw_hour)
    except (TypeError, ValueError) as exc:
        raise ValueError("queue_start_hour must be an hour from 0 to 23") from exc
    if not 0 <= hour <= 23 or str(raw_hour).strip() not in {str(hour), f"{hour:02d}"}:
        raise ValueError("queue_start_hour must be an hour from 0 to 23")
    return time(hour, 0)


def online_window_for_settings(
    settings: dict[str, Any], *, policy_version: str
) -> tuple[time, time | None]:
    """Return a queue's creation-time window without reading/changing a row.

    Legacy rows keep the previous start-hour gate and do not acquire a new
    admission cutoff. V1 rows freeze the configured ``auto_close_time`` and
    reject overnight or empty intervals.
    """
    start_time = _queue_start_time(settings)
    if policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION:
        end_time = parse_hhmm(
            settings.get("auto_close_time", "09:00"), field_name="auto_close_time"
        )
        if end_time <= start_time:
            raise ValueError("auto_close_time must be later than queue_start_hour")
        return start_time, end_time
    if policy_version != LEGACY_POLICY_VERSION:
        raise ValueError("unsupported daily queue policy version")
    return start_time, None


def online_admission_window(
    *, daily_queue: Any | None, settings: dict[str, Any]
) -> OnlineAdmissionWindow:
    """Resolve the policy/window used by both availability and admission.

    Existing v1 rows use immutable day fields. A rowless read calculates the
    same policy that a subsequent constructor will select. Legacy rows keep
    their existing policy and only retain the configured start check.
    """
    policy_version = (
        getattr(daily_queue, "policy_version", LEGACY_POLICY_VERSION)
        if daily_queue is not None
        else policy_version_for_new_queue()
    )
    if daily_queue is not None and policy_version == ONLINE_ISSUANCES_V1_POLICY_VERSION:
        start_time = parse_hhmm(
            daily_queue.online_start_time, field_name="online_start_time"
        )
        end_time = parse_hhmm(
            daily_queue.online_end_time, field_name="online_end_time"
        )
        if end_time <= start_time:
            raise ValueError("daily queue online end time must be later than start time")
    else:
        start_time, end_time = online_window_for_settings(
            settings, policy_version=policy_version
        )
    return OnlineAdmissionWindow(policy_version, start_time, end_time)


def evaluate_online_admission_window(day, now, window: OnlineAdmissionWindow) -> str:
    """Return the same-day window result; future dates keep legacy behavior."""
    if day < now.date():
        return "date_past"
    if day > now.date():
        return "available"
    current_time = now.timetz().replace(tzinfo=None)
    if current_time < window.start_time:
        return "before_start"
    if window.end_time is not None and current_time >= window.end_time:
        return "after_end"
    return "available"


def daily_queue_creation_snapshot(
    db: Session,
    *,
    doctor: Doctor | None = None,
    resource: QueueResource | None = None,
    queue_tag: str | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, str | int]:
    """Return policy metadata and the canonical start-number snapshot.

    The environment flag selects a policy only for a queue being created.
    Existing rows never pass through this function when reused. Callers in a
    queue-service command pass its settings snapshot so nested creation uses
    the same clinic defaults as the rest of that command.
    """
    if settings is None:
        from app.crud.clinic import get_queue_settings

        settings = get_queue_settings(db) or {}
    policy_version = policy_version_for_new_queue()
    start_time, end_time = online_window_for_settings(
        settings, policy_version=policy_version
    )
    if end_time is None:
        # Preserve the historical service-opening snapshot for legacy rows;
        # this field is not a legacy admission cutoff.
        raw_end_hour = settings.get("queue_end_hour", 9)
        try:
            legacy_end_hour = int(raw_end_hour)
        except (TypeError, ValueError):
            legacy_end_hour = 9
        if not 0 <= legacy_end_hour <= 23:
            legacy_end_hour = 9
        stored_end_time = f"{legacy_end_hour:02d}:00"
    else:
        stored_end_time = end_time.strftime("%H:%M")

    return {
        "policy_version": policy_version,
        "online_issued_count": 0,
        "online_start_time": start_time.strftime("%H:%M"),
        "online_end_time": stored_end_time,
        "start_number": effective_day_start_number(
            db,
            doctor=doctor,
            resource=resource,
            queue_tag=queue_tag,
            settings=settings,
        ),
    }
