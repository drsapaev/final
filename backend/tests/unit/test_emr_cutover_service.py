from __future__ import annotations

from datetime import date

import pytest

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.emr import EMR, Prescription
from app.models.emr_v2 import EMRMigrationLedger, EMRRecord, EMRRevision
from app.models.file_system import File, FileStatus, FileType
from app.services.emr_cutover_service import EMRCutoverService


@pytest.mark.unit
class TestEMRCutoverService:
    def test_migrate_legacy_emr_creates_canonical_record_and_rebinds_refs(
        self,
        db_session,
        test_patient,
        test_doctor,
        test_visit,
        admin_user,
        monkeypatch,
    ):
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=test_visit.visit_date,
            appointment_time=test_visit.visit_time,
            status="scheduled",
            notes="legacy appointment",
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        legacy_emr = EMR(
            appointment_id=appointment.id,
            complaints="Chest pain",
            anamnesis="Several days of symptoms",
            examination="Stable",
            diagnosis="Angina",
            icd10="I20.9",
            recommendations="Observation",
            specialty="cardio",
            is_draft=False,
        )
        db_session.add(legacy_emr)
        db_session.commit()
        db_session.refresh(legacy_emr)

        prescription = Prescription(
            appointment_id=appointment.id,
            emr_id=legacy_emr.id,
            medications={"items": ["ASA"]},
            is_draft=False,
        )
        file_obj = File(
            filename="legacy-note.txt",
            original_filename="legacy-note.txt",
            file_path="/tmp/legacy-note.txt",
            file_size=128,
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            status=FileStatus.READY,
            owner_id=admin_user.id,
            patient_id=test_patient.id,
            appointment_id=appointment.id,
            emr_id=legacy_emr.id,
        )
        db_session.add(prescription)
        db_session.add(file_obj)
        db_session.commit()

        monkeypatch.setattr(settings, "EMR_LEGACY_WRITE_FREEZE", True, raising=False)

        result = EMRCutoverService(db_session).migrate_legacy_emrs()

        assert result["success"] is True
        assert result["migrated"] == 1
        assert result["failed"] == 0
        assert result["rebound_prescriptions"] == 1
        assert result["rebound_files"] == 1

        canonical_emr = (
            db_session.query(EMRRecord)
            .filter(EMRRecord.visit_id == test_visit.id)
            .one()
        )
        migrated_revision = (
            db_session.query(EMRRevision)
            .filter(EMRRevision.emr_id == canonical_emr.id, EMRRevision.change_type == "migrated")
            .one()
        )
        ledger = (
            db_session.query(EMRMigrationLedger)
            .filter(EMRMigrationLedger.legacy_emr_id == legacy_emr.id)
            .one()
        )
        rebound_prescription = (
            db_session.query(Prescription).filter(Prescription.id == prescription.id).one()
        )
        rebound_file = db_session.query(File).filter(File.id == file_obj.id).one()

        assert canonical_emr.data["specialty"] == "cardiology"
        assert isinstance(canonical_emr.data["specialty_data"], dict)
        assert canonical_emr.status == "in_progress"
        assert migrated_revision.version == 1
        assert ledger.status == "migrated"
        assert ledger.canonical_emr_id == canonical_emr.id
        assert ledger.migrated_revision_id == migrated_revision.id
        assert rebound_prescription.visit_id == test_visit.id
        assert rebound_prescription.emr_record_id == canonical_emr.id
        assert rebound_file.visit_id == test_visit.id
        assert rebound_file.emr_record_id == canonical_emr.id
        assert result["verification"]["passed"] is True

    def test_live_migration_requires_write_freeze_but_dry_run_does_not(
        self,
        db_session,
        test_patient,
        test_doctor,
        test_visit,
        monkeypatch,
    ):
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="09:30",
            status="scheduled",
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        legacy_emr = EMR(
            appointment_id=appointment.id,
            complaints="Itching",
            diagnosis="Dermatitis",
            specialty="derma",
            is_draft=True,
        )
        db_session.add(legacy_emr)
        db_session.commit()

        monkeypatch.setattr(settings, "EMR_LEGACY_WRITE_FREEZE", False, raising=False)
        service = EMRCutoverService(db_session)

        with pytest.raises(ValueError):
            service.migrate_legacy_emrs()

        dry_run_result = service.migrate_legacy_emrs(dry_run=True)

        assert dry_run_result["success"] is True
        assert dry_run_result["processed"] == 1
        assert dry_run_result["migrated"] == 1
