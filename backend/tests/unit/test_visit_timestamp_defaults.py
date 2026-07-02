from __future__ import annotations

from datetime import timezone

from app.models.visit import Visit


def test_visit_created_at_default_is_timezone_aware_utc() -> None:
    default_factory = Visit.__table__.c.created_at.default.arg

    created_at = default_factory(None)

    assert created_at.tzinfo is not None
    assert created_at.utcoffset() == timezone.utc.utcoffset(created_at)
