from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.lab import LabRequest  # type: ignore[attr-defined]

router = APIRouter(prefix="/lab", tags=["lab"])


class LabRowOut(BaseModel):
    id: int
    patient_id: Optional[int] = None
    service_code: Optional[str] = None
    service_name: Optional[str] = None
    status: str
    result_text: Optional[str] = None


class LabResultIn(BaseModel):
    result_text: Optional[str] = Field(default=None, max_length=20000)
    status: Optional[str] = Field(default=None, max_length=32)


def _row_to_out(r: LabRequest) -> LabRowOut:
    return LabRowOut(
        id=r.id,
        patient_id=getattr(r, "patient_id", None),
        service_code=getattr(r, "service_code", None),
        service_name=getattr(r, "service_name", None),
        status=str(getattr(r, "status", "")),
        result_text=getattr(r, "result_text", None),
    )


@router.get("", response_model=List[LabRowOut], summary="Список лабораторных заявок")
@router.get(
    "/requests",
    response_model=List[LabRowOut],
    summary="Список лабораторных заявок (alias)",
)
async def list_lab_requests(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
    status: Optional[str] = Query(default=None, max_length=32),
    patient_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(LabRequest)
    if status:
        stmt = stmt.where(LabRequest.status == status)
    if patient_id:
        stmt = stmt.where(LabRequest.patient_id == patient_id)
    stmt = stmt.order_by(LabRequest.id.desc()).limit(limit).offset(offset)
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
    row = db.get(LabRequest, req_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.result_text is not None:
        row.result_text = payload.result_text
    if payload.status is not None:
        row.status = payload.status
    db.flush()
    return _row_to_out(row)
