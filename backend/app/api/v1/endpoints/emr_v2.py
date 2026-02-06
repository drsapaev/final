"""
EMR v2 API Endpoints - Production EMR with versioning

Endpoints:
- GET  /emr/feature-flags        - Get EMR v2 feature flag config
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
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.user import User
from app.schemas.emr_v2 import (
    EMRAmendRequest,
    EMRConflictError,
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
from app.services.emr_v2_service import (
    ConcurrencyError,
    EMRNotFoundException,
    EMRSignedError,
    emr_v2_service,
)
from app.services.section_templates_service import DoctorSectionTemplatesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emr", tags=["EMR v2"])


# =============================================================================
# Feature Flags
# =============================================================================


class FeatureFlagsResponse(BaseModel):
    """EMR v2 feature flags configuration"""
    enabled: bool
    rollout_percentage: int
    allowed_user_ids: List[int]
    shadow_mode: bool


@router.get("/feature-flags", response_model=FeatureFlagsResponse)
async def get_feature_flags(
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get EMR v2 feature flags configuration.
    
    Returns the current rollout configuration for the frontend
    to determine which EMR version to display.
    """
    # Parse allowed user IDs from comma-separated string
    allowed_ids = []
    if settings.EMR_V2_ALLOWED_USER_IDS:
        try:
            allowed_ids = [
                int(uid.strip()) 
                for uid in settings.EMR_V2_ALLOWED_USER_IDS.split(",")
                if uid.strip().isdigit()
            ]
        except ValueError:
            pass  # Invalid format, use empty list
    
    return FeatureFlagsResponse(
        enabled=settings.EMR_V2_ENABLED,
        rollout_percentage=settings.EMR_V2_ROLLOUT_PERCENTAGE,
        allowed_user_ids=allowed_ids,
        shadow_mode=settings.EMR_V2_SHADOW_MODE,
    )


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# =============================================================================
# GET Endpoints
# =============================================================================


@router.get("/{visit_id}", response_model=EMRRecordOut)
async def get_emr(
    visit_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Doctor", "Admin")),
):
    """
    Get current EMR for visit.
    
    Returns the latest version of the EMR for the specified visit.
    Creates an audit log entry for the view action.
    """
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
    current_user: User = Depends(deps.require_roles("Doctor", "Admin")),
):
    """
    Get revision history for EMR.
    
    Returns list of all revisions in descending order (newest first).
    """
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
    current_user: User = Depends(deps.require_roles("Doctor", "Admin")),
):
    """
    Get specific version of EMR.
    
    Returns the complete data snapshot for the specified version.
    """
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
    current_user: User = Depends(deps.require_roles("Doctor", "Admin")),
):
    """
    Compare two EMR versions.
    
    Returns list of field changes between the two versions.
    """
    try:
        diff = emr_v2_service.get_diff(db, visit_id, v1, v2)
        return diff
    except EMRNotFoundException:
        raise HTTPException(status_code=404, detail="EMR not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patient/{patient_id}", response_model=List[EMRRecordSummary])
