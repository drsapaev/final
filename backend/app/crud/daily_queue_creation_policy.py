"""Canonical policy and start-number snapshot for newly created day queues."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from app.crud.queue_resource_routing import effective_day_start_number
from app.models.clinic import Doctor
from app.models.online_queue import QueueResource

LEGACY_POLICY_VERSION = "legacy"
ONLINE_ISSUANCES_V1_POLICY_VERSION = "daily_online_issuances_v1"
_V2_CREATION_FLAG = "QUEUE_POLICY_V2_CREATION_ENABLED"
_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


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
    flag_value = os.getenv(_V2_CREATION_FLAG, "").strip().lower()
    policy_version = (
        ONLINE_ISSUANCES_V1_POLICY_VERSION
        if flag_value in _TRUTHY_VALUES
        else LEGACY_POLICY_VERSION
    )

    return {
        "policy_version": policy_version,
        "online_issued_count": 0,
        "start_number": effective_day_start_number(
            db,
            doctor=doctor,
            resource=resource,
            queue_tag=queue_tag,
            settings=settings,
        ),
    }
