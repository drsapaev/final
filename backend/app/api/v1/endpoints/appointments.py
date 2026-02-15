"""Appointments API endpoints."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.appointment import appointment as appointment_crud
from app.models.user import User
from app.schemas import appointment as appointment_schemas
from app.services.appointments_api_service import AppointmentsApiService
from app.services.online_queue import _broadcast, get_or_create_day, load_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/appointments", tags=["appointments"])


class PendingPaymentResponse(BaseModel):
    id: int
    patient_id: Optional[int]
    patient_name: Optional[str]
    patient_last_name: Optional[str]
    patient_first_name: Optional[str]
    doctor_id: Optional[int]
    department: Optional[str]
    appointment_date: Optional[str]
    appointment_time: Optional[str]
    status: str
    services: list[str]
    services_names: list[str]
    payment_amount: Optional[float]
    created_at: Optional[str]
    record_type: str
    visit_ids: Optional[list[int]] = None


def _pick_date(date_str: Optional[str], date: Optional[str], d: Optional[str]) -> str:
    value = date_str or date or d
    if not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date is required (use ?date_str=YYYY-MM-DD or ?date=... or ?d=...)",
        )
    return value


def _service(db: Session) -> AppointmentsApiService:
    return AppointmentsApiService(db)


@router.get("/", response_model=List[appointment_schemas.Appointment])
def list_appointments(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None, description="Patient id filter"),
    doctor_id: Optional[int] = Query(None, description="Doctor id filter"),
    department: Optional[str] = Query(None, description="Department filter"),
    date_from: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    return _service(db).list_appointments(
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department=department,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/", response_model=appointment_schemas.Appointment)
def create_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_in: appointment_schemas.AppointmentCreate,
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    if appointment_crud.is_time_slot_occupied(
        db,
        doctor_id=appointment_in.doctor_id,
        appointment_date=appointment_in.appointment_date,
        appointment_time=appointment_in.appointment_time,
    ):
        raise HTTPException(
            status_code=400,
            detail="This time slot is already occupied for selected doctor",
        )
    return appointment_crud.create(db=db, obj_in=appointment_in)


@router.get("/pending-payments", response_model=list[PendingPaymentResponse])
async def get_pending_payments(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    try:
        return _service(db).get_pending_payments(
            skip=skip,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:  # pragma: no cover - defensive API guard
        logger.error("Error in get_pending_payments: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while loading pending payments: {exc}",
        ) from exc


@router.get("/{appointment_id}", response_model=appointment_schemas.Appointment)
def get_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    appointment = appointment_crud.get_appointment(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.put("/{appointment_id}", response_model=appointment_schemas.Appointment)
def update_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    appointment_in: appointment_schemas.AppointmentUpdate,
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    appointment = appointment_crud.get_appointment(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if (
        appointment_in.appointment_date
        or appointment_in.appointment_time
        or appointment_in.doctor_id
    ):
        new_date = appointment_in.appointment_date or appointment.appointment_date
        new_time = appointment_in.appointment_time or appointment.appointment_time
        new_doctor_id = appointment_in.doctor_id or appointment.doctor_id
        if appointment_crud.is_time_slot_occupied(
            db,
            doctor_id=new_doctor_id,
            appointment_date=new_date,
            appointment_time=new_time,
            exclude_appointment_id=appointment_id,
        ):
            raise HTTPException(
                status_code=400,
                detail="This time slot is already occupied for selected doctor",
            )

    return appointment_crud.update_appointment(db=db, db_obj=appointment, obj_in=appointment_in)


@router.delete("/{appointment_id}")
def delete_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    appointment = appointment_crud.get_appointment(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment_crud.delete_appointment(db=db, id=appointment_id)
    return {"message": "Appointment canceled successfully"}


@router.get("/doctor/{doctor_id}/schedule")
def get_doctor_schedule(
    *,
    db: Session = Depends(deps.get_db),
    doctor_id: int,
    date: str = Query(..., description="Date (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    return appointment_crud.get_doctor_schedule(db, doctor_id=doctor_id, date=date)


@router.get("/department/{department}/schedule")
def get_department_schedule(
    *,
    db: Session = Depends(deps.get_db),
    department: str,
    date: str = Query(..., description="Date (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    return appointment_crud.get_department_schedule(db, department=department, date=date)


@router.post(
    "/open-day",
    name="open_day",
    dependencies=[Depends(deps.require_roles("Admin"))],
)
def open_day(
    department: str = Query(..., description="Department"),
    date_str: str = Query(..., description="YYYY-MM-DD"),
    start_number: int = Query(..., ge=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    key_prefix = f"{department}::{date_str}"
    service = _service(db)
    service.upsert_queue_setting(key=f"{key_prefix}::open", value="1")
    service.upsert_queue_setting(key=f"{key_prefix}::start_number", value=str(start_number))
    service.commit()

    stats = load_stats(db, department=department, date_str=date_str)
    try:
        _broadcast(department, date_str, stats)
    except Exception as exc:  # pragma: no cover - websocket side effect
        logger.warning("Broadcast error in open_day: %s", exc, exc_info=True)

    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "start_number": start_number,
        "is_open": True,
        "last_ticket": getattr(stats, "last_ticket", None),
        "waiting": getattr(stats, "waiting", None),
        "serving": getattr(stats, "serving", None),
        "done": getattr(stats, "done", None),
    }


@router.get("/stats", name="stats")
def stats(
    department: str = Query(...),
    date_str: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    d: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    effective_date = _pick_date(date_str, date, d)
    day_stats = load_stats(db, department=department, date_str=effective_date)
    return {
        "department": department,
        "date_str": effective_date,
        "is_open": getattr(day_stats, "is_open", False),
        "start_number": getattr(day_stats, "start_number", 0),
        "last_ticket": getattr(day_stats, "last_ticket", 0),
        "waiting": getattr(day_stats, "waiting", 0),
        "serving": getattr(day_stats, "serving", 0),
        "done": getattr(day_stats, "done", 0),
    }


@router.post(
    "/close",
    name="close_day",
    dependencies=[Depends(deps.require_roles("Admin"))],
)
def close_day(
    department: str = Query(..., description="Department"),
    date_str: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    get_or_create_day(db, department=department, date_str=date_str, open_flag=False)
    _service(db).commit()
    day_stats = load_stats(db, department=department, date_str=date_str)
    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "is_open": day_stats.is_open,
        "start_number": day_stats.start_number,
        "last_ticket": day_stats.last_ticket,
        "waiting": day_stats.waiting,
        "serving": day_stats.serving,
        "done": day_stats.done,
    }


@router.get("/qrcode", name="qrcode_png")
def qrcode_png(
    department: str = Query(...),
    date_str: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    d: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_user),
):
    del current_user
    effective_date = _pick_date(date_str, date, d)
    return {"format": "text", "data": f"{department}::{effective_date}"}
