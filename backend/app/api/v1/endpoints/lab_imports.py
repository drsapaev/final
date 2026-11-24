"""Manual batch and structured file import for laboratory drafts."""

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud.clinic import get_queue_settings
from app.models.user import User
from app.schemas.lab_import import LabImportBatch, LabImportBatchOut
from app.services.lab_import import process_import_batch
from app.services.lab_operational_metrics import laboratory_metrics

router = APIRouter(prefix="/lab", tags=["lab-operations"])


@router.post("/imports", response_model=LabImportBatchOut)
def import_lab_values(
    payload: LabImportBatch,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return LabImportBatchOut(rows=process_import_batch(db, payload, actor_id=user.id))


@router.post("/imports/preview", response_model=LabImportBatchOut)
def preview_lab_import(
    payload: LabImportBatch,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return LabImportBatchOut(
        rows=process_import_batch(db, payload, actor_id=user.id, preview=True)
    )


class LabMetricsOut(BaseModel):
    from_at: datetime
    until_at: datetime
    actionable: int
    overdue: int
    rejected_samples: int
    held_samples: int
    turnaround_pairs: int
    average_turnaround_minutes: float | None
    released_corrections: int
    communications_open: int


@router.get("/metrics", response_model=LabMetricsOut)
def lab_metrics(
    response: Response,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin")),
):
    timezone = ZoneInfo(get_queue_settings(db).get("timezone", "Asia/Tashkent"))
    response.headers["Cache-Control"] = "private, no-store"
    return laboratory_metrics(db, timezone, days=days)
