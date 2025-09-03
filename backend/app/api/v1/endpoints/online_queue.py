# app/api/v1/endpoints/online_queue.py
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
# важно: алиасы дергают реализацию из appointments,
# а не тянут что-то из services напрямую — так мы избегаем конфликтов сигнатур
from app.api.v1.endpoints import appointments as impl
from app.schemas.online import OnlineJoinRequest, OnlineJoinResponse
from app.services.online_queue import (can_issue_more_today,
                                       get_existing_ticket_for_identity,
                                       is_within_morning_window,
                                       issue_next_ticket,
                                       remember_identity_ticket)

router = APIRouter(prefix="/online-queue", tags=["online-queue"])


@router.post(
    "/open", name="online_queue_open", dependencies=[Depends(require_roles("Admin"))]
)
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


@router.post(
    "/close", name="online_queue_close", dependencies=[Depends(require_roles("Admin"))]
)
def close_alias(
    department: str = Query(...),
    date_str: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    d: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    eff_date = date_str or date or d
    return impl.close_day(
        department=department,
        date_str=eff_date,
        db=db,
        current_user=current_user,
    )


@router.post("/join", response_model=OnlineJoinResponse, name="online_queue_join")
def join_online_queue(
    payload: OnlineJoinRequest,
    db: Session = Depends(get_db),
):
    dep = payload.department.strip()
    d = payload.date.isoformat()

    # Окно времени
    if not is_within_morning_window(db=db, department=dep, date_str=d):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="online window is closed"
        )

    # Лимит на день
    if not can_issue_more_today(db=db, department=dep, date_str=d):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="daily limit reached"
        )

    # Дубликаты по телефону/Telegram: возвращаем прежний номер
    if payload.phone or payload.tg_id:
        if (
            old := get_existing_ticket_for_identity(
                db=db,
                department=dep,
                date_str=d,
                phone=payload.phone,
                tg_id=payload.tg_id,
            )
        ) is not None:
            return OnlineJoinResponse(
                queue_entry_id=0,
                ticket_number=int(old),
                department=dep,
                date=payload.date,
            )

    ticket, _stats = issue_next_ticket(db, department=dep, date_str=d)
    remember_identity_ticket(
        db=db,
        department=dep,
        date_str=d,
        phone=payload.phone,
        tg_id=payload.tg_id,
        ticket=ticket,
    )
    return OnlineJoinResponse(
        queue_entry_id=0,
        ticket_number=int(ticket),
        department=dep,
        date=payload.date,
    )
