"""
Regression: Alert.timestamp defaulted to naive datetime.utcnow(), while
get_recent_alerts()/cooldown logic compare with aware datetime.now(UTC) —
so /api/v1/observability/sla raised
"can't compare offset-naive and offset-aware datetimes" (500) whenever at
least one alert existed in memory. The SLA guardrail went blind exactly
when it had something to report. Timestamps are now aware UTC.
"""

from app.core.alerts import (
    AlertManager,
    AlertSeverity,
    AlertType,
)


def test_created_alert_has_aware_timestamp_and_is_findable():
    manager = AlertManager()
    alert = manager.create_alert(
        AlertType.SYSTEM_RESOURCE,
        AlertSeverity.WARNING,
        "SLA breach: p95 latency test",
    )
    assert alert is not None
    assert alert.timestamp.tzinfo is not None

    # Pre-fix this raised: naive vs aware comparison in get_recent_alerts
    recent = manager.get_recent_alerts(24)
    assert len(recent) == 1
    assert recent[0].message == "SLA breach: p95 latency test"

    stats = manager.get_alert_stats()
    assert stats["recent_24h"] == 1
    assert stats["total_alerts"] == 1
