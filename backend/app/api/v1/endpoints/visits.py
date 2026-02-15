# app/api/v1/endpoints/visits.py
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.visits_api_service import VisitsApiService

router = APIRouter()


class VisitCreate(BaseModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    notes: Optional[str] = None
    planned_date: Optional[date] = None


class VisitOut(BaseModel):
    id: int
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    notes: Optional[str] = None
    planned_date: Optional[date] = None


class VisitServiceIn(BaseModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitWithServices(BaseModel):
    visit: VisitOut
    services: List[VisitServiceIn]


@router.get("/visits", response_model=List[VisitOut], summary="Список визитов")
def list_visits(
    patient_id: Optional[int] = Query(default=None),
    doctor_id: Optional[int] = Query(default=None),
    status_q: Optional[str] = Query(default=None),
    planned: Optional[date] = Query(default=None, alias="planned_date"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = VisitsApiService(db).list_visits(
        patient_id=patient_id,
        doctor_id=doctor_id,
        status_q=status_q,
        planned=planned,
        limit=limit,
        offset=offset,
    )
    return [VisitOut(**row) for row in rows]


@router.post(
    "/visits",
    response_model=VisitOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("Admin", "Registrar", "Doctor"))],
    summary="Создать визит",
)
def create_visit(
    request: Request,
    payload: VisitCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    result = VisitsApiService(db).create_visit(
        request=request,
        payload=payload,
        current_user=current_user,
    )
    return VisitOut(**result)


@router.get("/visits/{visit_id}", response_model=VisitWithServices, summary="Карточка визита")
def get_visit(visit_id: int, db: Session = Depends(get_db)):
    payload = VisitsApiService(db).get_visit(visit_id=visit_id)
    return VisitWithServices(
        visit=VisitOut(**payload["visit"]),
        services=[VisitServiceIn(**item) for item in payload["services"]],
    )


@router.post(
    "/visits/{visit_id}/services",
    dependencies=[Depends(require_roles("Admin", "Registrar", "Doctor", "Cashier"))],
    summary="Добавить услугу к визиту",
)
def add_service(visit_id: int, item: VisitServiceIn, db: Session = Depends(get_db)):
    return VisitsApiService(db).add_service(visit_id=visit_id, item=item)


@router.post(
    "/visits/{visit_id}/status",
    dependencies=[Depends(require_roles("Admin", "Doctor", "Registrar"))],
    summary="Смена статуса визита",
)
def set_status(visit_id: int, status_new: str, db: Session = Depends(get_db)):
    visit = VisitsApiService(db).set_status(visit_id=visit_id, status_new=status_new)
    return VisitOut(
        id=visit.id,
        patient_id=visit.patient_id,
        doctor_id=visit.doctor_id,
        status=visit.status,
        created_at=visit.created_at,
        started_at=visit.started_at,
        finished_at=visit.finished_at,
        notes=visit.notes,
        planned_date=visit.visit_date,
    )


@router.post(
    "/visits/{visit_id}/reschedule",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на конкретную дату (new_date в формате YYYY-MM-DD)",
)
def reschedule_visit(
    visit_id: int,
    new_date: date = Query(..., alias="new_date"),
    db: Session = Depends(get_db),
):
    row = VisitsApiService(db).reschedule_visit(visit_id=visit_id, new_date=new_date)
    return VisitOut(**row)


@router.post(
    "/visits/{visit_id}/reschedule/tomorrow",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на завтра (planned_date = today + 1)",
)
def reschedule_visit_tomorrow(visit_id: int, db: Session = Depends(get_db)):
    row = VisitsApiService(db).reschedule_visit_tomorrow(visit_id=visit_id)
    return VisitOut(**row)
