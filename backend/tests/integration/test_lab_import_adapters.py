from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.clinic import (
    Branch,
    Equipment,
    EquipmentStatus,
    EquipmentType,
)
from app.models.lab import (
    LabEquipmentIntegrationProfile,
    LabEquipmentIntegrationProfileVersion,
    LabReportValue,
)
from app.models.lab_import import LabImportReceipt
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.patient import Patient
from app.services.lab_reporting import LabReportingService

pytestmark = pytest.mark.integration


HL7_MESSAGE = (
    "MSH|^~\\&|SYNTHETIC-ANALYZER|SYNTHETIC-LAB|FC|SYNTHETIC-LAB|"
    "202611271200||ORU^R01|SYNTHETIC-INTEGRATION-1|P|2.5.1\r"
    "PID|1||SYNTHETIC-PATIENT-DO-NOT-READ||Synthetic^Patient\r"
    "OBR|1|SYNTHETIC-PLACER-1|SYNTHETIC-ACCESSION-1\r"
    "SPM|1|SYNTHETIC-SP-1\r"
    "OBX|1|NM|HGB^Synthetic analyte^99SYNTHETIC||12.4|SYNTHETIC-UNIT||H||F\r"
)


def _active_synthetic_profile(
    db_session,
    admin_user,
    *,
    status="ACTIVE",
    specimen_id_source="specimen_id",
    mapping_profile=None,
):
    suffix = uuid4().hex[:12]
    branch = Branch(name="SYNTHETIC Integration Clinic", code=f"SYN-{suffix}")
    db_session.add(branch)
    db_session.flush()
    equipment = Equipment(
        name="SYNTHETIC Analyzer",
        model="SYNTHETIC MODEL",
        serial_number=f"SYN-{suffix}",
        equipment_type=EquipmentType.LABORATORY,
        branch_id=branch.id,
        status=EquipmentStatus.ACTIVE,
    )
    db_session.add(equipment)
    db_session.flush()
    profile = LabEquipmentIntegrationProfile(
        equipment_id=equipment.id,
        device_role="analyzer",
        created_by_user_id=admin_user.id,
    )
    db_session.add(profile)
    db_session.flush()
    version = LabEquipmentIntegrationProfileVersion(
        profile_id=profile.id,
        version_no=1,
        status=status,
        adapter_key="hl7_v2",
        protocol_code="hl7_v2",
        transport_code="file_drop",
        mapping_profile=mapping_profile or {
            "analyte_codes": {"HGB": "hgb"},
            "unit_codes": {"HGB": {"SYNTHETIC-UNIT": "g_per_l"}},
            "flag_codes": {"H": "HIGH"},
            "specimen_id_source": specimen_id_source,
        },
        transport_settings={},
        device_settings={},
        simulator_validation_status="PASS",
        simulator_validated_at=datetime.now(UTC),
        simulator_evidence_ref="test://synthetic-simulator",
        physical_validation_status="PASS" if status == "ACTIVE" else "NOT_RUN",
        physical_validated_at=datetime.now(UTC) if status == "ACTIVE" else None,
        physical_validated_by_user_id=admin_user.id if status == "ACTIVE" else None,
        physical_evidence_ref="test://synthetic-fixture" if status == "ACTIVE" else None,
        created_by_user_id=admin_user.id,
        created_at=datetime.now(UTC),
        activated_at=datetime.now(UTC) if status == "ACTIVE" else None,
    )
    db_session.add(version)
    db_session.commit()
    return version


def _synthetic_report_with_specimen(db_session, *, template_code="cbc_oak"):
    patient = Patient(first_name="SYNTHETIC", last_name="LAB-IMPORT")
    db_session.add(patient)
    db_session.flush()
    service = LabReportingService(db_session)
    template = next(
        item for item in service.list_templates() if item.code == template_code
    )
    report = service.create_instance(
        {"patient_id": patient.id, "template_id": template.id}
    )
    specimen = LabSpecimen(
        order_id=report.order_id,
        barcode="SYNTHETIC-SP-1",
        material_code="SYNTHETIC-MATERIAL",
        container_code="SYNTHETIC-CONTAINER",
        status="accepted",
        revision=1,
        create_request_id=str(uuid4()),
        created_at=datetime.now(UTC),
    )
    db_session.add(specimen)
    db_session.flush()
    db_session.add(
        LabSpecimenAssignment(specimen_id=specimen.id, report_instance_id=report.id)
    )
    db_session.commit()
    return report, specimen


