from __future__ import annotations

"""Legacy board read model for the OnlineDay compatibility island."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.online_queue import load_stats

router = APIRouter(prefix="/board", tags=["board"])


class BoardLegacyStateResponse(BaseModel):
    department: str
    date_str: str
    is_open: bool
    start_number: int
    last_ticket: int
    waiting: int
    serving: int
    done: int


@router.get(
    "/state",
    response_model=BoardLegacyStateResponse,
    summary="Legacy board state compatibility route",
    deprecated=True,
)
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
