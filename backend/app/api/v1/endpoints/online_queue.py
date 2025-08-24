# app/api/v1/endpoints/online_queue.py
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles

# важно: алиасы дергают реализацию из appointments,
# а не тянут что-то из services напрямую — так мы избегаем конфликтов сигнатур
from app.api.v1.endpoints import appointments as impl

router = APIRouter(prefix="/online-queue", tags=["online-queue"])


@router.post("/open", name="online_queue_open", dependencies=[Depends(require_roles("Admin"))])
def open_day_alias(
    department: str = Query(...),
    date_str: str = Query(...),
    start_number: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # проксируем 1-в-1 к “родной” ручке
    return impl.open_day(
        department=department,
        date_str=date_str,
        start_number=start_number,
        db=db,
        current_user=current_user,
    )


@router.get("/stats", name="online_queue_stats")
def stats_alias(
    department: str = Query(...),
    date_str: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    d: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # appointments.stats умеет принимать date_str/date/d — передаём как есть
    return impl.stats(
        department=department,
        date_str=date_str,
        date=date,
        d=d,
        db=db,
        current_user=current_user,
    )


@router.get("/qrcode", name="online_queue_qrcode")
def qrcode_alias(
    department: str = Query(...),
    date_str: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    d: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    return impl.qrcode_png(
        department=department,
        date_str=date_str,
        date=date,
        d=d,
        current_user=current_user,
    )
