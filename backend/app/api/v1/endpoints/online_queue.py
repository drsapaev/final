from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.online_queue import DayStats, get_or_create_day, load_stats

router = APIRouter(prefix="/online-queue", tags=["online-queue"])


class OpenOut(BaseModel):
    ok: bool
    department: str
    date_str: str
    start_number: Optional[int] = None
    is_open: bool


@router.post("/open", response_model=OpenOut, summary="Открыть день онлайн-очереди (alias)")
async def open_online_day(
    department: str = Query(..., min_length=1, max_length=64),
    date_str: str = Query(..., min_length=8, max_length=16),
    start_number: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar")),
):
    row = get_or_create_day(db, department=department.strip(), date_str=date_str.strip(), start_number=start_number, open_flag=True)
    return OpenOut(
        ok=True,
        department=row.department,
        date_str=row.date_str,
        start_number=row.start_number,
        is_open=row.is_open,
    )


class StatsOut(BaseModel):
    department: str
    date_str: str
    is_open: bool
    start_number: Optional[int] = None
    last_ticket: int
    waiting: int
    serving: int
    done: int


@router.get("/stats", response_model=StatsOut, summary="Статус онлайн-очереди (alias /appointments/stats)")
async def online_stats(
    department: str = Query(..., min_length=1, max_length=64),
    date_str: str = Query(..., min_length=8, max_length=16),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")),
):
    s: DayStats = load_stats(db, department=department.strip(), date_str=date_str.strip())
    return StatsOut(
        department=s.department,
        date_str=s.date_str,
        is_open=s.is_open,
        start_number=s.start_number,
        last_ticket=s.last_ticket,
        waiting=s.waiting,
        serving=s.serving,
        done=s.done,
    )