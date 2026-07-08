# --- BEGIN app/api/v1/endpoints/queues.py ---
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.online_queue import DayStats, issue_next_ticket, load_stats

from typing import Any
router = APIRouter(tags=["queues"])


@router.get("/stats", response_model=dict[str, Any])
def stats(
    department: str,
    d: str | None = Query(None),
    date: str | None = Query(None),
    db: Session = Depends(get_db),
    # QUEUE-AUDIT-28 P0-3: was public — leaked queue stats to anonymous
    _current_user=Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    date_str = d or date
    if not date_str:
        raise HTTPException(
            status_code=422, detail="Query param 'd' or 'date' is required"
        )
    s: DayStats = load_stats(db, department=department, date_str=date_str)
    return asdict(s)


@router.post("/next-ticket", response_model=dict[str, Any])
def next_ticket(
    department: str,
    d: str | None = Query(None),
    date: str | None = Query(None),
    db: Session = Depends(get_db),
    _current_user=Depends(require_roles("Admin", "Registrar")),
):
    date_str = d or date
    if not date_str:
        raise HTTPException(
            status_code=422, detail="Query param 'd' or 'date' is required"
        )
    ticket, s = issue_next_ticket(db, department=department, date_str=date_str)
    return {"ticket": ticket, "stats": asdict(s)}


# --- END app/api/v1/endpoints/queues.py ---
