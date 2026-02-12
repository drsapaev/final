"""Application observability state and SLA alert evaluation."""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.alerts import AlertSeverity, AlertType, alert_manager
from app.core.config import settings
from app.models.online_queue import OnlineQueueEntry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlaThresholds:
    """SLA thresholds used for runtime alerting."""

    latency_p95_ms: float
    error_rate_pct: float
    queue_lag_max: int
    window_seconds: int


class ObservabilityState:
    """In-memory request metrics and SLA checks."""

    def __init__(self, thresholds: SlaThresholds) -> None:
        self.thresholds = thresholds
        self._lock = threading.Lock()
        self._request_total = 0
        self._error_total = 0
        self._duration_sum_ms = 0.0
        self._queue_lag = 0
        self._queue_lag_updated_at = 0.0
        self._window: deque[tuple[float, float, bool]] = deque()
        self._status_counters: Counter[str] = Counter()
        self._endpoint_counters: Counter[tuple[str, str, str]] = Counter()
        self._last_sla_eval_at = 0.0
        self._sla_eval_interval_seconds = 10.0

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: float) -> float:
        if not sorted_values:
            return 0.0
        if len(sorted_values) == 1:
            return float(sorted_values[0])
        rank = (percentile / 100.0) * (len(sorted_values) - 1)
        low = math.floor(rank)
        high = math.ceil(rank)
        if low == high:
            return float(sorted_values[low])
        low_value = sorted_values[low]
        high_value = sorted_values[high]
        return float(low_value + (high_value - low_value) * (rank - low))

    def _prune_window(self, now: float) -> None:
        cutoff = now - self.thresholds.window_seconds
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

    def record_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        now = time.time()
        with self._lock:
            is_error = status_code >= 500
            self._request_total += 1
            if is_error:
                self._error_total += 1
            self._duration_sum_ms += duration_ms
            self._window.append((now, duration_ms, is_error))
            self._prune_window(now)
            status_bucket = f"{status_code // 100}xx"
            self._status_counters[status_bucket] += 1
            self._endpoint_counters[(method, path, str(status_code))] += 1

    def set_queue_lag(self, queue_lag: int) -> None:
        now = time.time()
        with self._lock:
            self._queue_lag = max(queue_lag, 0)
            self._queue_lag_updated_at = now

    def get_queue_lag(self) -> int:
        with self._lock:
            return self._queue_lag

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._prune_window(now)
            durations = sorted(item[1] for item in self._window)
            window_count = len(self._window)
            window_errors = sum(1 for _, _, is_error in self._window if is_error)
            error_rate_pct = (
                (window_errors / window_count) * 100.0 if window_count else 0.0
            )
            p95 = self._percentile(durations, 95.0)
            p99 = self._percentile(durations, 99.0)
            avg_duration = (
                self._duration_sum_ms / self._request_total
                if self._request_total
                else 0.0
            )
            return {
                "totals": {
                    "requests": self._request_total,
                    "errors": self._error_total,
                    "avg_duration_ms": round(avg_duration, 2),
                },
                "window": {
                    "seconds": self.thresholds.window_seconds,
                    "requests": window_count,
                    "errors": window_errors,
                    "error_rate_pct": round(error_rate_pct, 2),
                    "latency_p95_ms": round(p95, 2),
                    "latency_p99_ms": round(p99, 2),
                },
                "queue_lag": {
                    "value": self._queue_lag,
                    "updated_at_unix": self._queue_lag_updated_at,
                },
                "thresholds": {
                    "latency_p95_ms": self.thresholds.latency_p95_ms,
                    "error_rate_pct": self.thresholds.error_rate_pct,
                    "queue_lag_max": self.thresholds.queue_lag_max,
                },
                "status_codes": dict(self._status_counters),
            }

    def evaluate_sla_alerts(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            if now - self._last_sla_eval_at < self._sla_eval_interval_seconds:
                return {}
            self._last_sla_eval_at = now

        snapshot = self.snapshot()
        window = snapshot["window"]
        queue_lag_value = snapshot["queue_lag"]["value"]
        alerts: dict[str, Any] = {}

        error_rate = float(window["error_rate_pct"])
        if error_rate > self.thresholds.error_rate_pct:
            severity = (
                AlertSeverity.CRITICAL
                if error_rate > self.thresholds.error_rate_pct * 1.5
                else AlertSeverity.WARNING
            )
            alert = alert_manager.create_alert(
                AlertType.HIGH_ERROR_RATE,
                severity,
                (
                    f"SLA breach: error rate {error_rate:.2f}% "
                    f"(threshold {self.thresholds.error_rate_pct:.2f}%)"
                ),
                details={
                    "error_rate_pct": error_rate,
                    "window_seconds": self.thresholds.window_seconds,
                },
            )
            if alert:
                alerts["error_rate"] = alert.message

        p95_latency = float(window["latency_p95_ms"])
        if p95_latency > self.thresholds.latency_p95_ms:
            severity = (
                AlertSeverity.CRITICAL
                if p95_latency > self.thresholds.latency_p95_ms * 1.5
                else AlertSeverity.WARNING
            )
            alert = alert_manager.create_alert(
                AlertType.SYSTEM_RESOURCE,
                severity,
                (
                    f"SLA breach: p95 latency {p95_latency:.2f}ms "
                    f"(threshold {self.thresholds.latency_p95_ms:.2f}ms)"
                ),
                details={
                    "latency_p95_ms": p95_latency,
                    "window_seconds": self.thresholds.window_seconds,
                },
            )
            if alert:
                alerts["latency"] = alert.message

        if queue_lag_value > self.thresholds.queue_lag_max:
            severity = (
                AlertSeverity.CRITICAL
                if queue_lag_value > self.thresholds.queue_lag_max * 2
                else AlertSeverity.WARNING
            )
            alert = alert_manager.create_alert(
                AlertType.QUEUE_ERROR,
                severity,
                (
                    f"SLA breach: queue lag {queue_lag_value} "
                    f"(threshold {self.thresholds.queue_lag_max})"
                ),
                details={
                    "queue_lag": queue_lag_value,
                    "threshold": self.thresholds.queue_lag_max,
                },
            )
            if alert:
                alerts["queue_lag"] = alert.message

        if alerts:
            logger.warning("SLA alerts triggered: %s", alerts)
        return alerts

    def collect_queue_lag(self, db: Session) -> int:
        queue_lag = (
            db.query(func.count(OnlineQueueEntry.id))
            .filter(OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]))
            .scalar()
            or 0
        )
        self.set_queue_lag(int(queue_lag))
        return int(queue_lag)

    def prometheus_metrics(self) -> str:
        snapshot = self.snapshot()
        totals = snapshot["totals"]
        window = snapshot["window"]
        queue_lag = snapshot["queue_lag"]["value"]
        thresholds = snapshot["thresholds"]
        lines = [
            "# HELP clinic_http_requests_total Total HTTP requests",
            "# TYPE clinic_http_requests_total counter",
            f"clinic_http_requests_total {totals['requests']}",
            "# HELP clinic_http_errors_total Total HTTP 5xx responses",
            "# TYPE clinic_http_errors_total counter",
            f"clinic_http_errors_total {totals['errors']}",
            "# HELP clinic_http_request_duration_ms_avg Average HTTP latency in ms",
            "# TYPE clinic_http_request_duration_ms_avg gauge",
            f"clinic_http_request_duration_ms_avg {totals['avg_duration_ms']}",
            "# HELP clinic_http_request_latency_p95_ms Rolling p95 latency in ms",
            "# TYPE clinic_http_request_latency_p95_ms gauge",
            f"clinic_http_request_latency_p95_ms {window['latency_p95_ms']}",
            "# HELP clinic_http_error_rate_percent Rolling error rate in percent",
            "# TYPE clinic_http_error_rate_percent gauge",
            f"clinic_http_error_rate_percent {window['error_rate_pct']}",
            "# HELP clinic_queue_lag Current queue lag (waiting+called+in_service)",
            "# TYPE clinic_queue_lag gauge",
            f"clinic_queue_lag {queue_lag}",
            "# HELP clinic_sla_latency_p95_threshold_ms SLA threshold for p95 latency",
            "# TYPE clinic_sla_latency_p95_threshold_ms gauge",
            f"clinic_sla_latency_p95_threshold_ms {thresholds['latency_p95_ms']}",
            "# HELP clinic_sla_error_rate_threshold_percent SLA threshold for error rate",
            "# TYPE clinic_sla_error_rate_threshold_percent gauge",
            f"clinic_sla_error_rate_threshold_percent {thresholds['error_rate_pct']}",
            "# HELP clinic_sla_queue_lag_threshold SLA threshold for queue lag",
            "# TYPE clinic_sla_queue_lag_threshold gauge",
            f"clinic_sla_queue_lag_threshold {thresholds['queue_lag_max']}",
        ]

        for (method, path, status), count in self._endpoint_counters.items():
            safe_path = path.replace('"', "'")
            lines.append(

                    'clinic_http_requests_by_endpoint_total'
                    f'{{method="{method}",path="{safe_path}",status="{status}"}} {count}'

            )
        return "\n".join(lines) + "\n"


observability_state = ObservabilityState(
    thresholds=SlaThresholds(
        latency_p95_ms=float(getattr(settings, "OBS_SLA_LATENCY_P95_MS", 1200.0)),
        error_rate_pct=float(getattr(settings, "OBS_SLA_ERROR_RATE_PCT", 5.0)),
        queue_lag_max=int(getattr(settings, "OBS_SLA_QUEUE_LAG_MAX", 50)),
        window_seconds=int(getattr(settings, "OBS_SLA_WINDOW_SECONDS", 300)),
    )
)
