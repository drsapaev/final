# app/api/v1/endpoints/visits.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, select, Table
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.visits_api_service import VisitsApiService

router = APIRouter()


# Pydantic fallbacks (если полноценные схемы уже есть в app.schemas, в следующих шагах заменим)
class VisitCreate(BaseModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    notes: Optional[str] = None
    planned_date: Optional[date] = None  # <-- новая поддержка
    source: Optional[str] = Field(default="desk", max_length=20)


class VisitOut(BaseModel):
    id: int
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    notes: Optional[str] = None
    planned_date: Optional[date] = None  # <-- новая поддержка
    source: Optional[str] = None


class VisitServiceIn(BaseModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitWithServices(BaseModel):
    visit: VisitOut
    services: List[VisitServiceIn]


def _visits(db: Session) -> Table:
    """
    Return reflected visits table. Использует autoload_with, не bind.
    """
    md = MetaData()
    return Table("visits", md, autoload_with=db.get_bind())


def _vservices(db: Session) -> Table:
    md = MetaData()
    return Table("visit_services", md, autoload_with=db.get_bind())


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
    return [VisitOut(**row) for row in rows]  # type: ignore[arg-type]


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
    current_user = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    result = VisitsApiService(db).create_visit(
        request=request,
        payload=payload,
        current_user=current_user,
    )
    return VisitOut(**result)


@router.get(
    "/visits/{visit_id}", response_model=VisitWithServices, summary="Карточка визита"
)
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
    if status_new not in {"open", "in_progress", "closed", "canceled"}:
        raise HTTPException(400, "Invalid status")
    # Use ORM for reliability
    from app.models.visit import Visit
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "Visit not found")

    visit.status = status_new
    if status_new == "in_progress":
        visit.started_at = datetime.utcnow()
    if status_new in {"closed", "canceled"}:
        visit.finished_at = datetime.utcnow()
    
    # [FIX] Также обновляем статус в очереди, если есть связанная запись
    if status_new == "canceled":
        try:
            from sqlalchemy import text
            db.execute(
                text("UPDATE queue_entries SET status = 'canceled' WHERE visit_id = :visit_id"),
                {"visit_id": visit_id}
            )
        except Exception as e:
            # Ошибка обновления очереди не должна блокировать обновление визита
            pass

    db.commit()
    db.refresh(visit)
    
    # Convert ORM object to Pydantic model
    return VisitOut(
        id=visit.id,
        patient_id=visit.patient_id,
        doctor_id=visit.doctor_id,
        status=visit.status,
        created_at=visit.created_at,
        started_at=visit.started_at,
        finished_at=visit.finished_at,
        notes=visit.notes,
        planned_date=visit.visit_date
    )


#
# Reschedule endpoints — перенос визита
#
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
    """
    Перенос визита на указанную дату (записывается в planned_date).
    Требует, чтобы в таблице visits была колонка planned_date.
    """
    t = _visits(db)
    # Проверка наличия колонки visit_date
    if not hasattr(t.c, "visit_date"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="visits table has no visit_date column; check your schema.",
        )

    vrow = db.execute(select(t).where(t.c.id == visit_id)).mappings().first()
    if not vrow:
        raise HTTPException(404, "Visit not found")

    # Запретим перенос, если визит завершён/отменён или уже начат
    if vrow.get("status") in {"closed", "canceled"}:
        raise HTTPException(
            status_code=409, detail="Cannot reschedule closed or canceled visit"
        )
    if vrow.get("started_at"):
        raise HTTPException(
            status_code=409, detail="Cannot reschedule a visit that has been started"
        )

    upd = (
        t.update().where(t.c.id == visit_id).values(visit_date=new_date).returning(t)
    )
    row = db.execute(upd).mappings().first()
    if not row:
        raise HTTPException(404, "Visit not found")
    
    # [FIX] Обновляем статус в очереди для старой даты
    try:
        from sqlalchemy import text
        # Помечаем старую запись очереди как перенесенную
        db.execute(
            text("UPDATE queue_entries SET status = 'rescheduled' WHERE visit_id = :visit_id"),
            {"visit_id": visit_id}
        )
    except Exception:
        pass

    db.commit()
    return VisitOut(**row)  # type: ignore[arg-type]


@router.post(
    "/visits/{visit_id}/reschedule/tomorrow",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на завтра (planned_date = today + 1)",
)
def reschedule_visit_tomorrow(visit_id: int, db: Session = Depends(get_db)):
    t = _visits(db)
    if not hasattr(t.c, "visit_date"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="visits table has no visit_date column; check your schema.",
        )

    vrow = db.execute(select(t).where(t.c.id == visit_id)).mappings().first()
    if not vrow:
        raise HTTPException(404, "Visit not found")

    if vrow.get("status") in {"closed", "canceled"}:
        raise HTTPException(
            status_code=409, detail="Cannot reschedule closed or canceled visit"
        )
    if vrow.get("started_at"):
        raise HTTPException(
            status_code=409, detail="Cannot reschedule a visit that has been started"
        )

    tomorrow = date.today() + timedelta(days=1)
    upd = (
        t.update().where(t.c.id == visit_id).values(visit_date=tomorrow).returning(t)
    )
    row = db.execute(upd).mappings().first()
    if not row:
        raise HTTPException(404, "Visit not found")
    
    # [FIX] Обновляем статус в очереди для старой даты
    try:
        from sqlalchemy import text
        # Помечаем старую запись очереди как перенесенную
        db.execute(
            text("UPDATE queue_entries SET status = 'rescheduled' WHERE visit_id = :visit_id"),
            {"visit_id": visit_id}
        )
    except Exception:
        pass

    db.commit()
    return VisitOut(**row)  # type: ignore[arg-type]
