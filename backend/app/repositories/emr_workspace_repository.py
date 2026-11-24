"""Database access for the EMR workspace."""

from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.crud.lab import patient_lab_results_statement
from app.models.emr_v2 import EMRRecord
from app.models.lab import (
    LabOrder,
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabResult,
)
from app.models.patient import Patient
from app.models.patient_clinical import PatientClinicalRevision
from app.models.visit import Visit


class EMRWorkspaceRepository:
    def __init__(self, db: Session):
        self.db = db

    def visit_and_patient(self, visit_id: int):
        return (
            self.db.query(Visit, Patient)
            .join(Patient, Patient.id == Visit.patient_id)
            .filter(Visit.id == visit_id, Patient.is_deleted.is_not(True))
            .first()
        )

    def lock_patient(self, patient_id: int) -> None:
        # Serialize entry updates and allergy reconciliation for the same patient.
        self.db.query(Patient.id).filter(
            Patient.id == patient_id
        ).with_for_update().one()

    def current_entries(self, patient_id: int) -> list[PatientClinicalRevision]:
        table = PatientClinicalRevision
        latest = (
            self.db.query(table.entry_id, func.max(table.version).label("version"))
            .filter(table.patient_id == patient_id)
            .group_by(table.entry_id)
            .subquery()
        )
        return (
            self.db.query(table)
            .join(
                latest,
                and_(
                    table.entry_id == latest.c.entry_id,
                    table.version == latest.c.version,
                ),
            )
            .filter(table.patient_id == patient_id)
            .order_by(table.recorded_at.desc(), table.id.desc())
            .all()
        )

    def entry_history(
        self, patient_id: int, entry_id: UUID
    ) -> list[PatientClinicalRevision]:
        return (
            self.db.query(PatientClinicalRevision)
            .filter_by(patient_id=patient_id, entry_id=entry_id)
            .order_by(PatientClinicalRevision.version.desc())
            .all()
        )

    def entry_exists(self, entry_id: UUID) -> bool:
        return (
            self.db.query(PatientClinicalRevision.id)
            .filter_by(entry_id=entry_id)
            .first()
            is not None
        )

    def add_entry(self, row: PatientClinicalRevision) -> None:
        self.db.add(row)
        self.db.flush()

    def prior_documents(
        self, visit: Visit, doctor_id: int | None, limit: int, offset: int
    ):
        query = (
            self.db.query(EMRRecord, Visit)
            .join(
                Visit,
                and_(
                    EMRRecord.visit_id == Visit.id,
                    EMRRecord.patient_id == Visit.patient_id,
                ),
            )
            .filter(
                EMRRecord.patient_id == visit.patient_id,
                EMRRecord.visit_id != visit.id,
                EMRRecord.is_active.is_(True),
                EMRRecord.status.in_(("signed", "amended")),
            )
        )
        if visit.visit_date is not None:
            query = query.filter(
                or_(Visit.visit_date.is_(None), Visit.visit_date <= visit.visit_date)
            )
        if doctor_id is not None:
            query = query.filter(Visit.doctor_id == doctor_id)
        return (
            query.order_by(
                Visit.visit_date.desc().nulls_last(),
                EMRRecord.signed_at.desc(),
                EMRRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
            .all()
        )

    def workspace_lab_values(self, patient_id: int, visit_ids: list[int]):
        if not visit_ids:
            return []
        statement = (
            patient_lab_results_statement(patient_id, include_observation=True)
            .add_columns(
                LabReportInstance.visit_id.label("source_visit_id"),
                LabReportInstance.template_version_id,
                LabReportTemplate.name.label("template_name"),
                LabReportTemplateVersion.version_no.label("template_version"),
            )
            .join(
                LabReportTemplateVersion,
                and_(
                    LabReportTemplateVersion.id
                    == LabReportInstance.template_version_id,
                    LabReportTemplateVersion.template_id == LabReportInstance.template_id,
                ),
            )
            .join(LabReportTemplate, LabReportTemplate.id == LabReportInstance.template_id)
            .where(
                LabOrder.visit_id == LabReportInstance.visit_id,
                LabReportInstance.visit_id.in_(visit_ids),
                LabResult.value.is_not(None),
            )
            .order_by(
                LabResult.abnormal.desc(),
                LabReportInstance.finalized_at.desc(),
                LabResult.id,
            )
        )
        return self.db.execute(statement).mappings().all()
