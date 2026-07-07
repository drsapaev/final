"""
EMR v2 API Endpoints - Production EMR with versioning

Endpoints:
- GET  /emr/{visit_id}           - Get current EMR for visit
- GET  /emr/{visit_id}/history   - Get all revisions
- GET  /emr/{visit_id}/version/{v} - Get specific version
- POST /emr/{visit_id}           - Create or update EMR (new version)
- POST /emr/{visit_id}/sign      - Sign EMR (finalize)
- POST /emr/{visit_id}/amend     - Create amendment (post-sign)
- POST /emr/{visit_id}/restore   - Restore to specific version
- GET  /emr/{visit_id}/diff      - Compare two versions
- GET  /emr/patient/{patient_id} - Get all EMRs for patient
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.core.audit import extract_model_changes, log_critical_change
from app.models.clinic import Doctor
from app.models.user import User
from app.models.visit import Visit
from app.schemas.emr_v2 import (
    EMRAmendRequest,
    EMRDiffOut,
    EMRHistoryOut,
    EMRRecordOut,
    EMRRecordSummary,
    EMRRestoreRequest,
    EMRRevisionOut,
    EMRRevisionSummary,
    EMRSaveRequest,
    EMRSignRequest,
)
from app.services.emr_doctor_history_service import (
    EMRDoctorHistoryDomainError,
    EMRDoctorHistoryService,
)
from app.services.emr_v2_service import (
    ConcurrencyError,
    EMRNotFoundException,
    EMRSignedError,
    emr_v2_service,
)
from app.services.section_templates_service import DoctorSectionTemplatesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emr", tags=["EMR v2"])

# EMR-AUDIT-28 P0-1: "Lab"/"Laboratory" removed from ALLOWED_ROLES.
# Lab role could read ANY patient's EMR by sequential visit_id enumeration
# (ensure_emr_visit_access returned early without ownership check for
# non-doctor roles). Lab should use a dedicated /lab/emr-summary endpoint
# that returns only lab-relevant fields, not full clinical narrative.
EMR_V2_ALLOWED_ROLES = (
    "Doctor",
    "Admin",
    "cardio",
    "cardiology",
    "Cardiologist",
    "Cardio",
    "derma",
    "Dermatologist",
    "dentist",
    "Dentist",
)

EMR_V2_DOCTOR_ROLES = {
    "Doctor",
    "cardio",
    "cardiology",
    "Cardiologist",
    "Cardio",
    "derma",
    "Dermatologist",
    "dentist",
    "Dentist",
}

EMR_V2_WRITE_ROLES = (
    "Admin",
    *EMR_V2_DOCTOR_ROLES,
)


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_active_doctor(db: Session, current_user: User) -> Doctor | None:
    return (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active == True)
        .first()
    )


def ensure_emr_visit_access(db: Session, visit_id: int, current_user: User) -> None:
    """Prevent doctor-profile users from opening another doctor's visit EMR.

    EMR-AUDIT-28 P0-1: ранее non-doctor roles (Lab) bypassed ownership check
    (early return без проверки). Теперь все non-Admin роли без Doctor profile
    получают 403.
    """
    if current_user.role == "Admin" or current_user.is_superuser:
        return

    doctor = get_current_active_doctor(db, current_user)
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")

    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if visit.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="Access denied")


def filter_patient_emrs_for_access(
    db: Session,
    emrs: list,
    current_user: User,
) -> list:
    if current_user.role == "Admin" or current_user.is_superuser:
        return emrs

    doctor = get_current_active_doctor(db, current_user)
    if not doctor:
        # EMR-AUDIT-28 P0-1: deny all non-Admin roles without Doctor profile
        raise HTTPException(status_code=403, detail="Access denied")

    visit_ids = [emr.visit_id for emr in emrs]
    if not visit_ids:
        return emrs

    allowed_visit_ids = {
        row[0]
        for row in db.query(Visit.id)
        .filter(Visit.id.in_(visit_ids), Visit.doctor_id == doctor.id)
        .all()
    }
    return [emr for emr in emrs if emr.visit_id in allowed_visit_ids]


# =============================================================================
# GET Endpoints
# =============================================================================


class DoctorHistoryEntry(BaseModel):
    """Single history entry"""
    content: str
    diagnosis: str | None = None
    created_at: str


class DoctorHistoryResponse(BaseModel):
    """Doctor history response"""
    entries: list[DoctorHistoryEntry]
    total: int
    field_name: str


@router.get("/doctor-history", response_model=DoctorHistoryResponse)
async def get_doctor_history(
    doctor_id: int = Query(..., description="Doctor ID"),
    field_name: str = Query(..., description="Field name (complaints, diagnosis, etc.)"),
    specialty: str = Query("general", description="Doctor specialty"),
    search_text: str | None = Query(None, description="Search text for similarity"),
    limit: int = Query(10, ge=1, le=50, description="Max entries"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_ALLOWED_ROLES)),
):
    """
    Get doctor's previous EMR entries for a specific field.

    Used to provide context to AI for better suggestions.
    Doctor can only access their own history.
    """
    # Security: doctor can only access their own history
    is_admin = current_user.role == "Admin" or current_user.is_superuser
    if current_user.id != doctor_id and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    history_service = EMRDoctorHistoryService(db)
    try:
        entries = history_service.get_history_entries(
            doctor_id=doctor_id,
            field_name=field_name,
            specialty=specialty,
            search_text=search_text,
            limit=limit,
        )
        return DoctorHistoryResponse(
            entries=[DoctorHistoryEntry(**entry) for entry in entries],
            total=len(entries),
            field_name=field_name,
        )
    except EMRDoctorHistoryDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        logger.error("[EMR v2] Doctor history error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch history") from exc


@router.get("/{visit_id}", response_model=EMRRecordOut)
async def get_emr(
    visit_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_ALLOWED_ROLES)),
):
    """
    Get current EMR for visit.

    Returns the latest version of the EMR for the specified visit.
    Creates an audit log entry for the view action.
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    emr = emr_v2_service.get_by_visit(db, visit_id)
    if not emr:
        raise HTTPException(status_code=404, detail="EMR not found")

    # Log view action
    emr_v2_service.log_view(
        db,
        emr=emr,
        user_id=current_user.id,
        user_role=current_user.role if hasattr(current_user, 'role') else "Doctor",
        ip_address=get_client_ip(request),
    )

    return emr


