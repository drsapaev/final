from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, Table, and_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles

router = APIRouter()


# Pydantic fallbacks (если полноценные схемы уже есть в app.schemas, в следующих шагах заменим)
class VisitCreate(BaseModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    notes: Optional[str] = None


class VisitOut(BaseModel):
    id: int
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    notes: Optional[str] = None


class VisitServiceIn(BaseModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitWithServices(BaseModel):
    visit: VisitOut
    services: List[VisitServiceIn]


def _visits(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("visits", md, autoload_with=db.get_bind())


def _vservices(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("visit_services", md, autoload_with=db.get_bind())


@router.get("/visits", response_model=List[VisitOut], summary="Список визитов")
def list_visits(
    patient_id: Optional[int] = Query(default=None),
    doctor_id: Optional[int] = Query(default=None),
    status_q: Optional[str] = Query(default=None),
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
    t = _visits(db)
    ins = (
        t.insert()
        .values(
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            status="open",
            notes=payload.notes,
        )
        .returning(t)
    )
    row = db.execute(ins).mappings().first()
    db.commit()
    assert row is not None
    return VisitOut(**row)  # type: ignore[arg-type]


@router.get("/visits/{visit_id}", response_model=VisitWithServices, summary="Карточка визита")
def get_visit(visit_id: int, db: Session = Depends(get_db)):
    t = _visits(db)
    s = _vservices(db)
    vrow = db.execute(select(t).where(t.c.id == visit_id)).mappings().first()
    if not vrow:
        raise HTTPException(404, "Visit not found")
    items = db.execute(select(s).where(s.c.visit_id == visit_id).order_by(s.c.id.asc())).mappings().all()
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

    ins = (
        s.insert()
        .values(
            visit_id=visit_id,
            code=item.code,
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