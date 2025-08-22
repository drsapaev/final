# --- BEGIN app/api/v1/endpoints/online_queue.py ---
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.online_queue import load_stats, open_day

router = APIRouter()


def _stats_to_dict(s) -> dict:
    # Унифицированный ответ со всеми ключами
    return {
        "department": getattr(s, "department", None),
        "date_str": getattr(s, "date_str", None),
        "is_open": getattr(s, "is_open", False),
        "start_number": getattr(s, "start_number", 0),
        "last_ticket": getattr(s, "last_ticket", 0),
        "waiting": getattr(s, "waiting", 0),
        "serving": getattr(s, "serving", 0),
        "done": getattr(s, "done", 0),
    }


@router.post("/open", name="online_queue_open")
def open_queue(
    department: str = Query(..., min_length=1),
    date_str: str = Query(..., min_length=8),
    start_number: int = Query(1, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_roles("Admin", "Registrar")),
):
    """
    Открыть онлайн-очередь на день. Все параметры — в query string.
    """
    s = open_day(db, department=department, date_str=date_str, start_number=start_number)
    # Ответ в формате, как ты уже видел в консоли
    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "start_number": start_number,
        "is_open": getattr(s, "is_open", True),
    }


@router.get("/stats", name="online_queue_stats")
def stats(
    department: str = Query(..., min_length=1),
    date_str: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
    _=Depends(require_roles("Admin", "Registrar")),
):
    """
    Статистика онлайн-очереди (вариант с параметром date_str).
    """
    s = load_stats(db, department=department, date_str=date_str)
    return _stats_to_dict(s)
# --- END app/api/v1/endpoints/online_queue.py ---
