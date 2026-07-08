from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.online_queue import load_stats

from typing import Any
router = APIRouter(prefix="/board", tags=["board"])


@router.get("/state", summary="Состояние очереди для табло", response_model=dict[str, Any])
def board_state(
    department: str = Query(..., min_length=1, max_length=64),
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    # QUEUE-AUDIT-28 P0-3: was public — leaked live queue state to anonymous
    _current_user=Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Return the legacy board stats snapshot.

    Live display rows, current calls, and announcements are owned by the
    display board WebSocket initial_state/update stream.
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
