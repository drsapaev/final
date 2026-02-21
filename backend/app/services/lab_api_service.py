from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.lab import LabOrder
from app.repositories.lab_api_repository import LabApiRepository

router = APIRouter(prefix="/lab", tags=["lab"])



def _repo(db: Session) -> LabApiRepository:
    return LabApiRepository(db)

class LabRowOut(BaseModel):
    id: int
    patient_id: int | None = None
    visit_id: int | None = None
    status: str
    notes: str | None = None


class LabResultIn(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, max_length=16)


def _row_to_out(r: LabOrder) -> LabRowOut:
    return LabRowOut(
        id=r.id,
        patient_id=getattr(r, "patient_id", None),
        visit_id=getattr(r, "visit_id", None),
        status=str(getattr(r, "status", "")),
        notes=getattr(r, "notes", None),
    )


@router.get("", response_model=list[LabRowOut], summary="Список лабораторных заявок")
@router.get(
    "/requests",
    response_model=list[LabRowOut],
    summary="Список лабораторных заявок (alias)",
)
async def list_lab_requests(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor", "Registrar", "Receptionist", "Cashier")),
    status: str | None = Query(default=None, max_length=32),
    patient_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(LabOrder)
    if status:
        stmt = stmt.where(LabOrder.status == status)
    if patient_id:
        stmt = stmt.where(LabOrder.patient_id == patient_id)
    stmt = stmt.order_by(LabOrder.id.desc()).limit(limit).offset(offset)
    rows = _repo(db).execute(stmt).scalars().all()
    return [_row_to_out(r) for r in rows]


@router.put("/{req_id}", response_model=LabRowOut, summary="Обновить результат заявки")
@router.put(
    "/requests/{req_id}",
    response_model=LabRowOut,
    summary="Обновить результат заявки (alias)",
)
async def update_lab_result(
    payload: LabResultIn,
    req_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    row = db.get(LabOrder, req_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.notes is not None:
        row.notes = payload.notes
    if payload.status is not None:
        row.status = payload.status
    _repo(db).flush()
    return _row_to_out(row)
