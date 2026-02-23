"""Service layer for appointments endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.crud.appointment import appointment as appointment_crud
from app.models.setting import Setting
from app.repositories.appointments_api_repository import AppointmentsApiRepository
from app.schemas import appointment as appointment_schemas


class AppointmentsApiService:
    """Builds payloads for appointments API endpoints."""

    def __init__(
        self,
        db: Session,
        repository: AppointmentsApiRepository | None = None,
    ):
        self.repository = repository or AppointmentsApiRepository(db)

    def list_appointments(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        doctor_id: int | None,
        department: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict[str, Any]]:
        appointments = self.repository.list_appointments(
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            doctor_id=doctor_id,
            department=department,
            date_from=date_from,
            date_to=date_to,
        )

        result = []
        for apt in appointments:
            patient_name = None
            if apt.patient_id:
                patient = self.repository.get_patient_by_id(apt.patient_id)
                patient_name = patient.short_name() if patient else f"Пациент #{apt.patient_id}"

            services_with_names = []
            if apt.services and isinstance(apt.services, list):
                for service_item in apt.services:
                    if isinstance(service_item, str):
                        service = self.repository.get_service_by_code(service_item)
                        services_with_names.append(service.name if service else service_item)
                    elif isinstance(service_item, dict):
                        if "name" in service_item:
                            services_with_names.append(service_item["name"])
                        elif "code" in service_item:
                            service = self.repository.get_service_by_code(service_item["code"])
                            services_with_names.append(
                                service.name if service else service_item.get("code", "Услуга")
                            )
                        else:
                            services_with_names.append(str(service_item))
                    else:
                        services_with_names.append(str(service_item))

            apt_dict = appointment_schemas.Appointment.model_validate(apt).model_dump()
            apt_dict["patient_name"] = patient_name
            if services_with_names:
                apt_dict["services"] = services_with_names
            result.append(apt_dict)

        return result

    def upsert_queue_setting(self, *, key: str, value: str) -> None:
        now = datetime.utcnow()
        row = self.repository.get_queue_setting(key=key)
        if row:
            row.value = value
            row.updated_at = now
            return
        row = Setting(category="queue", key=key, value=value, created_at=now, updated_at=now)
        self.repository.add(row)

    def commit(self) -> None:
        self.repository.commit()

    def get_pending_payments(
        self,
        *,
        skip: int,
        limit: int,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict[str, Any]]:
        from collections import defaultdict

        result = []

        from_date = None
        to_date = None

        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            except ValueError:
                pass

        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
            except ValueError:
                pass

        appointments = self.repository.list_pending_appointments(date_from=from_date, date_to=to_date)

        for apt in appointments:
            if apt.payment_amount and apt.status == "paid":
                continue

            patient_name = None
            patient_last_name = None
            patient_first_name = None
            if apt.patient_id:
                patient = self.repository.get_patient_by_id(apt.patient_id)
                if patient:
                    patient_name = patient.short_name()
                    patient_last_name = patient.last_name
                    patient_first_name = patient.first_name
                else:
                    patient_name = f"Пациент #{apt.patient_id}"

            services_codes: list[str] = []
            services_names: list[str] = []
            if apt.services and isinstance(apt.services, list):
                for service_item in apt.services:
                    if isinstance(service_item, str):
                        service = self.repository.get_service_by_code(service_item)
                        if service:
                            service_code = (
                                self.repository.get_mapped_service_code(service.id)
                                or service.code
                                or service_item
                            )
                            services_codes.append(service_code)
                            services_names.append(service.name)
                        else:
                            services_codes.append(service_item)
                            services_names.append(service_item)
                    elif isinstance(service_item, dict):
                        code = (
                            service_item.get("code")
                            or service_item.get("service_code")
                            or str(service_item)
                        )
                        if "name" in service_item:
                            services_codes.append(code)
                            services_names.append(service_item["name"])
                        elif "code" in service_item:
                            service = self.repository.get_service_by_code(service_item["code"])
                            if service:
                                service_code = (
                                    self.repository.get_mapped_service_code(service.id)
                                    or service.code
                                    or service_item["code"]
                                )
                                services_codes.append(service_code)
                                services_names.append(service.name)
                            else:
                                services_codes.append(code)
                                services_names.append(code)
                        else:
                            services_codes.append(str(service_item))
                            services_names.append(str(service_item))
                    else:
                        services_codes.append(str(service_item))
                        services_names.append(str(service_item))

            result.append(
                {
                    "id": int(apt.id),
                    "patient_id": int(apt.patient_id) if apt.patient_id else None,
                    "patient_name": str(patient_name) if patient_name else None,
                    "patient_last_name": str(patient_last_name) if patient_last_name else None,
                    "patient_first_name": str(patient_first_name) if patient_first_name else None,
                    "doctor_id": int(apt.doctor_id) if apt.doctor_id else None,
                    "department": str(apt.department) if apt.department else None,
                    "appointment_date": apt.appointment_date.isoformat() if apt.appointment_date else None,
                    "appointment_time": str(apt.appointment_time) if apt.appointment_time else None,
                    "status": str(apt.status),
                    "services": [str(s) for s in services_codes] if services_codes else [],
                    "services_names": [str(s) for s in services_names] if services_names else [],
                    "payment_amount": float(apt.payment_amount) if apt.payment_amount else None,
                    "created_at": apt.created_at.isoformat() if apt.created_at else None,
                    "record_type": "appointment",
                    "visit_ids": [],
                }
            )

        visits = self.repository.list_visits_for_pending_payments(
            date_from=from_date,
            date_to=to_date,
        )
        visits_by_patient = defaultdict(
            lambda: {
                "visits": [],
                "patient_id": None,
                "patient_name": None,
                "patient_last_name": None,
                "patient_first_name": None,
                "visit_date": None,
                "created_at": None,
                "services_codes": [],
                "services_names": [],
                "total_amount": 0,
                "visit_ids": [],
            }
        )

        for visit in visits:
            if self.repository.has_paid_invoice_for_visit(visit.id):
                continue

            visit_date = visit.visit_date or (visit.created_at.date() if visit.created_at else None)
            group_key = (visit.patient_id, visit_date.isoformat() if visit_date else None)

            if group_key not in visits_by_patient:
                patient_name = None
                patient_last_name = None
                patient_first_name = None
                if visit.patient_id:
                    patient = self.repository.get_patient_by_id(visit.patient_id)
                    if patient:
                        patient_name = patient.short_name()
                        patient_last_name = patient.last_name
                        patient_first_name = patient.first_name
                    else:
                        patient_name = f"Пациент #{visit.patient_id}"

                visits_by_patient[group_key] = {
                    "visits": [],
                    "patient_id": visit.patient_id,
                    "patient_name": patient_name,
                    "patient_last_name": patient_last_name,
                    "patient_first_name": patient_first_name,
                    "visit_date": visit_date,
                    "created_at": visit.created_at,
                    "services_codes": [],
                    "services_names": [],
                    "total_amount": 0,
                    "visit_ids": [],
                }

            visits_by_patient[group_key]["visits"].append(visit)
            visits_by_patient[group_key]["visit_ids"].append(visit.id)
            if visit.created_at and (
                not visits_by_patient[group_key]["created_at"]
                or visit.created_at < visits_by_patient[group_key]["created_at"]
            ):
                visits_by_patient[group_key]["created_at"] = visit.created_at

        for group_data in visits_by_patient.values():
            all_services_codes = []
            all_services_names = []
            total_amount = 0

            for visit in group_data["visits"]:
                visit_services = self.repository.list_visit_services(visit.id)
                for vs in visit_services:
                    service_code = vs.code
                    if not service_code:
                        service = self.repository.get_service_by_id(vs.service_id)
                        if service:
                            service_code = (
                                self.repository.get_mapped_service_code(vs.service_id)
                                or service.code
                                or f"S{vs.service_id}"
                            )
                    service_name = vs.name
                    if not service_name:
                        service = self.repository.get_service_by_id(vs.service_id)
                        service_name = service.name if service else f"Услуга #{vs.service_id}"

                    if service_code not in all_services_codes:
                        all_services_codes.append(service_code or f"S{vs.service_id}")
                        all_services_names.append(service_name)
                    if vs.price:
                        total_amount += float(vs.price) * vs.qty

            if not group_data["visit_ids"]:
                continue

            result.append(
                {
                    "id": int(min(group_data["visit_ids"]) + 20000),
                    "patient_id": int(group_data["patient_id"]) if group_data["patient_id"] else None,
                    "patient_name": str(group_data["patient_name"]) if group_data["patient_name"] else None,
                    "patient_last_name": str(group_data["patient_last_name"]) if group_data["patient_last_name"] else None,
                    "patient_first_name": str(group_data["patient_first_name"]) if group_data["patient_first_name"] else None,
                    "doctor_id": None,
                    "department": None,
                    "appointment_date": group_data["visit_date"].isoformat() if group_data["visit_date"] else None,
                    "appointment_time": None,
                    "status": "pending",
                    "services": [str(s) for s in all_services_codes] if all_services_codes else [],
                    "services_names": [str(s) for s in all_services_names] if all_services_names else [],
                    "payment_amount": float(total_amount) if total_amount > 0 else None,
                    "created_at": group_data["created_at"].isoformat() if group_data["created_at"] else None,
                    "record_type": "visit",
                    "visit_ids": [int(v) for v in group_data["visit_ids"]] if group_data["visit_ids"] else [],
                }
            )

        result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        paginated_result = result[skip : skip + limit]
        json_result = []
        for item in paginated_result:
            json_item = {}
            for key, value in item.items():
                if value is None or isinstance(value, (str, int, float, bool)):
                    json_item[key] = value
                elif isinstance(value, list):
                    json_item[key] = [
                        str(v) if not isinstance(v, (str, int, float, bool)) else v
                        for v in value
                    ]
                else:
                    json_item[key] = str(value)
            json_result.append(json_item)
        return json_result

# --- API Router moved from app/api/v1/endpoints/appointments.py ---

"""Appointments API endpoints."""


import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.appointment import appointment as appointment_crud
from app.models.user import User
from app.schemas import appointment as appointment_schemas
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

