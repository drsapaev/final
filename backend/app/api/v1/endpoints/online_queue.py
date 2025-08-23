import logging
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles

log = logging.getLogger("api.online_queue")

# Делаем алиасы под /api/v1/online-queue/*
router = APIRouter(prefix="/online-queue", tags=["online-queue"])


@router.post("/open", name="online_queue_open")
def open_day_alias(
    department: str = Query(..., description="Код отделения, напр. ENT"),
    date_str: str = Query(..., description="Дата в формате YYYY-MM-DD"),
    start_number: int = Query(1, ge=0, description="Стартовый номер талона"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Reception")),
):
    """
    Алиас для /api/v1/appointments/open — принимает параметры в query.
    """
    from app.api.v1.endpoints.appointments import open_day as impl_open_day

    return impl_open_day(
        department=department,
        date_str=date_str,
        start_number=start_number,
        db=db,
        current_user=current_user,
    )


@router.get("/stats", name="online_queue_stats")
def stats_alias(
    department: str = Query(..., description="Код отделения, напр. ENT"),
    date_str: str = Query(..., description="Дата в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Reception", "Doctor")),
):
    """
    Алиас для /api/v1/appointments/stats — параметры тоже в query.
    """
    from app.api.v1.endpoints.appointments import stats as impl_stats

    return impl_stats(
        department=department,
        date_str=date_str,
        db=db,
        current_user=current_user,
    )


@router.get("/qrcode", name="online_queue_qrcode")
def qrcode_alias(
    department: str = Query(..., description="Код отделения, напр. ENT"),
    date_str: str = Query(..., description="Дата в формате YYYY-MM-DD"),
    size: int = Query(512, ge=64, le=1024, description="Размер PNG"),
    margin: int = Query(1, ge=0, le=10, description="Отступ от края"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Reception")),
) -> Response:
    """
    Алиас для /api/v1/appointments/qrcode — возвращает PNG.
    """
    from app.api.v1.endpoints.appointments import qrcode_png as impl_qrcode

    return impl_qrcode(
        department=department,
        date_str=date_str,
        size=size,
        margin=margin,
        db=db,
        current_user=current_user,
    )
