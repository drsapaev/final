"""setup/status latency instrumentation (no behavior change).

The production p95 for GET /api/v1/setup/status was 15.7s against an
8s threshold (Sentry PYTHON-FASTAPI-A/9/8) while warm local probes sit
at 1.2-1.6s. Before any cache decision, this module instruments the
endpoint to answer WHY: how many SQL statements run per request, how
much wall time the database owns vs application processing, and whether
a given request was cold (first call in the process) or warm.

Every request logs one INFO line:
    setup_status_profile: duration_ms=... sql_count=... db_time_ms=...
        app_time_ms=... cold=true|false

Read-only: adds no SQL, no writes, no caching, and does not alter the
response. Remove the profile wrapper once the latency incident is
resolved.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar

from fastapi import APIRouter, Depends
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.session import engine as _app_engine
from app.schemas.setup import SetupInitializeIn, SetupInitializeOut, SetupStatusOut
from app.services.setup_service import SetupService

router = APIRouter(prefix="/setup", tags=["setup"])

logger = logging.getLogger(__name__)

# Per-request SQL stats, active only while the instrumented handler runs.
# The listeners are registered ONCE on the application engine and check the
# ContextVar, so concurrent requests on the shared engine stay isolated.
_sql_stats: ContextVar[dict | None] = ContextVar("setup_status_sql_stats", default=None)


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    stats = _sql_stats.get()
    if stats is not None:
        stats["_t0"] = time.perf_counter()


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    stats = _sql_stats.get()
    if stats is None:
        return
    started = stats.pop("_t0", None)
    if started is not None:
        stats["count"] = stats.get("count", 0) + 1
        stats["db_time"] = stats.get("db_time", 0.0) + (time.perf_counter() - started)


event.listen(_app_engine, "before_cursor_execute", _before_cursor_execute)
event.listen(_app_engine, "after_cursor_execute", _after_cursor_execute)

_first_call_seen = False


@router.get("/status", response_model=SetupStatusOut, summary="Minimal setup state")
def get_setup_status(db: Session = Depends(get_db)):
    global _first_call_seen

    stats: dict = {"count": 0, "db_time": 0.0}
    _sql_stats.set(stats)
    started = time.perf_counter()
    try:
        result = SetupService(db).get_status()
    finally:
        duration = time.perf_counter() - started
        _sql_stats.set(None)
        cold = not _first_call_seen
        _first_call_seen = True
        logger.info(
            "setup_status_profile: duration_ms=%d sql_count=%d db_time_ms=%d "
            "app_time_ms=%d cold=%s",
            round(duration * 1000),
            stats.get("count", 0),
            round(stats.get("db_time", 0.0) * 1000),
            round(max(0.0, duration - stats.get("db_time", 0.0)) * 1000),
            cold,
        )
    return result


@router.post(
    "/initialize",
    response_model=SetupInitializeOut,
    summary="Initialize clinic deployment from first-run setup",
)
def initialize_setup(body: SetupInitializeIn, db: Session = Depends(get_db)):
    return SetupService(db).initialize(body)