async def get_patient_emrs(
    patient_id: int,
    limit: int = Query(100, ge=1, le=500, description="Maximum EMRs to return"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Doctor", "Admin")),
):
    """
    Get all EMRs for a patient.
    
    Returns list of EMR summaries in descending order by creation date.
    """
    emrs = emr_v2_service.get_by_patient(db, patient_id, limit=limit)
    return emrs


# =============================================================================
# POST Endpoints
# =============================================================================


@router.post("/{visit_id}", response_model=EMRRecordOut)
async def save_emr(
    visit_id: int,
    payload: EMRSaveRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Doctor")),
):
    """
    Save EMR with versioning.
    
    Creates new EMR if none exists, otherwise updates with new version.
    Uses optimistic locking via row_version to detect concurrent edits.
    
    **Conflict Resolution:**
    - If row_version mismatch and different user: returns 409 Conflict
    - If row_version mismatch but same user/session: allows (autosave)
    """
    try:
        emr = emr_v2_service.save(
            db,
            visit_id=visit_id,
            data=payload.data,
            user_id=current_user.id,
            row_version=payload.row_version,
            client_session_id=payload.client_session_id,
            is_draft=payload.is_draft,
        )
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
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{visit_id}/sign", response_model=EMRRecordOut)
async def sign_emr(
    visit_id: int,
    payload: EMRSignRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Doctor")),
):
    """
    Sign and finalize EMR.
    
    Changes status to 'signed' and records signing timestamp.
    After signing, EMR can only be modified via the amend endpoint.
    """
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
        raise HTTPException(status_code=400, detail=str(e))
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
    current_user: User = Depends(deps.require_roles("Doctor")),
):
    """
    Amend a signed EMR.
    
    Creates a new version with amendment, requires a reason (min 10 chars).
    Only available for EMRs with status 'signed'.
    """
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
        raise HTTPException(status_code=400, detail=str(e))
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
    current_user: User = Depends(deps.require_roles("Doctor", "Admin")),
):
    """
    Restore EMR to a specific version.
    
    Creates a new version with data from the target version.
    The restore is recorded in the revision history.
    """
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
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Doctor History (for AI context)
# =============================================================================


class DoctorHistoryEntry(BaseModel):
    """Single history entry"""
    content: str
    diagnosis: Optional[str] = None
    created_at: str


class DoctorHistoryResponse(BaseModel):
    """Doctor history response"""
    entries: List[DoctorHistoryEntry]
    total: int
    field_name: str


@router.get("/doctor-history", response_model=DoctorHistoryResponse)
async def get_doctor_history(
    doctor_id: int = Query(..., description="Doctor ID"),
    field_name: str = Query(..., description="Field name (complaints, diagnosis, etc.)"),
    specialty: str = Query("general", description="Doctor specialty"),
    search_text: Optional[str] = Query(None, description="Search text for similarity"),
    limit: int = Query(10, ge=1, le=50, description="Max entries"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Doctor")),
):
    """
    Get doctor's previous EMR entries for a specific field.
    
    Used to provide context to AI for better suggestions.
    Doctor can only access their own history.
    """
    # Security: doctor can only access their own history
    if current_user.id != doctor_id and not current_user.has_role("Admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Map field names to EMR columns
    field_map = {
        "complaints": "complaints",
        "anamnesis_morbi": "anamnesis_morbi",
        "anamnesis_vitae": "anamnesis_vitae",
        "examination": "examination",
        "diagnosis": "diagnosis",
        "treatment": "treatment",
        "recommendations": "recommendations",
    }
    
    db_field = field_map.get(field_name)
    if not db_field:
        raise HTTPException(status_code=400, detail=f"Invalid field name: {field_name}")
    
    try:
        # Query EMR records created by this doctor
        from app.models.emr_v2 import EMRRecord
        from sqlalchemy import desc
        
        query = db.query(EMRRecord).filter(
            EMRRecord.created_by == doctor_id,
            getattr(EMRRecord, db_field).isnot(None),
            getattr(EMRRecord, db_field) != "",
        )
        
        # If search text provided, filter by similarity (simple LIKE)
        if search_text and len(search_text) >= 3:
            query = query.filter(
                getattr(EMRRecord, db_field).ilike(f"%{search_text[:50]}%")
            )
        
        # Order by recency, limit
        records = query.order_by(desc(EMRRecord.updated_at)).limit(limit).all()
        
        entries = []
        for record in records:
            content = getattr(record, db_field, "")
            if content:
                entries.append(DoctorHistoryEntry(
                    content=content[:500],  # Limit content size
                    diagnosis=record.diagnosis[:200] if record.diagnosis else None,
                    created_at=record.created_at.isoformat() if record.created_at else "",
                ))
        
        return DoctorHistoryResponse(
            entries=entries,
            total=len(entries),
            field_name=field_name,
        )
        
    except Exception as e:
        logger.error(f"[EMR v2] Doctor history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")
