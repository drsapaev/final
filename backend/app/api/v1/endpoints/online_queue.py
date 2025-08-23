# app/api/v1/endpoints/online_queue.py
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_roles
from app.services.online_queue import load_stats  # есть в services

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


@router.post("/open", name="online_queue_open")
def online_queue_open(
    department: str = Query(..., description="Напр. ENT"),
    date_str: str = Query(..., description="YYYY-MM-DD"),
    start_number: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["Admin"])),
):
    """
    Алиас открытия дня для онлайн-очереди.
    Просто апсертит настройки:
      queue::{dep}::{date}::is_open = 1
      queue::{dep}::{date}::start_number = <start_number>
    """
    prefix = f"{department}::{date_str}"
    now = datetime.utcnow()

    def upsert(key: str, value: str | int):
        rec = db.query(Setting).filter_by(category="queue", key=key).first()
        if rec:
            rec.value = str(value)
            rec.updated_at = now
        else:
            rec = Setting(
                category="queue",
                key=key,
                value=str(value),
                created_at=now,
                updated_at=now,
            )
            db.add(rec)

    upsert(f"{prefix}::is_open", "1")
    upsert(f"{prefix}::start_number", start_number)

    db.commit()
    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "start_number": start_number,
        "is_open": True,
    }


@router.get("/stats", name="online_queue_stats")
def online_queue_stats(
    department: str = Query(...),
    date_str: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Алиас статистики для онлайн-очереди, использует services.online_queue.load_stats()."""
    s = load_stats(db, department=department, date_str=date_str)
    # Поддержим разные типы (pydantic v2 / v1 / dataclass)
    for attr in ("model_dump", "dict"):
        fn = getattr(s, attr, None)
        if callable(fn):
            return fn()
    return s  # на крайний случай


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
