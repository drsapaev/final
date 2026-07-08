"""
Prometheus metrics integration for the clinic backend.

Exposes a /metrics endpoint compatible with Prometheus scraping.
Metrics are collected automatically by the prometheus_client library
plus custom clinic-specific metrics.

Usage:
    # In app/main.py:
    from app.core.prometheus import init_prometheus
    init_prometheus(app)

    # Prometheus scrapes GET /metrics
    # Add prometheus-client to requirements (already in requirements-monitoring.txt)

Custom metrics exposed:
    - clinic_http_requests_total{method, path, status} — request counter
    - clinic_http_request_duration_seconds{method, path} — request latency histogram
    - clinic_visits_total{status} — visit counter by status
    - clinic_queue_length{department} — current queue length
    - clinic_ai_requests_total{provider, task_type} — AI API call counter
    - clinic_ai_request_duration_seconds{provider} — AI API call latency
    - clinic_active_websocket_connections — current WS connections
    - clinic_db_pool_connections — DB pool size (if available)

Standard metrics from prometheus_client:
    - process_virtual_memory_bytes
    - process_resident_memory_bytes
    - process_start_time_seconds
    - process_cpu_seconds_total
    - python_info
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# Flag to avoid double-init
_prometheus_initialized = False

# Custom metrics (defined at module level so they persist across requests)
if os.getenv("ENABLE_PROMETHEUS", "1").lower() in ("1", "true", "yes", "on"):
    try:
        from prometheus_client import (
                CONTENT_TYPE_LATEST,  # noqa: F401,
                REGISTRY,  # noqa: F401,
                CollectorRegistry,  # noqa: F401,
            Counter,
            Gauge,
            Histogram,
            Info,
                generate_latest,  # noqa: F401,
            make_asgi_app,
        )

        # HTTP request metrics
        http_requests_total = Counter(
            "clinic_http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status"],
        )

        http_request_duration = Histogram(
            "clinic_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "path"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        # Business metrics
        visits_total = Counter(
            "clinic_visits_total",
            "Total visits created/updated",
            ["status"],
        )

        queue_length = Gauge(
            "clinic_queue_length",
            "Current queue length per department",
            ["department"],
        )

        # AI metrics
        ai_requests_total = Counter(
            "clinic_ai_requests_total",
            "Total AI API calls",
            ["provider", "task_type"],
        )

        ai_request_duration = Histogram(
            "clinic_ai_request_duration_seconds",
            "AI API call duration in seconds",
            ["provider"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )

        # WebSocket metrics
        active_websocket_connections = Gauge(
            "clinic_active_websocket_connections",
            "Current active WebSocket connections",
        )

        # App info
        app_info = Info(
            "clinic",
            "Clinic application info",
        )

        _PROMETHEUS_AVAILABLE = True
        logger.info("[prometheus] metrics initialized (ENABLE_PROMETHEUS=1)")

    except ImportError:
        _PROMETHEUS_AVAILABLE = False
        logger.warning(
            "[prometheus] prometheus-client not installed. "
            "Run: pip install -r backend/requirements-monitoring.txt"
        )
else:
    _PROMETHEUS_AVAILABLE = False
    logger.info("[prometheus] disabled (ENABLE_PROMETHEUS != 1)")


def init_prometheus(app: Any) -> None:
    """Initialize Prometheus metrics + mount /metrics endpoint on FastAPI app.

    Call this once from app/main.py after app creation.

    Args:
        app: FastAPI app instance
    """
    global _prometheus_initialized
    if _prometheus_initialized:
        return

    if not _PROMETHEUS_AVAILABLE:
        logger.info("[prometheus] skipping init — prometheus-client not available")
        return

    import os

    # Mount Prometheus ASGI app at /metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Set app info
    app_info.info({
        "version": os.getenv("APP_VERSION", "0.9.0"),
        "env": os.getenv("ENV", "dev"),
    })

    # Add middleware to track HTTP requests
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
        """Middleware that records HTTP request count + duration."""

        async def dispatch(self, request: Request, call_next):
            # Skip /metrics endpoint itself (avoid recursive counting)
            if request.url.path == "/metrics":
                return await call_next(request)

            start_time = time.time()
            method = request.method
            # Normalize path to avoid cardinality explosion
            # /api/v1/patients/123 → /api/v1/patients/:id
            path = _normalize_path(request.url.path)

            try:
                response = await call_next(request)
                status = str(response.status_code)
            except Exception:
                status = "500"
                raise
            finally:
                duration = time.time() - start_time
                http_requests_total.labels(method=method, path=path, status=status).inc()
                http_request_duration.labels(method=method, path=path).observe(duration)

            return response

    app.add_middleware(PrometheusMetricsMiddleware)

    _prometheus_initialized = True
    logger.info("[prometheus] /metrics endpoint mounted + middleware added")


def _normalize_path(path: str) -> str:
    """Normalize URL path to reduce cardinality.

    /api/v1/patients/123 → /api/v1/patients/:id
    /api/v1/visits/456/emr → /api/v1/visits/:id/emr
    """
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        # If part is numeric or UUID-like, replace with :id
        if part.isdigit() or (len(part) == 36 and part.count("-") == 4):
            normalized.append(":id")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


# Convenience functions for business code to record metrics
def record_visit(status: str) -> None:
    """Record a visit creation/update."""
    if _PROMETHEUS_AVAILABLE:
        visits_total.labels(status=status).inc()


def set_queue_length(department: str, length: int) -> None:
    """Update current queue length for a department."""
    if _PROMETHEUS_AVAILABLE:
        queue_length.labels(department=department).set(length)


def record_ai_request(provider: str, task_type: str, duration_seconds: float) -> None:
    """Record an AI API call."""
    if _PROMETHEUS_AVAILABLE:
        ai_requests_total.labels(provider=provider, task_type=task_type).inc()
        ai_request_duration.labels(provider=provider).observe(duration_seconds)


def increment_websocket_connections() -> None:
    """Call when a new WebSocket connects."""
    if _PROMETHEUS_AVAILABLE:
        active_websocket_connections.inc()


def decrement_websocket_connections() -> None:
    """Call when a WebSocket disconnects."""
    if _PROMETHEUS_AVAILABLE:
        active_websocket_connections.dec()
