"""
Regression (SLA alert flapping): p95/error-rate alerts fired on tiny
windows — at clinic opening (07:41), at night (02:30) and minutes after a
restart, a handful of cold requests dragged p95 over the threshold and
paged Sentry with a "breach" that was sampling noise (PYTHON-FASTAPI-A/9/8,
three same-class spikes). Both ratio alerts are now suppressed until the
window holds at least SlaThresholds.alert_min_samples requests.
"""

from app.core import observability as obs
from app.core.observability import ObservabilityState, SlaThresholds


class _AlertRecorder:
    def __init__(self):
        self.created = []

    def create_alert(self, alert_type, severity, message, details=None):
        self.created.append((alert_type, message))
        return type("A", (), {"message": message})()


def _state(min_samples: int = 20) -> ObservabilityState:
    return ObservabilityState(
        SlaThresholds(
            latency_p95_ms=100.0,
            error_rate_pct=5.0,
            queue_lag_max=50,
            window_seconds=300,
            alert_min_samples=min_samples,
        )
    )


def _record(state, n, duration_ms, status_code=200):
    for _ in range(n):
        state.record_request(
            method="GET", path="/x", status_code=status_code, duration_ms=duration_ms
        )


def test_latency_alert_suppressed_below_min_samples(monkeypatch):
    rec = _AlertRecorder()
    monkeypatch.setattr(obs, "alert_manager", rec)
    state = _state(min_samples=20)

    _record(state, 5, duration_ms=30_000)  # p95 way over 100ms, but n=5
    alerts = state.evaluate_sla_alerts()

    assert "latency" not in alerts
    assert rec.created == []


def test_error_rate_alert_suppressed_below_min_samples(monkeypatch):
    rec = _AlertRecorder()
    monkeypatch.setattr(obs, "alert_manager", rec)
    state = _state(min_samples=20)

    _record(state, 3, duration_ms=1, status_code=500)  # 100% errors, but n=3
    alerts = state.evaluate_sla_alerts()

    assert "error_rate" not in alerts
    assert rec.created == []


def test_latency_alert_fires_above_min_samples(monkeypatch):
    rec = _AlertRecorder()
    monkeypatch.setattr(obs, "alert_manager", rec)
    state = _state(min_samples=20)

    _record(state, 25, duration_ms=30_000)
    alerts = state.evaluate_sla_alerts()

    assert "latency" in alerts
    assert rec.created, "alert must be created above the sample floor"


def test_healthy_window_never_alerts(monkeypatch):
    rec = _AlertRecorder()
    monkeypatch.setattr(obs, "alert_manager", rec)
    state = _state(min_samples=20)

    _record(state, 25, duration_ms=10)
    alerts = state.evaluate_sla_alerts()

    assert alerts == {}
    assert rec.created == []
