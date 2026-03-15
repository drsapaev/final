from __future__ import annotations

import pytest

from app.services.queue_status import (
    DUPLICATE_ACTIVE_RAW_STATUSES,
    POSITION_VISIBLE_RAW_STATUSES,
    QUEUE_STATUS_ALIASES,
    REORDER_ACTIVE_RAW_STATUSES,
    normalize_queue_status,
)


@pytest.mark.unit
def test_normalize_queue_status_maps_known_aliases() -> None:
    assert normalize_queue_status("canceled") == "cancelled"
    assert normalize_queue_status("in_progress") == "in_service"
    assert normalize_queue_status("completed") == "served"
    assert normalize_queue_status("waiting") == "waiting"


@pytest.mark.unit
def test_status_groups_preserve_phase1_runtime_behavior() -> None:
    assert DUPLICATE_ACTIVE_RAW_STATUSES == ("waiting", "called")
    assert REORDER_ACTIVE_RAW_STATUSES == ("waiting", "called")
    assert POSITION_VISIBLE_RAW_STATUSES == (
        "waiting",
        "called",
        "in_service",
        "diagnostics",
    )
    assert QUEUE_STATUS_ALIASES["canceled"] == "cancelled"
