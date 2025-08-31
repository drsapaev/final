from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import schedule as crud
from app.schemas.schedule import ScheduleCreateIn, ScheduleRowOut
from app.models.user import User

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _to_out(r) -> ScheduleRowOut:
    return ScheduleRowOut(
        id=r.id,
        department=r.department,
        doctor_id=r.doctor_id,
        weekday=int(r.weekday),
        start_time=str(r.start_time),
        end_time=str(r.end_time),
        room=r.room,
        capacity_per_hour=r.capacity_per_hour,
        active=bool(r.active),
    )


@router.get("", response_model=List[ScheduleRowOut], summary="Список расписаний")
async def list_templates(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: Optional[str] = Query(default=None, max_length=64),
    doctor_id: Optional[int] = Query(default=None, ge=1),
    weekday: Optional[int] = Query(default=None, ge=0, le=6),
    active: Optional[bool] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows = crud.list_schedules(
        db,
        department=department,
        doctor_id=doctor_id,
        weekday=weekday,
        active=active,
        limit=limit,
        offset=offset,
    )
    return [_to_out(r) for r in rows]


@router.post("", response_model=ScheduleRowOut, summary="Создать расписание")
async def create_template(
    payload: ScheduleCreateIn,
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin")),
):
    row = crud.create_schedule(
        db,
        department=payload.department,
        doctor_id=payload.doctor_id,
        weekday=payload.weekday,
        start_time=payload.start_time,
        end_time=payload.end_time,
        room=payload.room,
        capacity_per_hour=payload.capacity_per_hour,
        active=payload.active,
    )
    return row


@router.delete("/{id}", summary="Удалить расписание")
async def delete_template(
    id: int = Path(..., ge=1),
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin")),
):
    ok = crud.delete_schedule(db, id_=id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# Новые endpoints для интеграции с панелью регистратора

@router.get("/weekly", summary="Расписание на неделю")
async def get_weekly_schedule(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: Optional[str] = Query(default=None, description="Отделение"),
    doctor_id: Optional[int] = Query(default=None, description="ID врача"),
    week_start: Optional[str] = Query(default=None, description="Начало недели (YYYY-MM-DD)"),
):
    """
    Получить расписание на неделю с возможностью фильтрации по отделению или врачу
    """
    if week_start:
        try:
            start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")
    else:
        # Если дата не указана, берем начало текущей недели (понедельник)
        today = date.today()
        start_date = today - timedelta(days=today.weekday())
    
    weekly_schedule = crud.get_weekly_schedule(
        db, 
        start_date=start_date,
        department=department,
        doctor_id=doctor_id
    )
    return weekly_schedule


@router.get("/daily", summary="Расписание на день")
async def get_daily_schedule(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(default=None, description="Отделение"),
    doctor_id: Optional[int] = Query(default=None, description="ID врача"),
):
    """
    Получить расписание на конкретный день
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")
    
    daily_schedule = crud.get_daily_schedule(
        db,
        target_date=target_date,
        department=department,
        doctor_id=doctor_id
    )
    return daily_schedule


@router.get("/available-slots", summary="Доступные слоты для записи")
async def get_available_slots(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
    department: str = Query(..., description="Отделение"),
    doctor_id: Optional[int] = Query(default=None, description="ID врача"),
):
    """
    Получить доступные слоты времени для записи на конкретную дату
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")
    
    available_slots = crud.get_available_slots(
        db,
        target_date=target_date,
        department=department,
        doctor_id=doctor_id
    )
    return available_slots


@router.get("/doctors", summary="Список врачей по отделениям")
async def get_doctors_by_department(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: Optional[str] = Query(default=None, description="Отделение"),
):
    """
    Получить список врачей, сгруппированных по отделениям
    """
    doctors = crud.get_doctors_by_department(db, department=department)
    return doctors


@router.get("/departments", summary="Список отделений")
async def get_departments(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить список всех отделений с расписанием
    """
    departments = crud.get_departments(db)
    return departments