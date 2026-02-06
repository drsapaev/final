from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.lab import LabOrder


router = APIRouter(prefix="/lab", tags=["lab"])


class LabRowOut(BaseModel):
    id: int
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    status: str
    notes: Optional[str] = None


class LabResultIn(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(default=None, max_length=16)


def _row_to_out(r: LabOrder) -> LabRowOut:
    return LabRowOut(
        id=r.id,
        patient_id=getattr(r, "patient_id", None),
        visit_id=getattr(r, "visit_id", None),
        status=str(getattr(r, "status", "")),
        notes=getattr(r, "notes", None),
    )


@router.get("", response_model=List[LabRowOut], summary="Список лабораторных заявок")
@router.get(
    "/requests",
    response_model=List[LabRowOut],
    summary="Список лабораторных заявок (alias)",
)
async def list_lab_requests(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor", "Registrar", "Receptionist", "Cashier")),
    status: Optional[str] = Query(default=None, max_length=32),
    patient_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(LabOrder)
    if status:
        stmt = stmt.where(LabOrder.status == status)
    if patient_id:
        stmt = stmt.where(LabOrder.patient_id == patient_id)
    stmt = stmt.order_by(LabOrder.id.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
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
    db.flush()
    return _row_to_out(row)
