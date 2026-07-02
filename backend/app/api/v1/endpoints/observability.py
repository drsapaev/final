"""Observability endpoints for metrics, traces and SLA snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.alerts import alert_manager
from app.core.observability import observability_state
from app.db.session import get_db

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/sla", dependencies=[Depends(deps.require_roles("Admin"))])
def get_sla_snapshot(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Return current SLA snapshot and trigger SLA alerts check.

    Includes:
    - latency/error SLI window
    - current queue lag
    - current active alert stats
    """
    queue_lag = observability_state.collect_queue_lag(db)
    triggered_alerts = observability_state.evaluate_sla_alerts()
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "queue_lag": queue_lag,
        "snapshot": observability_state.snapshot(),
        "triggered_alerts": triggered_alerts,
        "alert_stats": alert_manager.get_alert_stats(),
    }


@router.get("/alerts", dependencies=[Depends(deps.require_roles("Admin"))])
def get_observability_alerts(hours: int = 24) -> dict[str, Any]:
    """Return recent alerts emitted by SLA guardrails."""
    alerts = alert_manager.get_recent_alerts(hours=hours)
    return {
        "hours": hours,
        "count": len(alerts),
        "alerts": [
            {
                "type": alert.alert_type.value,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "details": alert.details,
            }
            for alert in alerts
        ],
    }


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def get_prometheus_metrics(db: Session = Depends(get_db)) -> PlainTextResponse:
    """
    Prometheus-style metrics endpoint.

    Exposed without auth to simplify Prometheus scrape in local/dev setup.
    """
    observability_state.collect_queue_lag(db)
    observability_state.evaluate_sla_alerts()
    payload = observability_state.prometheus_metrics()
    return PlainTextResponse(
        content=payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
