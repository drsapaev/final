# app/api/v1/endpoints/online_queue.py
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.services.online_queue import load_stats  # есть в services
import app.api.v1.endpoints.appointments as impl

router = APIRouter(prefix="/online-queue", tags=["online-queue"])

# Аккуратно берём модель Setting (название файла/класса может отличаться)
def _get_setting_model():
    try:
        from app.models.setting import Setting  # type: ignore
        return Setting
    except Exception:
        from app.models.settings import Setting  # type: ignore
        return Setting

Setting = _get_setting_model()


@router.post("/open", dependencies=[Depends(require_roles("Admin"))])
def open_day_alias(
    department: str = Query(...),
    date_str: str = Query(...),
    start_number: int = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # проксируем на appointments.open с теми же именами параметров
    return impl.open_day(
        department=department,
        date_str=date_str,
        start_number=start_number,
        db=db,
        current_user=current_user,
    )

@router.get("/stats")
def stats_alias(
    department: str = Query(...),
    date_str: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return impl.stats(
        department=department,
        d=date_str,          # ВНИМАНИЕ: если stats ожидает параметр 'd', передаём его так
        db=db,
        current_user=current_user,
    )

@router.get("/qrcode", name="online_queue_qrcode")
def online_queue_qrcode(
    department: str = Query(...),
    date_str: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Алиас генерации QR — прокидываем в существующий обработчик из appointments.
    Если там другое имя параметра даты (например, date вместо date_str) — поменяйте ниже.
    """
    from app.api.v1.endpoints.appointments import qrcode_png  # импортим локально, чтобы избежать циклов
    return qrcode_png(department=department, date_str=date_str, db=db, current_user=current_user)