def test_analyzer_import_uses_canonical_receipt_exact_specimen_and_profile_provenance(
    client, db_session, admin_user, admin_auth_headers
):
    version = _active_synthetic_profile(
        db_session,
        admin_user,
        specimen_id_source="accession_id",
        mapping_profile={
            "analyte_codes": {"HBA1C": "hba1c"},
            "unit_codes": {"HBA1C": {"SYNTHETIC-UNIT": "percent"}},
            "flag_codes": {"H": "HIGH"},
            "specimen_id_source": "accession_id",
        },
    )
    report, specimen = _synthetic_report_with_specimen(
        db_session, template_code="hba1c_panel"
    )
    message = HL7_MESSAGE.replace(
        "OBR|1|SYNTHETIC-PLACER-1|SYNTHETIC-ACCESSION-1",
        "OBR|1|SYNTHETIC-PLACER-1|SYNTHETIC-SP-1",
    ).replace(
        "SPM|1|SYNTHETIC-SP-1",
        "SPM|1|SYNTHETIC-SP-2",
    ).replace(
        "HGB^Synthetic analyte^99SYNTHETIC",
        "HBA1C^Synthetic analyte^99SYNTHETIC",
    )

    preview = client.post(
        "/api/v1/lab/imports/analyzer/preview",
        json={
            "profile_version_id": version.id,
            "report_instance_id": report.id,
            "message": message,
        },
        headers=admin_auth_headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.headers["Cache-Control"] == "private, no-store"
    ready = preview.json()["rows"][0]
    assert ready["status"] == "ready", preview.text
    assert "SYNTHETIC-PATIENT-DO-NOT-READ" not in preview.text

    applied = client.post(
        "/api/v1/lab/imports/analyzer",
        json={
            "profile_version_id": version.id,
            "report_instance_id": report.id,
            "message": message,
            "expected_updated_at": ready["updated_at"],
        },
        headers=admin_auth_headers,
    )
    assert applied.status_code == 200
    saved = applied.json()["rows"][0]
    assert saved["status"] == "saved"
    assert saved["receipt_id"]
    result = db_session.scalar(
        select(LabReportValue).where(
            LabReportValue.instance_id == report.id,
            LabReportValue.field_key == "hba1c",
        )
    )
    assert result is not None
    assert result.source_integration_profile_version_id == version.id
    assert result.result_payload["source_specimen_id"] == specimen.id
    assert result.result_payload["import_origin"]["source"] == "analyzer"
    assert result.result_payload["import_origin"]["submitted_analyte_code"] == "HBA1C"
    assert result.result_payload["import_origin"]["source_instrument_flags"] == ["H"]
    receipt = db_session.scalar(
        select(LabImportReceipt).where(LabImportReceipt.source == "analyzer")
    )
    assert receipt is not None

    replay = client.post(
        "/api/v1/lab/imports/analyzer",
        json={
            "profile_version_id": version.id,
            "report_instance_id": report.id,
            "message": message,
            "expected_updated_at": ready["updated_at"],
        },
        headers=admin_auth_headers,
    )
    assert replay.status_code == 200
    assert replay.json()["rows"][0]["status"] == "duplicate"

    changed_payload = client.post(
        "/api/v1/lab/imports/analyzer",
        json={
            "profile_version_id": version.id,
            "report_instance_id": report.id,
            "message": message.replace("12.4", "12.5"),
            "expected_updated_at": ready["updated_at"],
        },
        headers=admin_auth_headers,
    )
    assert changed_payload.status_code == 200
    assert changed_payload.json()["rows"][0]["error_code"] == "message_conflict"


def test_analyzer_import_rejects_draft_profile_and_exact_specimen_mismatch(
    client, db_session, admin_user, admin_auth_headers
):
    draft = _active_synthetic_profile(db_session, admin_user, status="DRAFT")
    report, _ = _synthetic_report_with_specimen(db_session)
    blocked = client.post(
        "/api/v1/lab/imports/analyzer/preview",
        json={
            "profile_version_id": draft.id,
            "report_instance_id": report.id,
            "message": HL7_MESSAGE,
        },
        headers=admin_auth_headers,
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"] == {"code": "analyzer_profile_not_ready"}

    active = _active_synthetic_profile(db_session, admin_user)
    wrong_specimen_message = HL7_MESSAGE.replace(
        "SYNTHETIC-SP-1", "SYNTHETIC-SP-2"
    )
    mismatched = client.post(
        "/api/v1/lab/imports/analyzer/preview",
        json={
            "profile_version_id": active.id,
            "report_instance_id": report.id,
            "message": wrong_specimen_message,
        },
        headers=admin_auth_headers,
    )
    assert mismatched.status_code == 200
    assert mismatched.json()["rows"][0]["error_code"] == "specimen_mismatch"
    assert db_session.scalar(
        select(LabReportValue.id).where(LabReportValue.instance_id == report.id)
    ) is None


def test_analyzer_import_role_is_restricted_to_lab_and_admin(
    client, db_session, admin_user, registrar_auth_headers
):
    version = _active_synthetic_profile(db_session, admin_user)
    report, _ = _synthetic_report_with_specimen(db_session)

    response = client.post(
        "/api/v1/lab/imports/analyzer/preview",
        json={
            "profile_version_id": version.id,
            "report_instance_id": report.id,
            "message": HL7_MESSAGE,
        },
        headers=registrar_auth_headers,
    )
    assert response.status_code == 403
    assert db_session.scalar(select(LabImportReceipt.id)) is None


def test_invalid_analyzer_request_does_not_echo_raw_message(
    client, admin_auth_headers
):
    marker = "SYNTHETIC-PHI-DO-NOT-ECHO"
    response = client.post(
        "/api/v1/lab/imports/analyzer/preview",
        json={"message": marker},
        headers=admin_auth_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "invalid_analyzer_request"}
    assert marker not in response.text
