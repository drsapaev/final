from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import schedule as crud
from app.schemas.schedule import ScheduleCreateIn, ScheduleRowOut  # type: ignore[attr-defined]

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
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor")),
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
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
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
    return _to_out(row)


@router.delete("/{id}", summary="Удалить расписание")
async def delete_template(
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    ok = crud.delete_schedule(db, id_=id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}