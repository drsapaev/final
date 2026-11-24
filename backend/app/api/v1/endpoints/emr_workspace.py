"""Visit-scoped clinician workspace endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.endpoints.emr_v2 import (
    EMR_V2_ALLOWED_ROLES,
    EMR_V2_WRITE_ROLES,
    ensure_emr_visit_access,
    get_current_active_doctor,
)
from app.models.user import User
from app.schemas.emr_workspace import (
    ClinicalEntryOut,
    ClinicalEntryWrite,
    IssuePrescription,
    LabReviewOut,
    LabReviewRequest,
    WorkspaceHistoryDocument,
    WorkspaceLabs,
    WorkspaceOut,
    WorkspacePrescription,
)
from app.services.audit_service import log_audit_event
from app.services.authorization.staff import staff_authorization_service
from app.services.emr_lab_workspace_service import read_visit_labs, record_lab_review
from app.services.emr_prescription_service import issue_prescription, read_prescription
from app.services.emr_workspace_service import EMRWorkspaceService, WorkspaceError
from app.services.reason_codes import ReasonCode

router = APIRouter(prefix="/emr/{visit_id}/workspace")


def fail_workspace(error: WorkspaceError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code})


def audit_workspace(
    db: Session,
    request: Request,
    user: User,
    patient_id: int,
    visit_id: int,
    action: str,
    resource_id: str,
):
    log_audit_event(
        db=db,
        event_type="EMR_WORKSPACE",
        actor_user_id=user.id,
        actor_role=user.role,
        subject_patient_id=patient_id,
        action=action,
        resource_type="emr_workspace",
        resource_id=resource_id,
        reason_code=ReasonCode.visit(visit_id).to_dict(),
        request=request,
    )


def get_history_doctor_id(db: Session, user: User) -> int | None:
    staff = staff_authorization_service
    if staff.has_permission(user, "emr:read") and (
        staff.has_permission(user, "emr:delete") or user.is_superuser
    ):
        return None
    doctor = get_current_active_doctor(db, user)
    if doctor is None:
        raise HTTPException(status_code=403, detail="Access denied")
    return doctor.id


@router.get("", response_model=WorkspaceOut)
def get_emr_workspace(
    visit_id: int,
    request: Request,
    patient_id: int | None = Query(None, gt=0),
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(25, ge=1, le=50),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_ALLOWED_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    service = EMRWorkspaceService(db)
    try:
        visit, patient = service.context(visit_id, patient_id)
        data = service.read(
            visit, patient, get_history_doctor_id(db, current_user), offset, limit
        )
    except WorkspaceError as error:
        raise fail_workspace(error) from error
    audit_workspace(
        db, request, current_user, patient.id, visit.id, "view", str(visit.id)
    )
    return data


@router.put("/entries/{entry_id}", response_model=ClinicalEntryOut)
def put_clinical_entry(
    visit_id: int,
    entry_id: UUID,
    payload: ClinicalEntryWrite,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_WRITE_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    service = EMRWorkspaceService(db)
    try:
        ensure_emr_visit_access(db, visit_id, current_user, for_update=True)
        visit, patient = service.context(visit_id, payload.patient_id)
        if visit.status == "canceled":
            raise WorkspaceError(409, "VISIT_CANCELED")
        data = service.update(visit, entry_id, payload, current_user.id)
        db.commit()
    except WorkspaceError as error:
        db.rollback()
        raise fail_workspace(error) from error
    except HTTPException:
        db.rollback()
        raise
    audit_workspace(
        db, request, current_user, patient.id, visit_id, "edit", str(entry_id)
    )
    return data


@router.get("/entries/{entry_id}/history", response_model=list[ClinicalEntryOut])
def get_clinical_entry_history(
    visit_id: int,
    entry_id: UUID,
    request: Request,
    patient_id: int | None = Query(None, gt=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_ALLOWED_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    service = EMRWorkspaceService(db)
    try:
        visit, patient = service.context(visit_id, patient_id)
    except WorkspaceError as error:
        raise fail_workspace(error) from error
    data = [
        ClinicalEntryOut.model_validate(row)
        for row in service.repository.entry_history(patient.id, entry_id)
    ]
    if not data:
        raise HTTPException(status_code=404, detail="Clinical entry not found")
    audit_workspace(
        db, request, current_user, patient.id, visit.id, "view", str(entry_id)
    )
    return data


@router.get(
    "/history/{source_visit_id}/{version}", response_model=WorkspaceHistoryDocument
)
def get_workspace_history_document(
    visit_id: int,
    source_visit_id: int,
    version: int,
    request: Request,
    patient_id: int | None = Query(None, gt=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_ALLOWED_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    ensure_emr_visit_access(db, source_visit_id, current_user)
    service = EMRWorkspaceService(db)
    try:
        visit, patient = service.context(visit_id, patient_id)
        result = service.history_document(visit, source_visit_id, version)
    except WorkspaceError as error:
        raise fail_workspace(error) from error
    audit_workspace(
        db, request, current_user, patient.id, visit_id, "view", str(result.id)
    )
    return result


@router.get("/prescription", response_model=WorkspacePrescription | None)
def get_workspace_prescription(
    visit_id: int,
    request: Request,
    patient_id: int = Query(gt=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_ALLOWED_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    try:
        visit, patient = EMRWorkspaceService(db).context(visit_id, patient_id)
        result = read_prescription(db, visit)
    except WorkspaceError as error:
        raise fail_workspace(error) from error
    audit_workspace(
        db, request, current_user, patient.id, visit_id, "view", str(visit_id)
    )
    return result


@router.post("/prescription", response_model=WorkspacePrescription)
def post_workspace_prescription(
    visit_id: int,
    payload: IssuePrescription,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_WRITE_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    try:
        visit, patient = EMRWorkspaceService(db).context(visit_id, payload.patient_id)
        result = issue_prescription(
            db,
            visit,
            payload.expected_row_version,
            authorize_visit=lambda locked_id: ensure_emr_visit_access(
                db, locked_id, current_user
            ),
        )
        db.commit()
    except WorkspaceError as error:
        db.rollback()
        raise fail_workspace(error) from error
    except HTTPException:
        db.rollback()
        raise
    audit_workspace(
        db, request, current_user, patient.id, visit_id, "edit", str(result.id)
    )
    return result


@router.get("/labs", response_model=WorkspaceLabs)
def get_workspace_labs(
    visit_id: int,
    request: Request,
    patient_id: int | None = Query(None, gt=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_ALLOWED_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    try:
        visit, patient = EMRWorkspaceService(db).context(visit_id, patient_id)
        result = read_visit_labs(db, visit)
    except WorkspaceError as error:
        raise fail_workspace(error) from error
    audit_workspace(
        db, request, current_user, patient.id, visit_id, "view", str(visit_id)
    )
    return result


@router.post("/labs/{instance_id}/review", response_model=LabReviewOut)
def post_workspace_lab_review(
    visit_id: int,
    instance_id: int,
    payload: LabReviewRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles(*EMR_V2_WRITE_ROLES)),
):
    ensure_emr_visit_access(db, visit_id, current_user)
    try:
        ensure_emr_visit_access(db, visit_id, current_user, for_update=True)
        visit, patient = EMRWorkspaceService(db).context(visit_id, payload.patient_id)
        result = record_lab_review(
            db, visit, instance_id, current_user.id, payload.next_action
        )
        db.commit()
    except WorkspaceError as error:
        db.rollback()
        raise fail_workspace(error) from error
    except HTTPException:
        db.rollback()
        raise
    audit_workspace(
        db, request, current_user, patient.id, visit_id, "edit", str(instance_id)
    )
    return result
