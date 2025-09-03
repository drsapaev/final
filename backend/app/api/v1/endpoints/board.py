from __future__ import annotations


from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.online_queue import load_stats

router = APIRouter(prefix="/board", tags=["board"])


@router.get("/state", summary="Состояние очереди для табло")
def board_state(
    department: str = Query(..., min_length=1, max_length=64),
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
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
