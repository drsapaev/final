from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.lab import LabOrder
from app.services.lab_api_service import LabApiDomainError, LabApiService

router = APIRouter(prefix="/lab", tags=["lab"])


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
    rows = LabApiService(db).list_requests(
        status=status,
        patient_id=patient_id,
        limit=limit,
        offset=offset,
    )
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
    service = LabApiService(db)
    try:
        row = service.update_result(
            req_id=req_id,
            notes=payload.notes,
            status=payload.status,
        )
        return _row_to_out(row)
    except LabApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
