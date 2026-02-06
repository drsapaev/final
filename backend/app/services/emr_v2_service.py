"""
EMR v2 Service - Business logic for production EMR

Features:
- Optimistic locking with row_version
- Smart conflict resolution with client_session_id
- Automatic revision creation
- Audit logging for all actions
- Materialized field extraction
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.emr_v2 import EMRAuditLog, EMRRecord, EMRRevision, SYSTEM_USER_ID
from app.models.visit import Visit

logger = logging.getLogger(__name__)


class ConcurrencyError(Exception):
    """Raised when optimistic lock fails"""

    def __init__(
        self,
        message: str,
        current_version: int,
        your_version: int,
        last_edited_by: int,
        last_edited_at: datetime,
    ):
        super().__init__(message)
        self.current_version = current_version
        self.your_version = your_version
        self.last_edited_by = last_edited_by
        self.last_edited_at = last_edited_at


class EMRNotFoundException(Exception):
    """Raised when EMR not found"""

    pass


class EMRSignedError(Exception):
    """Raised when trying to edit signed EMR without amendment"""

    pass


class EMRV2Service:
    """
    Production EMR Service
    
    RULES:
    - EMR is NEVER physically deleted
    - Every save creates a new revision
    - Optimistic locking prevents lost updates
    - Same-user conflicts are auto-resolved via client_session_id
    """

    # ==========================================================================
    # READ Operations
    # ==========================================================================

    def get_by_id(self, db: Session, emr_id: int) -> Optional[EMRRecord]:
        """Get EMR by ID"""
        return db.query(EMRRecord).filter(
            EMRRecord.id == emr_id,
            EMRRecord.is_active == True,
        ).first()

    def get_by_visit(self, db: Session, visit_id: int) -> Optional[EMRRecord]:
        """Get EMR by visit ID (primary lookup)"""
        return db.query(EMRRecord).filter(
            EMRRecord.visit_id == visit_id,
            EMRRecord.is_active == True,
        ).first()

    def get_by_patient(
        self, db: Session, patient_id: int, limit: int = 100
    ) -> List[EMRRecord]:
        """Get all EMRs for a patient"""
        return (
            db.query(EMRRecord)
            .filter(
                EMRRecord.patient_id == patient_id,
                EMRRecord.is_active == True,
            )
            .order_by(desc(EMRRecord.created_at))
            .limit(limit)
            .all()
        )

    def get_history(
        self, db: Session, emr_id: int, limit: int = 50
    ) -> List[EMRRevision]:
        """Get revision history for EMR"""
        return (
            db.query(EMRRevision)
            .filter(EMRRevision.emr_id == emr_id)
            .order_by(desc(EMRRevision.version))
            .limit(limit)
            .all()
        )

    def get_revision(
        self, db: Session, emr_id: int, version: int
    ) -> Optional[EMRRevision]:
        """Get specific revision"""
        return db.query(EMRRevision).filter(
            EMRRevision.emr_id == emr_id,
            EMRRevision.version == version,
        ).first()

    # ==========================================================================
    # WRITE Operations
    # ==========================================================================

    def save(
        self,
        db: Session,
        visit_id: int,
        data: Dict[str, Any],
        user_id: int,
        row_version: int = 0,
        client_session_id: Optional[str] = None,
        is_draft: bool = True,
    ) -> EMRRecord:
        """
        Save EMR with versioning and optimistic locking.
        
        Args:
            visit_id: Visit ID (primary anchor)
            data: Complete clinical data
            user_id: Current user ID
            row_version: Expected row version (for optimistic locking)
            client_session_id: Client session UUID (for smart conflict resolution)
            is_draft: Whether this is a draft save
            
        Returns:
            Updated EMRRecord
            
        Raises:
            ConcurrencyError: If row_version mismatch and different user
        """
        existing = self.get_by_visit(db, visit_id)

        if existing:
            return self._update_emr(
                db, existing, data, user_id, row_version, client_session_id, is_draft
            )
        else:
            return self._create_emr(db, visit_id, data, user_id, client_session_id)

    def _create_emr(
        self,
        db: Session,
        visit_id: int,
        data: Dict[str, Any],
        user_id: int,
        client_session_id: Optional[str] = None,
    ) -> EMRRecord:
        """Create new EMR"""
        # Get patient_id from visit
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise ValueError(f"Visit {visit_id} not found")

        # Extract materialized fields
        diagnosis_main, icd10_code = self._extract_materialized_fields(data)

        # Create EMR
        emr = EMRRecord(
            patient_id=visit.patient_id,
            visit_id=visit_id,
            version=1,
            data=data,
            diagnosis_main=diagnosis_main,
            icd10_code=icd10_code,
            status="draft",
            created_by=user_id,
            created_at=datetime.utcnow(),
            row_version=1,
            last_client_session_id=client_session_id,
        )
        db.add(emr)
        db.flush()  # Get ID

        # Create initial revision
        revision = EMRRevision(
            emr_id=emr.id,
            version=1,
            data=data,
            change_type="created",
            change_summary="Initial creation",
            created_by=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(revision)

        # Audit log
        self._log_action(
            db,
            emr_id=emr.id,
            patient_id=emr.patient_id,
            visit_id=visit_id,
            action="create",
            user_id=user_id,
            extra_data={"version": 1},
        )

        db.commit()
        db.refresh(emr)

        logger.info(f"Created EMR {emr.id} for visit {visit_id}")
        return emr

    def _update_emr(
        self,
        db: Session,
        emr: EMRRecord,
        data: Dict[str, Any],
        user_id: int,
        row_version: int,
        client_session_id: Optional[str] = None,
        is_draft: bool = True,
    ) -> EMRRecord:
        """Update existing EMR with optimistic locking"""
        # ✅ CRITICAL: Signed EMRs cannot be modified via save - must use amend
        if emr.status == "signed":
            raise EMRSignedError(
                "Cannot edit signed EMR. Use amend endpoint instead."
            )

        # Optimistic locking check
        if row_version > 0 and emr.row_version != row_version:
            # Smart conflict resolution: same user with same session = OK
            if (
                client_session_id
                and emr.last_client_session_id == client_session_id
                and emr.updated_by == user_id
            ):
                # Same session, same user - autosave conflict, allow
                logger.debug(
                    f"Same-session conflict resolved for EMR {emr.id}"
                )
            else:
                # Different user or session - real conflict
                raise ConcurrencyError(
                    message="EMR was modified by another user",
                    current_version=emr.row_version,
                    your_version=row_version,
                    last_edited_by=emr.updated_by or emr.created_by,
                    last_edited_at=emr.updated_at or emr.created_at,
                )

        # Generate change summary
        change_summary = self._generate_change_summary(emr.data, data)

        # Create revision snapshot before update
        new_version = emr.version + 1
        revision = EMRRevision(
            emr_id=emr.id,
            version=new_version,
            data=data,
            change_type="updated",
            change_summary=change_summary,
            created_by=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(revision)

        # Extract materialized fields
        diagnosis_main, icd10_code = self._extract_materialized_fields(data)

        # Update EMR
        emr.data = data
        emr.version = new_version
        emr.row_version = emr.row_version + 1
        emr.diagnosis_main = diagnosis_main
        emr.icd10_code = icd10_code
        emr.updated_at = datetime.utcnow()
        emr.updated_by = user_id
        emr.last_client_session_id = client_session_id

        if not is_draft and emr.status == "draft":
            emr.status = "in_progress"

        # Audit log
        self._log_action(
            db,
            emr_id=emr.id,
            patient_id=emr.patient_id,
            visit_id=emr.visit_id,
            action="update",
            user_id=user_id,
            extra_data={
                "version": new_version,
                "fields_changed": change_summary,
            },
        )

        db.commit()
        db.refresh(emr)

        logger.info(f"Updated EMR {emr.id} to version {new_version}")
        return emr

    def sign(
        self,
        db: Session,
        visit_id: int,
        data: Dict[str, Any],
        user_id: int,
        row_version: int,
        client_session_id: Optional[str] = None,
    ) -> EMRRecord:
        """Sign and finalize EMR"""
        emr = self.get_by_visit(db, visit_id)
        if not emr:
            raise EMRNotFoundException(f"EMR for visit {visit_id} not found")

        if emr.status == "signed":
            raise EMRSignedError("EMR is already signed")

        # Save with update first
        emr = self._update_emr(
            db, emr, data, user_id, row_version, client_session_id, is_draft=False
        )

        # Update status to signed
        emr.status = "signed"
        emr.signed_at = datetime.utcnow()
        emr.signed_by = user_id

        # Create signed revision
        revision = EMRRevision(
            emr_id=emr.id,
            version=emr.version,
            data=data,
            change_type="signed",
            change_summary="EMR signed and finalized",
            created_by=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(revision)

        # Audit log
        self._log_action(
            db,
            emr_id=emr.id,
            patient_id=emr.patient_id,
            visit_id=emr.visit_id,
            action="sign",
            user_id=user_id,
            extra_data={"version": emr.version, "signed_at": emr.signed_at.isoformat()},
        )

        db.commit()
        db.refresh(emr)

        # 📜 Learn treatment pattern for personalized clinical memory
        # Only if there's both ICD-10 code and treatment
        self._learn_treatment_pattern(db, user_id, data)

        logger.info(f"Signed EMR {emr.id}")
        return emr

    def _learn_treatment_pattern(
        self,
        db: Session,
        doctor_id: int,
        data: Dict[str, Any],
    ) -> None:
        """
        Обучение шаблонов лечения на подписанном EMR.
        
        Вызывается при успешном подписании EMR.
        Учит шаблоны только если есть ICD-10 код и лечение.
        """
        try:
            icd10_code = data.get("icd10_code") or ""
            
            # Лечение может быть в разных полях
            treatment = data.get("treatment") or ""
            if not treatment:
                medications = data.get("medications", {})
                treatment = medications.get("text", "") if isinstance(medications, dict) else ""
            
            if not icd10_code or not treatment:
                return
            
            # Используем синхронную версию для текущей сессии
            from ..models.doctor_templates import DoctorTreatmentTemplate
            
            normalized = DoctorTreatmentTemplate.normalize_treatment(treatment)
            if not normalized:
                return
            
            treatment_hash = DoctorTreatmentTemplate.compute_hash(normalized)
            
            # Проверяем существующий шаблон
            existing = db.query(DoctorTreatmentTemplate).filter(
                DoctorTreatmentTemplate.doctor_id == str(doctor_id),
                DoctorTreatmentTemplate.treatment_hash == treatment_hash,
            ).first()
            
            if existing:
                existing.usage_count += 1
                existing.last_used_at = datetime.utcnow()
                logger.info(
                    f"[DoctorTemplates] Updated: doctor={doctor_id}, "
                    f"icd10={icd10_code}, usage={existing.usage_count}"
                )
            else:
                import uuid
                template = DoctorTreatmentTemplate(
                    id=str(uuid.uuid4()),
                    doctor_id=str(doctor_id),
                    icd10_code=icd10_code,
                    treatment_text=normalized,
                    treatment_hash=treatment_hash,
                    usage_count=1,
                    last_used_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                db.add(template)
                logger.info(
                    f"[DoctorTemplates] Created: doctor={doctor_id}, "
                    f"icd10={icd10_code}"
                )
            
            db.commit()
            
        except Exception as e:
            logger.warning(f"[DoctorTemplates] Error learning pattern: {e}")
            # Don't fail signing on template error

    def amend(
        self,
        db: Session,
        visit_id: int,
        data: Dict[str, Any],
        reason: str,
        user_id: int,
        row_version: int,
    ) -> EMRRecord:
        """Amend a signed EMR (requires reason)"""
        emr = self.get_by_visit(db, visit_id)
        if not emr:
            raise EMRNotFoundException(f"EMR for visit {visit_id} not found")

        if emr.status != "signed":
            raise ValueError("Can only amend signed EMRs")

        if not reason or len(reason.strip()) < 10:
            raise ValueError("Amendment reason must be at least 10 characters")

        # Optimistic locking
        if emr.row_version != row_version:
            raise ConcurrencyError(
                message="EMR was modified",
                current_version=emr.row_version,
                your_version=row_version,
                last_edited_by=emr.updated_by or emr.created_by,
                last_edited_at=emr.updated_at or emr.created_at,
            )

        # Generate change summary
        change_summary = self._generate_change_summary(emr.data, data)

        # Create amendment revision
        # Note: reason is stored in change_summary for DB compatibility
        new_version = emr.version + 1
        revision = EMRRevision(
            emr_id=emr.id,
            version=new_version,
            data=data,
            change_type="amended",
            change_summary=f"{change_summary} | Reason: {reason}",
            created_by=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(revision)

        # Extract materialized fields
        diagnosis_main, icd10_code = self._extract_materialized_fields(data)

        # Update EMR
        emr.data = data
        emr.version = new_version
        emr.row_version = emr.row_version + 1
        emr.diagnosis_main = diagnosis_main
        emr.icd10_code = icd10_code
        emr.updated_at = datetime.utcnow()
        emr.updated_by = user_id
        emr.status = "amended"

        # Audit log
        self._log_action(
            db,
            emr_id=emr.id,
            patient_id=emr.patient_id,
            visit_id=emr.visit_id,
            action="amend",
            user_id=user_id,
            extra_data={
                "version": new_version,
                "reason": reason,
                "fields_changed": change_summary,
            },
        )

        db.commit()
        db.refresh(emr)

        logger.info(f"Amended EMR {emr.id} with reason: {reason[:50]}...")
        return emr

    def restore(
        self,
        db: Session,
        visit_id: int,
        target_version: int,
        user_id: int,
        reason: Optional[str] = None,
    ) -> EMRRecord:
        """Restore EMR to a specific version"""
        emr = self.get_by_visit(db, visit_id)
        if not emr:
            raise EMRNotFoundException(f"EMR for visit {visit_id} not found")

        # Get target revision
        target_revision = self.get_revision(db, emr.id, target_version)
        if not target_revision:
            raise ValueError(f"Version {target_version} not found")

        # Create restore revision
        new_version = emr.version + 1
        restore_reason = reason or f"Restored to version {target_version}"
        
        revision = EMRRevision(
            emr_id=emr.id,
            version=new_version,
            data=target_revision.data,
            change_type="restored",
            change_summary=f"Restored from version {target_version} | Reason: {restore_reason}",
            created_by=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(revision)

        # Extract materialized fields
        diagnosis_main, icd10_code = self._extract_materialized_fields(
            target_revision.data
        )

        # Update EMR
        emr.data = target_revision.data
        emr.version = new_version
        emr.row_version = emr.row_version + 1
        emr.diagnosis_main = diagnosis_main
        emr.icd10_code = icd10_code
        emr.updated_at = datetime.utcnow()
        emr.updated_by = user_id

        # Audit log
        self._log_action(
            db,
            emr_id=emr.id,
            patient_id=emr.patient_id,
            visit_id=emr.visit_id,
            action="restore",
            user_id=user_id,
            extra_data={
                "from_version": target_version,
                "to_version": new_version,
                "reason": restore_reason,
            },
        )

        db.commit()
        db.refresh(emr)

        logger.info(f"Restored EMR {emr.id} to version {target_version}")
        return emr

    # ==========================================================================
    # Diff / Comparison
    # ==========================================================================

    def get_diff(
        self, db: Session, visit_id: int, version_from: int, version_to: int
    ) -> Dict[str, Any]:
        """Compare two versions and return diff"""
        emr = self.get_by_visit(db, visit_id)
        if not emr:
            raise EMRNotFoundException(f"EMR for visit {visit_id} not found")

        rev_from = self.get_revision(db, emr.id, version_from)
        rev_to = self.get_revision(db, emr.id, version_to)

        if not rev_from or not rev_to:
            raise ValueError("One or both versions not found")

        changes = self._compare_data(rev_from.data, rev_to.data)

        return {
            "emr_id": emr.id,
            "version_from": version_from,
            "version_to": version_to,
            "changes": changes,
            "summary": f"{len(changes)} field(s) changed",
        }

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    def _extract_materialized_fields(
        self, data: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract searchable fields from JSONB data"""
        diagnosis_main = None
        icd10_code = None

        if isinstance(data, dict):
            diagnosis = data.get("diagnosis", {})
            if isinstance(diagnosis, dict):
                diagnosis_main = diagnosis.get("main")
                icd10_code = diagnosis.get("icd10_code")
            elif isinstance(diagnosis, str):
                diagnosis_main = diagnosis[:500] if diagnosis else None

        return diagnosis_main, icd10_code

    def _generate_change_summary(
        self, old_data: Dict[str, Any], new_data: Dict[str, Any]
    ) -> str:
        """Generate human-readable change summary"""
        if not old_data:
            return "Initial data"

        changed_fields = []
        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            if old_val != new_val:
                changed_fields.append(key)

        if not changed_fields:
            return "No changes"

        return f"Changed: {', '.join(changed_fields[:5])}" + (
            f" (+{len(changed_fields) - 5} more)" if len(changed_fields) > 5 else ""
        )

    def _compare_data(
        self, old_data: Dict[str, Any], new_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compare two data dicts and return list of changes"""
        changes = []
        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if key not in old_data:
                changes.append({
                    "field": key,
                    "change_type": "added",
                    "new_value": new_val,
                })
            elif key not in new_data:
                changes.append({
                    "field": key,
                    "change_type": "removed",
                    "old_value": old_val,
                })
            elif old_val != new_val:
                changes.append({
                    "field": key,
                    "change_type": "modified",
                    "old_value": old_val,
                    "new_value": new_val,
                })

        return changes

    def _log_action(
        self,
        db: Session,
        emr_id: int,
        patient_id: int,
        visit_id: int,
        action: str,
        user_id: int,
        user_role: str = "Doctor",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> EMRAuditLog:
        """Create audit log entry"""
        log = EMRAuditLog(
            emr_id=emr_id,
            patient_id=patient_id,
            visit_id=visit_id,
            action=action,
            user_id=user_id,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data,
            timestamp=datetime.utcnow(),
        )
        db.add(log)
        return log

    def log_view(
        self,
        db: Session,
        emr: EMRRecord,
        user_id: int,
        user_role: str = "Doctor",
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log EMR view action with rate-limiting.
        
        Only logs once per 5 minutes per user/emr combination
        to prevent audit log flooding from autosave/polling/reload.
        """
        from datetime import timedelta
        
        # Check if we already logged a view for this user/emr in the last 5 minutes
        rate_limit_minutes = 5
        cutoff_time = datetime.utcnow() - timedelta(minutes=rate_limit_minutes)
        
        recent_view = db.query(EMRAuditLog).filter(
            EMRAuditLog.emr_id == emr.id,
            EMRAuditLog.user_id == user_id,
            EMRAuditLog.action == "view",
            EMRAuditLog.timestamp > cutoff_time,
        ).first()
        
        if recent_view:
            # Already logged a view recently, skip
            logger.debug(
                f"Skipping view log for EMR {emr.id} by user {user_id} (rate-limited)"
            )
            return
        
        # Log the view
        self._log_action(
            db,
            emr_id=emr.id,
            patient_id=emr.patient_id,
            visit_id=emr.visit_id,
            action="view",
            user_id=user_id,
            user_role=user_role,
            ip_address=ip_address,
            extra_data={"version": emr.version},
        )
        db.commit()


# Singleton instance
emr_v2_service = EMRV2Service()
