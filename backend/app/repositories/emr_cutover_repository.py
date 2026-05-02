"""Repository helpers for EMR v2 hard-cutover migration and verification."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.emr import EMR, Prescription
from app.models.emr_v2 import EMRAuditLog, EMRMigrationLedger, EMRRecord, EMRRevision
from app.models.file_system import File
from app.models.visit import Visit


class EMRCutoverRepository:
    """Encapsulates persistence operations used by the EMR cutover service."""

    def __init__(self, db: Session):
        self.db = db

    def list_legacy_emrs(self, *, limit: int | None = None) -> list[EMR]:
        query = self.db.query(EMR).order_by(EMR.id.asc())
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_legacy_emr(self, legacy_emr_id: int) -> EMR | None:
        return self.db.query(EMR).filter(EMR.id == legacy_emr_id).first()

    def get_ledger(self, legacy_emr_id: int) -> EMRMigrationLedger | None:
        return (
            self.db.query(EMRMigrationLedger)
            .filter(EMRMigrationLedger.legacy_emr_id == legacy_emr_id)
            .first()
        )

    def save_ledger(self, ledger: EMRMigrationLedger) -> EMRMigrationLedger:
        self.db.add(ledger)
        self.db.flush()
        return ledger

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_canonical_emr_by_visit(self, visit_id: int) -> EMRRecord | None:
        return (
            self.db.query(EMRRecord)
            .filter(EMRRecord.visit_id == visit_id, EMRRecord.is_active.is_(True))
            .first()
        )

    def save_canonical_emr(self, emr_record: EMRRecord) -> EMRRecord:
        self.db.add(emr_record)
        self.db.flush()
        return emr_record

    def save_revision(self, revision: EMRRevision) -> EMRRevision:
        self.db.add(revision)
        self.db.flush()
        return revision

    def save_audit_log(self, audit_log: EMRAuditLog) -> EMRAuditLog:
        self.db.add(audit_log)
        self.db.flush()
        return audit_log

    def list_prescriptions_for_rebind(
        self,
        *,
        appointment_id: int | None,
        legacy_emr_id: int | None,
    ) -> list[Prescription]:
        filters = []
        if appointment_id is not None:
            filters.append(Prescription.appointment_id == appointment_id)
        if legacy_emr_id is not None:
            filters.append(Prescription.emr_id == legacy_emr_id)
        if not filters:
            return []
        return self.db.query(Prescription).filter(or_(*filters)).all()

    def list_files_for_rebind(
        self,
        *,
        appointment_id: int | None,
        legacy_emr_id: int | None,
    ) -> list[File]:
        filters = []
        if appointment_id is not None:
            filters.append(File.appointment_id == appointment_id)
        if legacy_emr_id is not None:
            filters.append(File.emr_id == legacy_emr_id)
        if not filters:
            return []
        return self.db.query(File).filter(or_(*filters)).all()

    def list_active_canonical_emrs(self) -> list[EMRRecord]:
        return self.db.query(EMRRecord).filter(EMRRecord.is_active.is_(True)).all()

    def list_revisions(self) -> list[EMRRevision]:
        return self.db.query(EMRRevision).all()

    def list_ledgers(self) -> list[EMRMigrationLedger]:
        return self.db.query(EMRMigrationLedger).all()

    def count_legacy_emrs(self) -> int:
        return self.db.query(EMR).count()

    def count_prescriptions_missing_canonical_refs(self) -> int:
        return (
            self.db.query(Prescription)
            .filter(
                or_(
                    Prescription.appointment_id.isnot(None),
                    Prescription.emr_id.isnot(None),
                ),
                or_(
                    Prescription.visit_id.is_(None),
                    Prescription.emr_record_id.is_(None),
                ),
            )
            .count()
        )

    def count_files_missing_canonical_refs(self) -> int:
        return (
            self.db.query(File)
            .filter(
                or_(
                    File.appointment_id.isnot(None),
                    File.emr_id.isnot(None),
                ),
                or_(
                    File.visit_id.is_(None),
                    File.emr_record_id.is_(None),
                ),
            )
            .count()
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
