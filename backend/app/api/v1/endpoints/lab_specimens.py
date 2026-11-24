from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import require_active_roles
from app.models.user import User
from app.schemas.lab_specimen import (
    LabSpecimenAssignmentCommand,
    LabSpecimenCommand,
    LabSpecimenCreate,
    LabSpecimenErrorOut,
    LabSpecimenListOut,
    LabSpecimenOut,
    LabSpecimenScan,
    LabSpecimenTransitionCommand,
)
from app.services.lab_reporting_service import LabReportingDomainError
from app.services.lab_specimen_service import LabSpecimenService
from app.services.patient_access_audit import log_patient_access

router = APIRouter(prefix="/lab", tags=["lab-reporting"])

LabActor = Annotated[User, Depends(require_active_roles("Admin", "Lab"))]
DatabaseSession = Annotated[Session, Depends(get_db)]
RecordId = Annotated[int, Path(gt=0)]
READ_ERRORS = {
    403: {"model": LabSpecimenErrorOut, "description": "Laboratory access denied"},
    404: {
        "model": LabSpecimenErrorOut,
        "description": "Record not found in this context",
    },
}
WRITE_ERRORS = {
    **READ_ERRORS,
    409: {
        "model": LabSpecimenErrorOut,
        "description": "Conflict or unavailable action",
    },
}


def _raise_domain_error(exc: LabReportingDomainError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/orders/{order_id}/specimens",
    response_model=LabSpecimenListOut,
    responses=READ_ERRORS,
    operation_id="lab_list_order_specimens",
)
def list_order_specimens(
    order_id: RecordId,
    request: Request,
    response: Response,
    db: DatabaseSession,
    actor: LabActor,
) -> LabSpecimenListOut:
    try:
        result, patient_id = LabSpecimenService(db).get_list(order_id)
    except LabReportingDomainError as exc:
        _raise_domain_error(exc)
    log_patient_access(
        db,
        actor_user=actor,
        subject_patient_id=patient_id,
        resource_type="lab_order_specimens",
        resource_id=str(order_id),
        action="view",
        request=request,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/orders/{order_id}/specimens",
    status_code=201,
    response_model=LabSpecimenOut,
    responses=WRITE_ERRORS,
    operation_id="lab_create_specimen",
)
def create_specimen(
    order_id: RecordId,
    command: LabSpecimenCreate,
    response: Response,
    db: DatabaseSession,
    actor: LabActor,
) -> LabSpecimenOut:
    try:
        result = LabSpecimenService(db).create(order_id, command, actor.id)
    except LabReportingDomainError as exc:
        _raise_domain_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/visits/{visit_id}/specimens",
    status_code=201,
    response_model=LabSpecimenOut,
    responses=WRITE_ERRORS,
    operation_id="lab_collect_specimen_for_visit",
)
def create_visit_specimen(
    visit_id: RecordId,
    command: LabSpecimenCreate,
    response: Response,
    db: DatabaseSession,
    actor: LabActor,
) -> LabSpecimenOut:
    try:
        result = LabSpecimenService(db).create_for_visit(visit_id, command, actor.id)
    except LabReportingDomainError as exc:
        _raise_domain_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/specimens/scan",
    response_model=LabSpecimenOut,
    responses=READ_ERRORS,
    operation_id="lab_scan_specimen",
)
def scan_specimen(
    query: LabSpecimenScan,
    request: Request,
    response: Response,
    db: DatabaseSession,
    actor: LabActor,
) -> LabSpecimenOut:
    try:
        result, patient_id = LabSpecimenService(db).scan(query)
    except LabReportingDomainError as exc:
        _raise_domain_error(exc)
    log_patient_access(
        db,
        actor_user=actor,
        subject_patient_id=patient_id,
        resource_type="lab_specimen",
        resource_id=str(result.id),
        action="view",
        request=request,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/specimens/{specimen_id}/events",
    response_model=LabSpecimenOut,
    responses=WRITE_ERRORS,
    operation_id="lab_apply_specimen_event",
)
def apply_specimen_event(
    specimen_id: RecordId,
    command: LabSpecimenTransitionCommand,
    response: Response,
    db: DatabaseSession,
    actor: LabActor,
) -> LabSpecimenOut:
    try:
        result = LabSpecimenService(db).transition(specimen_id, command, actor.id)
    except LabReportingDomainError as exc:
        _raise_domain_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/specimens/{specimen_id}/assignments",
    response_model=LabSpecimenOut,
    responses=WRITE_ERRORS,
    operation_id="lab_assign_specimen",
)
def assign_specimen(
    specimen_id: RecordId,
    command: LabSpecimenAssignmentCommand,
    response: Response,
    db: DatabaseSession,
    actor: LabActor,
) -> LabSpecimenOut:
    try:
        result = LabSpecimenService(db).assign(specimen_id, command, actor.id)
    except LabReportingDomainError as exc:
        _raise_domain_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/specimens/{specimen_id}/label",
    response_class=Response,
    responses={
        **WRITE_ERRORS,
        200: {
            "description": "Issued Code 128 label",
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}}
            },
        },
    },
    operation_id="lab_issue_specimen_label",
)
def issue_specimen_label(
    specimen_id: RecordId,
    command: LabSpecimenCommand,
    db: DatabaseSession,
    actor: LabActor,
) -> Response:
    try:
        result = LabSpecimenService(db).issue_label(specimen_id, command, actor.id)
    except LabReportingDomainError as exc:
        _raise_domain_error(exc)
    return Response(
        content=result,
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="specimen-label.pdf"',
        },
    )