@router.get("/{visit_id}/history", response_model=EMRHistoryOut)
async def get_emr_history(
    visit_id: int,
    limit: int = Query(50, ge=1, le=200, description="Maximum revisions to return"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_ALLOWED_ROLES)),
):
    """
    Get revision history for EMR.

    Returns list of all revisions in descending order (newest first).
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    emr = emr_v2_service.get_by_visit(db, visit_id)
    if not emr:
        raise HTTPException(status_code=404, detail="EMR not found")

    revisions = emr_v2_service.get_history(db, emr.id, limit=limit)

    return {
        "emr_id": emr.id,
        "current_version": emr.version,
        "revisions": [
            EMRRevisionSummary(
                id=r.id,
                version=r.version,
                change_type=r.change_type,
                change_summary=r.change_summary,
                created_by=r.created_by,
                created_at=r.created_at,
            )
            for r in revisions
        ],
    }


@router.get("/{visit_id}/version/{version}", response_model=EMRRevisionOut)
async def get_emr_version(
    visit_id: int,
    version: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_ALLOWED_ROLES)),
):
    """
    Get specific version of EMR.

    Returns the complete data snapshot for the specified version.
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    emr = emr_v2_service.get_by_visit(db, visit_id)
    if not emr:
        raise HTTPException(status_code=404, detail="EMR not found")

    revision = emr_v2_service.get_revision(db, emr.id, version)
    if not revision:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    return revision


@router.get("/{visit_id}/diff", response_model=EMRDiffOut)
async def compare_versions(
    visit_id: int,
    v1: int = Query(..., ge=1, description="First version number"),
    v2: int = Query(..., ge=1, description="Second version number"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_ALLOWED_ROLES)),
):
    """
    Compare two EMR versions.

    Returns list of field changes between the two versions.
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    try:
        diff = emr_v2_service.get_diff(db, visit_id, v1, v2)
        return diff
    except EMRNotFoundException:
        raise HTTPException(status_code=404, detail="EMR not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Internal server error")


@router.get("/patient/{patient_id}", response_model=list[EMRRecordSummary])
async def get_patient_emrs(
    patient_id: int,
    limit: int = Query(100, ge=1, le=500, description="Maximum EMRs to return"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_ALLOWED_ROLES)),
):
    """
    Get all EMRs for a patient.

    Returns list of EMR summaries in descending order by creation date.
    """
    emrs = emr_v2_service.get_by_patient(db, patient_id, limit=limit)
    return filter_patient_emrs_for_access(db, emrs, current_user)


# =============================================================================
# POST Endpoints
# =============================================================================


@router.post("/{visit_id}", response_model=EMRRecordOut)
async def save_emr(
    visit_id: int,
    payload: EMRSaveRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_WRITE_ROLES)),
):
    """
    Save EMR with versioning.

    Creates new EMR if none exists, otherwise updates with new version.
    Uses optimistic locking via row_version to detect concurrent edits.

    **Conflict Resolution:**
    - If row_version mismatch and different user: returns 409 Conflict
    - If row_version mismatch but same user/session: allows (autosave)
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    try:
        existing_emr = emr_v2_service.get_by_visit(db, visit_id)
        old_data = None
        if existing_emr is not None:
            old_data, _ = extract_model_changes(existing_emr, None)

        emr = emr_v2_service.save(
            db,
            visit_id=visit_id,
            data=payload.data,
            user_id=current_user.id,
            row_version=payload.row_version,
            client_session_id=payload.client_session_id,
            is_draft=payload.is_draft,
        )
        _, new_data = extract_model_changes(None, emr)
        log_critical_change(
            db=db,
            user_id=current_user.id,
            action="CREATE" if existing_emr is None else "UPDATE",
            table_name="emr",
            row_id=emr.id,
            old_data=old_data,
            new_data=new_data,
            request=request,
            description=f"Сохранен EMR ID={emr.id} для визита {visit_id}",
        )
        db.commit()
        return emr
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONFLICT",
                "message": str(e),
                "current_version": e.current_version,
                "your_version": e.your_version,
                "last_edited_by": e.last_edited_by,
                "last_edited_at": e.last_edited_at.isoformat(),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Internal server error")


