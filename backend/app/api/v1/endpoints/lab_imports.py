"""Manual batch and structured file import for laboratory drafts."""

import json
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.crud.clinic import get_queue_settings
from app.models.lab_specimen import LabSpecimenRejectionReasonCode
from app.models.user import User
from app.schemas.lab_import import LabImportBatch, LabImportBatchOut
from app.services.lab_import import (
    AnalyzerIntegrationError,
    import_analyzer_message,
    process_import_batch,
)
from app.services.lab_operational_metrics import laboratory_metrics

router = APIRouter(prefix="/lab", tags=["lab-operations"])
MAX_ANALYZER_REQUEST_BODY_BYTES = 5 * 1024 * 1024


class LabAnalyzerImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_version_id: int = Field(ge=1)
    report_instance_id: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=1_000_000, repr=False)
    expected_updated_at: AwareDatetime | None = None


def _import_analyzer_request(
    payload: LabAnalyzerImportRequest,
    *,
    db: Session,
    actor_id: int,
    preview: bool,
) -> LabImportBatchOut:
    try:
        rows = import_analyzer_message(
            db,
            profile_version_id=payload.profile_version_id,
            report_instance_id=payload.report_instance_id,
            payload=payload.message,
            actor_id=actor_id,
            expected_updated_at=payload.expected_updated_at,
            preview=preview,
        )
    except AnalyzerIntegrationError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail={"code": exc.code}) from exc
    return LabImportBatchOut(rows=rows)


async def _read_analyzer_request(request: Request) -> LabAnalyzerImportRequest:
    parts = []
    body_size = 0
    async for chunk in request.stream():
        body_size += len(chunk)
        if body_size > MAX_ANALYZER_REQUEST_BODY_BYTES:
            raise HTTPException(status_code=413, detail={"code": "request_too_large"})
        parts.append(chunk)
    try:
        body = json.loads(b"".join(parts))
        return LabAnalyzerImportRequest.model_validate(body)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, TypeError) as exc:
        # Validation errors can include the raw analyzer message as `input`.
        # Return a fixed contract error so a request body cannot be echoed.
        raise HTTPException(status_code=422, detail={"code": "invalid_analyzer_request"}) from exc


@router.post("/imports", response_model=LabImportBatchOut)
def import_lab_values(
    payload: LabImportBatch,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_roles("Admin", "Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return LabImportBatchOut(rows=process_import_batch(db, payload, actor_id=user.id))


@router.post("/imports/preview", response_model=LabImportBatchOut)
def preview_lab_import(
    payload: LabImportBatch,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_roles("Admin", "Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return LabImportBatchOut(
        rows=process_import_batch(db, payload, actor_id=user.id, preview=True)
    )


@router.post("/imports/analyzer", response_model=LabImportBatchOut)
async def import_analyzer_lab_values(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_roles("Admin", "Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    payload = await _read_analyzer_request(request)
    return _import_analyzer_request(
        payload, db=db, actor_id=user.id, preview=False
    )


@router.post("/imports/analyzer/preview", response_model=LabImportBatchOut)
async def preview_analyzer_lab_import(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_roles("Admin", "Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    payload = await _read_analyzer_request(request)
    return _import_analyzer_request(
        payload, db=db, actor_id=user.id, preview=True
    )


class LabMetricsOut(BaseModel):
    from_at: datetime
    until_at: datetime
    actionable: int
    overdue: int
    rejected_samples: int
    rejected_samples_by_reason: dict[
        LabSpecimenRejectionReasonCode | Literal["unknown"], int
    ]
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
    user: User = Depends(require_active_roles("Admin")),
):
    timezone = ZoneInfo(get_queue_settings(db).get("timezone", "Asia/Tashkent"))
    response.headers["Cache-Control"] = "private, no-store"
    return laboratory_metrics(db, timezone, days=days)
