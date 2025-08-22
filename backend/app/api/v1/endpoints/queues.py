# --- BEGIN app/api/v1/endpoints/queues.py ---
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.online_queue import load_stats, issue_next_ticket, DayStats

router = APIRouter(tags=["queues"])

@router.get("/stats")
def stats(
    department: str,
    d: str | None = Query(None),
    date: str | None = Query(None),
    db: Session = Depends(get_db),
):
    date_str = d or date
    if not date_str:
        raise HTTPException(status_code=422, detail="Query param 'd' or 'date' is required")
    s: DayStats = load_stats(db, department=department, date_str=date_str)
    return asdict(s)

@router.post("/next-ticket")
def next_ticket(
    department: str,
    d: str | None = Query(None),
    date: str | None = Query(None),
    db: Session = Depends(get_db),
):
    date_str = d or date
    if not date_str:
        raise HTTPException(status_code=422, detail="Query param 'd' or 'date' is required")
    ticket, s = issue_next_ticket(db, department=department, date_str=date_str)
    return {"ticket": ticket, "stats": asdict(s)}
# --- END app/api/v1/endpoints/queues.py ---
