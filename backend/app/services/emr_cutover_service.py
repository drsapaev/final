"""EMR v2 hard-cutover migration and verification service."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.emr import EMR
from app.models.emr_v2 import (
    SYSTEM_USER_ID,
    EMRAuditLog,
    EMRMigrationLedger,
    EMRRecord,
    EMRRevision,
)
from app.repositories.emr_cutover_repository import EMRCutoverRepository
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.emr_contract import (
    extract_diagnosis_main,
    extract_icd10_code,
    legacy_emr_to_v2_data,
    normalize_emr_data,
)

MIGRATION_CLIENT_SESSION_ID = "emr-v2-hard-cutover"


class EMRCutoverService:
    """Migrates legacy EMR data into canonical EMR v2 and verifies cutover invariants."""

    def __init__(
        self,
        db: Session,
        repository: EMRCutoverRepository | None = None,
        canonical_visit_service_factory: Callable[[Session], CanonicalVisitService] | None = None,
    ):
        self.db = db
        self.repository = repository or EMRCutoverRepository(db)
        self._canonical_visit_service_factory = canonical_visit_service_factory or CanonicalVisitService

    def migrate_legacy_emrs(
        self,
        *,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> dict:
        if not dry_run and not settings.EMR_LEGACY_WRITE_FREEZE:
            raise ValueError(
                "EMR legacy write freeze must be enabled before running canonical backfill."
            )

        processed = 0
        migrated = 0
        skipped = 0
        failed = 0
        rebound_prescriptions = 0
        rebound_files = 0
        errors: list[dict[str, object]] = []

        for legacy_emr in self.repository.list_legacy_emrs(limit=limit):
            processed += 1
            result = self._migrate_single_legacy_emr(legacy_emr, dry_run=dry_run)

            status = result["status"]
            if status == "migrated":
                migrated += 1
                rebound_prescriptions += int(result.get("rebound_prescriptions", 0))
                rebound_files += int(result.get("rebound_files", 0))
            elif status == "skipped":
                skipped += 1
                rebound_prescriptions += int(result.get("rebound_prescriptions", 0))
                rebound_files += int(result.get("rebound_files", 0))
            else:
                failed += 1
                errors.append(result["error"])

        payload = {
            "success": failed == 0,
            "dry_run": dry_run,
            "processed": processed,
            "migrated": migrated,
            "skipped": skipped,
            "failed": failed,
            "rebound_prescriptions": rebound_prescriptions,
            "rebound_files": rebound_files,
            "errors": errors,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        payload["contract_backfill"] = self._backfill_canonical_contracts(dry_run=dry_run)
        if not dry_run:
            payload["verification"] = self.verify_cutover()
        return payload

    def verify_cutover(self) -> dict:
        legacy_total = self.repository.count_legacy_emrs()
        ledgers = self.repository.list_ledgers()
        active_emrs = self.repository.list_active_canonical_emrs()
        revisions = self.repository.list_revisions()

        ledger_status_counts = Counter(ledger.status for ledger in ledgers)
        active_visit_counts = Counter(emr.visit_id for emr in active_emrs if emr.visit_id is not None)
        revision_version_counts = Counter((revision.emr_id, revision.version) for revision in revisions)

        migrated_ledgers = [
            ledger for ledger in ledgers if ledger.status == "migrated"
        ]
        missing_specialty = 0
        missing_specialty_data = 0
        for emr in active_emrs:
            stored_data = emr.data if isinstance(emr.data, dict) else {}
            specialty = stored_data.get("specialty")
            specialty_data = stored_data.get("specialty_data")
            if not isinstance(specialty, str) or not specialty.strip():
                missing_specialty += 1
            if not isinstance(specialty_data, dict):
                missing_specialty_data += 1

        duplicate_visit_records = sum(
            1 for count in active_visit_counts.values() if count > 1
        )
        duplicate_revision_versions = sum(
            1 for count in revision_version_counts.values() if count > 1
        )
        migrated_revision_count = sum(
            1 for revision in revisions if revision.change_type == "migrated"
        )
        prescriptions_missing_refs = self.repository.count_prescriptions_missing_canonical_refs()
        files_missing_refs = self.repository.count_files_missing_canonical_refs()
        ledger_total = len(ledgers)
        untracked_legacy_rows = max(legacy_total - ledger_total, 0)
        failed_ledgers = ledger_status_counts.get("failed", 0)

        checks = {
            "migration_completeness": {
                "legacy_total": legacy_total,
                "ledger_total": ledger_total,
                "migrated": ledger_status_counts.get("migrated", 0),
                "skipped": ledger_status_counts.get("skipped", 0),
                "failed": failed_ledgers,
                "untracked_legacy_rows": untracked_legacy_rows,
                "migrated_ledgers_with_canonical_emr": sum(
                    1 for ledger in migrated_ledgers if ledger.canonical_emr_id is not None
                ),
                "migrated_ledgers_with_revision": sum(
                    1 for ledger in migrated_ledgers if ledger.migrated_revision_id is not None
                ),
                "migrated_revision_count": migrated_revision_count,
            },
            "canonical_uniqueness": {
                "duplicate_visit_records": duplicate_visit_records,
                "missing_specialty": missing_specialty,
                "missing_specialty_data": missing_specialty_data,
                "duplicate_revision_versions": duplicate_revision_versions,
            },
            "referential_integrity": {
                "prescriptions_missing_canonical_refs": prescriptions_missing_refs,
                "files_missing_canonical_refs": files_missing_refs,
            },
            "cutover_guardrails": {
                "legacy_write_freeze_enabled": settings.EMR_LEGACY_WRITE_FREEZE,
            },
        }

        passed = (
            untracked_legacy_rows == 0
            and failed_ledgers == 0
            and duplicate_visit_records == 0
            and missing_specialty == 0
            and missing_specialty_data == 0
            and duplicate_revision_versions == 0
            and prescriptions_missing_refs == 0
            and files_missing_refs == 0
        )

        return {
            "passed": passed,
            "checks": checks,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _migrate_single_legacy_emr(self, legacy_emr: EMR, *, dry_run: bool) -> dict:
        checksum = self._build_checksum(legacy_emr)
        ledger = self.repository.get_ledger(legacy_emr.id)

        if ledger and ledger.status == "migrated" and ledger.canonical_emr_id:
            rebound_prescriptions, rebound_files = self._rebind_related_artifacts(
                legacy_emr=legacy_emr,
                visit_id=ledger.visit_id,
                canonical_emr_id=ledger.canonical_emr_id,
                dry_run=dry_run,
            )
            return {
                "status": "skipped",
                "rebound_prescriptions": rebound_prescriptions,
                "rebound_files": rebound_files,
            }

        visit_id = None
        patient_id = None

        try:
            visit_id = self._resolve_visit_id(legacy_emr.appointment_id)
            visit = self.repository.get_visit(visit_id)
            patient_id = visit.patient_id if visit else None
            canonical_emr = self.repository.get_canonical_emr_by_visit(visit_id)

            if canonical_emr:
                rebound_prescriptions, rebound_files = self._rebind_related_artifacts(
                    legacy_emr=legacy_emr,
                    visit_id=visit_id,
                    canonical_emr_id=canonical_emr.id,
                    dry_run=dry_run,
                )
                if not dry_run:
                    ledger = self._upsert_ledger(
                        ledger=ledger,
                        legacy_emr=legacy_emr,
                        patient_id=patient_id,
                        visit_id=visit_id,
                        checksum=checksum,
                        status="skipped",
                        canonical_emr_id=canonical_emr.id,
                        migrated_revision_id=None,
                        error_payload={"reason": "canonical_emr_already_exists"},
                    )
                    self.repository.commit()
                return {
                    "status": "skipped",
                    "rebound_prescriptions": rebound_prescriptions,
                    "rebound_files": rebound_files,
                }

            normalized_data = legacy_emr_to_v2_data(
                self._legacy_payload(legacy_emr),
                fallback_specialty=legacy_emr.specialty or "general",
            )

            if dry_run:
                return {
                    "status": "migrated",
                    "rebound_prescriptions": len(
                        self.repository.list_prescriptions_for_rebind(
                            appointment_id=legacy_emr.appointment_id,
                            legacy_emr_id=legacy_emr.id,
                        )
                    ),
                    "rebound_files": len(
                        self.repository.list_files_for_rebind(
                            appointment_id=legacy_emr.appointment_id,
                            legacy_emr_id=legacy_emr.id,
                        )
                    ),
                }

            canonical_emr, revision = self._create_canonical_emr(
                visit_id=visit_id,
                patient_id=patient_id,
                legacy_emr=legacy_emr,
                normalized_data=normalized_data,
            )
            rebound_prescriptions, rebound_files = self._rebind_related_artifacts(
                legacy_emr=legacy_emr,
                visit_id=visit_id,
                canonical_emr_id=canonical_emr.id,
                dry_run=False,
            )
            self._upsert_ledger(
                ledger=ledger,
                legacy_emr=legacy_emr,
                patient_id=patient_id,
                visit_id=visit_id,
                checksum=checksum,
                status="migrated",
                canonical_emr_id=canonical_emr.id,
                migrated_revision_id=revision.id,
                error_payload=None,
            )
            self.repository.commit()
            return {
                "status": "migrated",
                "rebound_prescriptions": rebound_prescriptions,
                "rebound_files": rebound_files,
            }
        except Exception as exc:  # noqa: BLE001
            self.repository.rollback()
            if not dry_run:
                self._upsert_ledger(
                    ledger=self.repository.get_ledger(legacy_emr.id),
                    legacy_emr=legacy_emr,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    checksum=checksum,
                    status="failed",
                    canonical_emr_id=None,
                    migrated_revision_id=None,
                    error_payload={
                        "message": str(exc),
                        "type": exc.__class__.__name__,
                    },
                )
                self.repository.commit()
            return {
                "status": "failed",
                "error": {
                    "legacy_emr_id": legacy_emr.id,
                    "appointment_id": legacy_emr.appointment_id,
                    "message": str(exc),
                    "type": exc.__class__.__name__,
                },
            }

    def _resolve_visit_id(self, appointment_id: int | None) -> int:
        if appointment_id is None:
            raise ValueError("Legacy EMR is missing appointment_id")
        service = self._canonical_visit_service_factory(self.db)
        try:
            return service.resolve_canonical_visit(appointment_id, create_if_missing=True)
        except CanonicalVisitResolutionError as exc:
            raise ValueError(exc.detail) from exc

    def _backfill_canonical_contracts(self, *, dry_run: bool) -> dict:
        repaired = 0
        repaired_emr_ids: list[int] = []

        for emr in self.repository.list_active_canonical_emrs():
            stored_data = emr.data if isinstance(emr.data, dict) else {}
            visit = self.repository.get_visit(emr.visit_id)
            fallback_specialty = "general"
            if visit is not None:
                doctor = getattr(visit, "doctor", None)
                if doctor is not None and getattr(doctor, "specialty", None):
                    fallback_specialty = doctor.specialty
                elif getattr(visit, "department", None):
                    fallback_specialty = visit.department

            normalized_data = normalize_emr_data(
                stored_data,
                fallback_specialty=fallback_specialty,
            )
            if normalized_data == stored_data:
                continue

            repaired += 1
            repaired_emr_ids.append(emr.id)
            if dry_run:
                continue

            emr.data = normalized_data
            emr.diagnosis_main = extract_diagnosis_main(normalized_data)
            emr.icd10_code = extract_icd10_code(normalized_data)
            self.repository.save_canonical_emr(emr)
            self.repository.save_audit_log(
                EMRAuditLog(
                    emr_id=emr.id,
                    patient_id=emr.patient_id,
                    visit_id=emr.visit_id,
                    action="contract_backfill",
                    user_id=SYSTEM_USER_ID,
                    user_role="system",
                    extra_data={
                        "reason": "missing_specialty_contract",
                        "specialty": normalized_data.get("specialty"),
                    },
                )
            )

        if repaired and not dry_run:
            self.repository.commit()

        return {
            "repaired": repaired,
            "emr_ids": repaired_emr_ids,
        }

    def _create_canonical_emr(
        self,
        *,
        visit_id: int,
        patient_id: int | None,
        legacy_emr: EMR,
        normalized_data: dict,
    ) -> tuple[EMRRecord, EMRRevision]:
        if patient_id is None:
            raise ValueError("Resolved visit is missing patient_id")

        created_at = legacy_emr.created_at or datetime.now(UTC)
        updated_at = legacy_emr.updated_at or legacy_emr.saved_at or created_at
        status = "draft" if legacy_emr.is_draft else "in_progress"

        emr_record = EMRRecord(
            patient_id=patient_id,
            visit_id=visit_id,
            version=1,
            data=normalized_data,
            diagnosis_main=extract_diagnosis_main(normalized_data),
            icd10_code=extract_icd10_code(normalized_data),
            status=status,
            created_at=created_at,
            created_by=SYSTEM_USER_ID,
            updated_at=updated_at,
            updated_by=SYSTEM_USER_ID,
            row_version=1,
            last_client_session_id=MIGRATION_CLIENT_SESSION_ID,
        )
        self.repository.save_canonical_emr(emr_record)

        revision = EMRRevision(
            emr_id=emr_record.id,
            version=1,
            data=normalized_data,
            change_type="migrated",
            change_summary=f"Migrated from legacy EMR {legacy_emr.id}",
            created_by=SYSTEM_USER_ID,
            created_at=updated_at,
            client_session_id=MIGRATION_CLIENT_SESSION_ID,
        )
        self.repository.save_revision(revision)

        audit_log = EMRAuditLog(
            emr_id=emr_record.id,
            patient_id=patient_id,
            visit_id=visit_id,
            action="migrate",
            user_id=SYSTEM_USER_ID,
            user_role="system",
            extra_data={
                "legacy_emr_id": legacy_emr.id,
                "legacy_appointment_id": legacy_emr.appointment_id,
            },
            timestamp=updated_at,
        )
        self.repository.save_audit_log(audit_log)
        return emr_record, revision

    def _rebind_related_artifacts(
        self,
        *,
        legacy_emr: EMR,
        visit_id: int | None,
        canonical_emr_id: int | None,
        dry_run: bool,
    ) -> tuple[int, int]:
        rebound_prescriptions = 0
        rebound_files = 0

        for prescription in self.repository.list_prescriptions_for_rebind(
            appointment_id=legacy_emr.appointment_id,
            legacy_emr_id=legacy_emr.id,
        ):
            changed = False
            if visit_id and prescription.visit_id != visit_id:
                if not dry_run:
                    prescription.visit_id = visit_id
                changed = True
            if canonical_emr_id and prescription.emr_record_id != canonical_emr_id:
                if not dry_run:
                    prescription.emr_record_id = canonical_emr_id
                changed = True
            if changed:
                rebound_prescriptions += 1

        for file_obj in self.repository.list_files_for_rebind(
            appointment_id=legacy_emr.appointment_id,
            legacy_emr_id=legacy_emr.id,
        ):
            changed = False
            if visit_id and file_obj.visit_id != visit_id:
                if not dry_run:
                    file_obj.visit_id = visit_id
                changed = True
            if canonical_emr_id and file_obj.emr_record_id != canonical_emr_id:
                if not dry_run:
                    file_obj.emr_record_id = canonical_emr_id
                changed = True
            if changed:
                rebound_files += 1

        return rebound_prescriptions, rebound_files

    def _upsert_ledger(
        self,
        *,
        ledger: EMRMigrationLedger | None,
        legacy_emr: EMR,
        patient_id: int | None,
        visit_id: int | None,
        checksum: str,
        status: str,
        canonical_emr_id: int | None,
        migrated_revision_id: int | None,
        error_payload: dict | None,
    ) -> EMRMigrationLedger:
        ledger = ledger or EMRMigrationLedger(legacy_emr_id=legacy_emr.id)
        ledger.legacy_appointment_id = legacy_emr.appointment_id
        ledger.patient_id = patient_id
        ledger.visit_id = visit_id
        ledger.canonical_emr_id = canonical_emr_id
        ledger.migrated_revision_id = migrated_revision_id
        ledger.status = status
        ledger.source_checksum = checksum
        ledger.attempt_count = (ledger.attempt_count or 0) + 1
        ledger.migrated_at = datetime.now(UTC) if status in {"migrated", "skipped"} else None
        ledger.error_payload = error_payload
        return self.repository.save_ledger(ledger)

    @staticmethod
    def _legacy_payload(legacy_emr: EMR) -> dict:
        return {
            column.name: getattr(legacy_emr, column.name)
            for column in legacy_emr.__table__.columns
        }

    def _build_checksum(self, legacy_emr: EMR) -> str:
        payload = self._legacy_payload(legacy_emr)
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
