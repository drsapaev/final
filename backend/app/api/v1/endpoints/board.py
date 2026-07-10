from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.online_queue import load_stats

router = APIRouter(prefix="/board", tags=["board"])


@router.get("/state", summary="Состояние очереди для табло", response_model=dict[str, Any])
def board_state(
    department: str = Query(..., min_length=1, max_length=64),
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Return the legacy board stats snapshot.

    The board state endpoint is intentionally public: it only exposes
    aggregate counters (``last_ticket``/``waiting``/``serving``/``done``)
    and the day's open/start-number flags. It must NOT leak live queue
    entries, current calls, or announcements — those are owned by the
    display board WebSocket initial_state/update stream, which is
    separately authenticated. Keeping this REST endpoint public lets the
    stats-only contract be verified without auth headers.
    """
    s = load_stats(db, department=department, date_str=date)
    return {
        "department": s.department,
        "date_str": s.date_str,
        "is_open": s.is_open,
        "start_number": s.start_number,
        "last_ticket": s.last_ticket,
        "waiting": s.waiting,
        "serving": s.serving,
        "done": s.done,
    }
