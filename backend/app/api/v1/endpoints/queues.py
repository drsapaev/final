from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.online_queue import load_stats, issue_next_ticket, DayStats

router = APIRouter(prefix="/queues", tags=["queues"])


class StatsOut(BaseModel):
    department: str
    date_str: str
    is_open: bool
    start_number: int | None = None
    last_ticket: int
    waiting: int
    serving: int
    done: int


@router.get("/stats", response_model=StatsOut, summary="Статистика дневной очереди")
async def stats(
    department: str = Query(..., min_length=1, max_length=64),
    d: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")),
):
    s: DayStats = load_stats(db, department=department, date_str=d)
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


class NextTicketOut(BaseModel):
    ticket: int
    stats: StatsOut


@router.post("/next-ticket", response_model=NextTicketOut, summary="Выдать следующий талон")
async def next_ticket(
    department: str = Query(..., min_length=1, max_length=64),
    d: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar")),
):
    ticket, s = issue_next_ticket(db, department=department, date_str=d)
    return NextTicketOut(
        ticket=ticket,
        stats=StatsOut(
            department=s.department,
            date_str=s.date_str,
            is_open=s.is_open,
            start_number=s.start_number,
            last_ticket=s.last_ticket,
            waiting=s.waiting,
            serving=s.serving,
            done=s.done,
        ),
    )