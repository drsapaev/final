from __future__ import annotations

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, Table, select, asc, desc
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles

router = APIRouter(prefix="/patients", tags=["patients"])


# --- Schemas: пробуем использовать проектные, иначе — локальные фолбэки ---
try:
    # Если в проекте есть полноценные схемы — используем их
    from app.schemas.patient import PatientCreate, PatientUpdate, PatientOut  # type: ignore[attr-defined]
except Exception:
    class PatientBase(BaseModel):
        first_name: Optional[str] = Field(default=None, max_length=120)
        last_name: Optional[str] = Field(default=None, max_length=120)
        middle_name: Optional[str] = Field(default=None, max_length=120)
        birth_date: Optional[str] = None  # YYYY-MM-DD
        gender: Optional[str] = Field(default=None, max_length=8)
        phone: Optional[str] = Field(default=None, max_length=32)
        doc_type: Optional[str] = Field(default=None, max_length=32)
        doc_number: Optional[str] = Field(default=None, max_length=64)
        address: Optional[str] = Field(default=None, max_length=512)
        
        class Config:
            from_attributes = True

    class PatientCreate(PatientBase):
        pass

    class PatientUpdate(PatientBase):
        pass

    class PatientOut(PatientBase):
        id: int


def _patients_table(db: Session) -> Table:
    md = MetaData()
    return Table("patients", md, autoload_with=db.get_bind())


def _row_to_out(row: Dict[str, Any]) -> PatientOut:
    # Преобразуем объект date в строку для Pydantic
    if 'birth_date' in row and row['birth_date']:
        if hasattr(row['birth_date'], 'strftime'):
            row['birth_date'] = row['birth_date'].strftime('%Y-%m-%d')
    
    return PatientOut(**row)  # type: ignore[arg-type]


@router.get(
    "",
    response_model=List[PatientOut],
    summary="Список пациентов",
)
def list_patients(
    q: Optional[str] = Query(default=None, description="Поиск: ФИО/телефон/документ"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="-id", description="id|-id|last_name|first_name"),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")),
):
    t = _patients_table(db)
    stmt = select(t)

    if q:
        like = f"%{q}%"
        cond = (
            (t.c.first_name.ilike(like))
            | (t.c.last_name.ilike(like))
            | (t.c.middle_name.ilike(like))
            | (t.c.phone.ilike(like))
            | (t.c.doc_number.ilike(like))
        )
        stmt = stmt.where(cond)

    # sort
    direction = desc if sort.startswith("-") else asc
    col = sort[1:] if sort.startswith("-") else sort
    if col not in t.c:
        col = "id"
    stmt = stmt.order_by(direction(t.c[col])).limit(limit).offset(offset)

    rows = db.execute(stmt).mappings().all()
    return [_row_to_out(dict(r)) for r in rows]


@router.post(
    "",
    response_model=PatientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пациента",
)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar")),
):
    t = _patients_table(db)
    values = {k: v for k, v in payload.model_dump().items() if v is not None}
    
    # Преобразуем строку birth_date в объект date
    if 'birth_date' in values and values['birth_date']:
        try:
            from datetime import datetime
            values['birth_date'] = datetime.strptime(values['birth_date'], '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid birth_date format. Use YYYY-MM-DD")
    
    ins = t.insert().values(**values)
    res = db.execute(ins)
    db.flush()

    new_id = res.lastrowid
    if not new_id:
        # на некоторых БД lastrowid недоступен — подстрахуемся max(id)
        new_id = db.execute(select(t.c.id).order_by(desc(t.c.id)).limit(1)).scalar_one()

    row = db.execute(select(t).where(t.c.id == new_id)).mappings().first()
    assert row is not None
    db.commit()
    return _row_to_out(dict(row))


@router.get(
    "/{patient_id}",
    response_model=PatientOut,
    summary="Получить пациента по id",
)
def get_patient(
    patient_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")),
):
    t = _patients_table(db)
    row = db.execute(select(t).where(t.c.id == patient_id)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _row_to_out(dict(row))


@router.put(
    "/{patient_id}",
    response_model=PatientOut,
    summary="Обновить пациента",
)
def update_patient(
    payload: PatientUpdate,
    patient_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar")),
):
    t = _patients_table(db)
    row = db.execute(select(t).where(t.c.id == patient_id)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")

    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if patch:
        db.execute(t.update().where(t.c.id == patient_id).values(**patch))
        db.flush()

    row2 = db.execute(select(t).where(t.c.id == patient_id)).mappings().first()
    assert row2 is not None
    db.commit()
    return _row_to_out(dict(row2))


@router.delete(
    "/{patient_id}",
    summary="Удалить пациента",
)
def delete_patient(
    patient_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    t = _patients_table(db)
    row = db.execute(select(t).where(t.c.id == patient_id)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")

    db.execute(t.delete().where(t.c.id == patient_id))
    db.commit()
    return {"ok": True}