@router.post("/{visit_id}/sign", response_model=EMRRecordOut)
async def sign_emr(
    visit_id: int,
    payload: EMRSignRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_WRITE_ROLES)),
):
    """
    Sign and finalize EMR.

    Changes status to 'signed' and records signing timestamp.
    After signing, EMR can only be modified via the amend endpoint.
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    try:
        emr = emr_v2_service.sign(
            db,
            visit_id=visit_id,
            data=payload.data,
            user_id=current_user.id,
            row_version=payload.row_version,
            client_session_id=payload.client_session_id,
        )

        # 🧠 Learn from signed EMR - create section templates
        try:
            template_service = DoctorSectionTemplatesService(db)
            icd10_code = payload.data.get('icd10_code') or payload.data.get('icd_10_code')

            # Learn from each section with content
            sections_to_learn = [
                ('anamnesis', payload.data.get('anamnesis_morbi')),
                ('examination', payload.data.get('examination')),
                ('treatment', payload.data.get('treatment') or payload.data.get('medications', {}).get('text')),
                ('recommendations', payload.data.get('recommendations')),
            ]

            for section_type, text in sections_to_learn:
                if text and text.strip():
                    await template_service.learn_from_signed_emr(
                        doctor_id=current_user.id,
                        section_type=section_type,
                        text=text,
                        icd10_code=icd10_code,
                    )

            logger.info(f"Learned templates from EMR sign: visit_id={visit_id}, doctor_id={current_user.id}")
        except Exception as learn_error:
            # Don't fail signing if learning fails
            logger.warning(f"Failed to learn templates from EMR: {learn_error}")

        return emr
    except EMRNotFoundException:
        raise HTTPException(status_code=404, detail="EMR not found")
    except EMRSignedError as e:
        raise HTTPException(status_code=400, detail="Internal server error")
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONFLICT",
                "message": str(e),
                "current_version": e.current_version,
                "your_version": e.your_version,
            },
        )


@router.post("/{visit_id}/amend", response_model=EMRRecordOut)
async def amend_emr(
    visit_id: int,
    payload: EMRAmendRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_WRITE_ROLES)),
):
    """
    Amend a signed EMR.

    Creates a new version with amendment, requires a reason (min 10 chars).
    Only available for EMRs with status 'signed'.
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    try:
        emr = emr_v2_service.amend(
            db,
            visit_id=visit_id,
            data=payload.data,
            reason=payload.reason,
            user_id=current_user.id,
            row_version=payload.row_version,
        )
        return emr
    except EMRNotFoundException:
        raise HTTPException(status_code=404, detail="EMR not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Internal server error")
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONFLICT",
                "message": str(e),
                "current_version": e.current_version,
                "your_version": e.your_version,
            },
        )


@router.post("/{visit_id}/restore", response_model=EMRRecordOut)
async def restore_emr(
    visit_id: int,
    payload: EMRRestoreRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles(*EMR_V2_WRITE_ROLES)),
):
    """
    Restore EMR to a specific version.

    Creates a new version with data from the target version.
    The restore is recorded in the revision history.
    """
    ensure_emr_visit_access(db, visit_id, current_user)

    try:
        emr = emr_v2_service.restore(
            db,
            visit_id=visit_id,
            target_version=payload.target_version,
            user_id=current_user.id,
            reason=payload.reason,
        )
        return emr
    except EMRNotFoundException:
        raise HTTPException(status_code=404, detail="EMR not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Internal server error")


