# --- BEGIN app/api/v1/endpoints/queues.py ---
"""Legacy queue-counter endpoints backed by the OnlineDay island."""

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.queue_stats_parity_harness import build_replacement_queues_stats
from app.services.online_queue import issue_next_ticket

router = APIRouter(tags=["queues"])


@router.get("/stats")
def stats(
    department: str,
    d: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    date_str = d or date
    if not date_str:
        raise HTTPException(
            status_code=422, detail="Query param 'd' or 'date' is required"
        )
    # Keep legacy compatibility fields while moving consumer-visible counters to SSOT.
    result = build_replacement_queues_stats(
        db, department=department, date_str=date_str
    )
    return asdict(result.snapshot)


@router.post("/next-ticket")
def next_ticket(
    department: str,
    d: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    date_str = d or date
    if not date_str:
        raise HTTPException(
            status_code=422, detail="Query param 'd' or 'date' is required"
        )
    ticket, s = issue_next_ticket(db, department=department, date_str=date_str)
    return {"ticket": ticket, "stats": asdict(s)}


# --- END app/api/v1/endpoints/queues.py ---
