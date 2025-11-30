# app/api/v1/endpoints/visits.py
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, select, Table
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.service_mapping import normalize_service_code

router = APIRouter()


# Pydantic fallbacks (если полноценные схемы уже есть в app.schemas, в следующих шагах заменим)
class VisitCreate(BaseModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    notes: Optional[str] = None
    planned_date: Optional[date] = None  # <-- новая поддержка


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
    t = _visits(db)
    stmt = select(t)
    if patient_id is not None:
        stmt = stmt.where(t.c.patient_id == patient_id)
    if doctor_id is not None:
        stmt = stmt.where(t.c.doctor_id == doctor_id)
    if status_q:
        stmt = stmt.where(t.c.status == status_q)
    if planned is not None:
        # фильтр по planned_date (если столбец есть)
        if "planned_date" in t.c:
            stmt = stmt.where(t.c.planned_date == planned)
        else:
            # если столбца нет — просто возвращаем пустой список или raise (выбрал мягкое поведение)
            return []
    stmt = stmt.order_by(t.c.id.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).mappings().all()
    return [VisitOut(**row) for row in rows]  # type: ignore[arg-type]


@router.post(
    "/visits",
    response_model=VisitOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("Admin", "Registrar", "Doctor"))],
    summary="Создать визит",
)
def create_visit(payload: VisitCreate, db: Session = Depends(get_db)):
    """
    Создать визит.

    Использует feature flag USE_CRUD_VISITS для переключения между старой (Table API)
    и новой (CRUD) реализацией. По умолчанию используется старая реализация для безопасности.
    """
    # Feature flag для безопасной миграции на CRUD
    use_crud = os.getenv("USE_CRUD_VISITS", "false").lower() == "true"

    if use_crud:
        # Новая реализация через CRUD (Single Source of Truth)
        from app.crud.visit import create_visit as crud_create_visit

        visit = crud_create_visit(
            db=db,
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            visit_date=payload.planned_date,  # planned_date -> visit_date
            notes=payload.notes,
            status="open",
            auto_status=False,  # Статус уже установлен
            notify=False,
            log=True,
        )

        return VisitOut(
            id=visit.id,
            patient_id=visit.patient_id,
            doctor_id=visit.doctor_id,
            status=visit.status,
            created_at=visit.created_at,
            started_at=None,
            finished_at=None,
            notes=visit.notes,
            planned_date=visit.visit_date,
        )
    else:
        # Старая реализация через Table API (для обратной совместимости)
        t = _visits(db)
        ins_values = {
            "patient_id": payload.patient_id,
            "doctor_id": payload.doctor_id,
            "status": "open",
            "notes": payload.notes,
        }
        # если передали planned_date — добавим в insert (если колонка есть)
        if hasattr(t.c, "planned_date") and payload.planned_date is not None:
            ins_values["planned_date"] = payload.planned_date

        ins = t.insert().values(**ins_values).returning(t)
        row = db.execute(ins).mappings().first()
        db.commit()
        assert row is not None
        return VisitOut(**row)  # type: ignore[arg-type]


@router.get(
    "/visits/{visit_id}", response_model=VisitWithServices, summary="Карточка визита"
)
def get_visit(visit_id: int, db: Session = Depends(get_db)):
    t = _visits(db)
    s = _vservices(db)
    vrow = db.execute(select(t).where(t.c.id == visit_id)).mappings().first()
    if not vrow:
        raise HTTPException(404, "Visit not found")
    items = (
        db.execute(select(s).where(s.c.visit_id == visit_id).order_by(s.c.id.asc()))
        .mappings()
        .all()
    )
    return VisitWithServices(
        visit=VisitOut(**vrow),  # type: ignore[arg-type]
        services=[VisitServiceIn(**it) for it in items],  # type: ignore[list-item]
    )


@router.post(
    "/visits/{visit_id}/services",
    dependencies=[Depends(require_roles("Admin", "Registrar", "Doctor", "Cashier"))],
    summary="Добавить услугу к визиту",
)
def add_service(visit_id: int, item: VisitServiceIn, db: Session = Depends(get_db)):
    t = _visits(db)
    s = _vservices(db)
    exists = db.execute(select(t.c.id).where(t.c.id == visit_id)).first()
    if not exists:
        raise HTTPException(404, "Visit not found")

    # Normalize service code before using it
    normalized_code = normalize_service_code(item.code) if item.code else None

    ins = (
        s.insert()
        .values(
            visit_id=visit_id,
            code=normalized_code,
            name=item.name,
            price=item.price,
            qty=item.qty,
        )
        .returning(s)
    )
    row = db.execute(ins).mappings().first()
    db.commit()
    return {"ok": True, "service": dict(row)}


@router.post(
    "/visits/{visit_id}/status",
    dependencies=[Depends(require_roles("Admin", "Doctor"))],
    summary="Смена статуса визита",
)
def set_status(visit_id: int, status_new: str, db: Session = Depends(get_db)):
    if status_new not in {"open", "in_progress", "closed", "canceled"}:
        raise HTTPException(400, "Invalid status")
    t = _visits(db)
    values = {"status": status_new}
    if status_new == "in_progress":
        values["started_at"] = datetime.utcnow()
    if status_new in {"closed", "canceled"}:
        values["finished_at"] = datetime.utcnow()
    upd = t.update().where(t.c.id == visit_id).values(**values).returning(t)
    row = db.execute(upd).mappings().first()
    if not row:
        raise HTTPException(404, "Visit not found")
    db.commit()
    return VisitOut(**row)  # type: ignore[arg-type]


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
    # Проверка наличия колонки planned_date
    if not hasattr(t.c, "planned_date"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="visits table has no planned_date column; add it via migration and retry.",
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
        t.update().where(t.c.id == visit_id).values(planned_date=new_date).returning(t)
    )
    row = db.execute(upd).mappings().first()
    if not row:
        raise HTTPException(404, "Visit not found")
    db.commit()
    return VisitOut(**row)  # type: ignore[arg-type]


@router.post(
    "/visits/{visit_id}/reschedule/tomorrow",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на завтра (planned_date = today + 1)",
)
def reschedule_visit_tomorrow(visit_id: int, db: Session = Depends(get_db)):
    t = _visits(db)
    if not hasattr(t.c, "planned_date"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="visits table has no planned_date column; add it via migration and retry.",
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
        t.update().where(t.c.id == visit_id).values(planned_date=tomorrow).returning(t)
    )
    row = db.execute(upd).mappings().first()
    if not row:
        raise HTTPException(404, "Visit not found")
    db.commit()
    return VisitOut(**row)  # type: ignore[arg-type]
