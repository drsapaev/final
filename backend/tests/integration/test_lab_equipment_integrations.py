from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.clinic import Branch, Equipment, EquipmentStatus, EquipmentType
from app.models.lab import (
    LabClinicalConfigurationVersion,
    LabEquipmentIntegrationProfile,
    LabEquipmentIntegrationProfileVersion,
)
from app.models.user import User
from app.services.authentication_service import authentication_service

pytestmark = pytest.mark.integration


SYNTHETIC_HL7 = (
    "MSH|^~\\&|SYNTHETIC-ANALYZER|SYNTHETIC-LAB|FC|SYNTHETIC-LAB|"
    "202611271200||ORU^R01|SYNTHETIC-CHECK-1|P|2.5.1\r"
    "OBR|1|SYNTHETIC-PLACER-1|SYNTHETIC-ACCESSION-1\r"
    "SPM|1|SYNTHETIC-SPECIMEN-1\r"
    "OBX|1|NM|HGB^Synthetic analyte^99SYNTHETIC||12.4|SYNTHETIC-UNIT||H||F\r"
)


def _equipment(db_session):
    suffix = uuid4().hex[:12]
    branch = Branch(name="SYNTHETIC Device Setup", code=f"SYN-{suffix}")
    db_session.add(branch)
    db_session.flush()
    equipment = Equipment(
        name="SYNTHETIC Laboratory Device",
        model="SYNTHETIC MODEL",
        serial_number=f"SYN-{suffix}",
        equipment_type=EquipmentType.LABORATORY,
        branch_id=branch.id,
        status=EquipmentStatus.ACTIVE,
    )
    db_session.add(equipment)
    db_session.commit()
    return equipment


def _lab_user(db_session, label: str) -> User:
    user = User(
        username=f"synthetic_equipment_{label}_{uuid4().hex[:8]}",
        email=None,
        full_name=f"SYNTHETIC Lab {label}",
        hashed_password="not-used-by-this-contract-test",
        role="Lab",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = authentication_service.create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _approved_clinical_configuration(db_session, actor, primary, substitute):
    now = datetime.now(UTC)
    configuration = LabClinicalConfigurationVersion(
        version_no=1,
        status="APPROVED",
        configuration_schema_version=1,
        configuration_snapshot={},
        primary_lab_physician_user_id=primary.id,
        substitute_lab_physician_user_id=substitute.id,
        approved_by_user_id=primary.id,
        approved_role_code="Lab",
        approval_authority_snapshot={
            "actor_user_id": primary.id,
            "assignment": "primary",
            "account_active_at_approval": True,
        },
        created_by_user_id=actor.id,
        created_at=now,
        updated_at=now,
        approved_at=now,
    )
    db_session.add(configuration)
    db_session.commit()
    db_session.refresh(configuration)
    return configuration


def _clinical_configuration_snapshot():
    return {
        "method_instructions": [
            {
                "method_code": "SYNTHETIC-METHOD",
                "method_version": "SYNTHETIC-2",
                "language_code": "en",
                "instruction_text": "Synthetic instruction for approval lifecycle tests.",
                "source_ref": "clinic-document://synthetic/method-2",
            }
        ],
        "reference_intervals": [],
        "critical_values": [],
        "qc_rules": [],
        "not_applicable_reasons": {
            "reference_intervals": "No separate reference interval in this synthetic setup.",
            "critical_values": "No separate critical threshold in this synthetic setup.",
            "qc_rules": "No separate QC rule in this synthetic setup.",
        },
    }


def test_admin_can_configure_versioned_analyzer_and_keep_validation_gates_separate(
    client, db_session, admin_user, admin_auth_headers
):
    primary = _lab_user(db_session, "primary")
    substitute = _lab_user(db_session, "substitute")
    unassigned = _lab_user(db_session, "unassigned")
    configuration = _approved_clinical_configuration(
        db_session, admin_user, primary, substitute
    )
    equipment = _equipment(db_session)
    registered = client.post(
        f"/api/v1/clinic/equipment/{equipment.id}/lab-integration",
        json={"device_role": "analyzer"},
        headers=admin_auth_headers,
    )
    assert registered.status_code == 201
    profile = registered.json()

    created = client.post(
        f"/api/v1/clinic/lab-equipment-integrations/{profile['id']}/versions",
        json={
            "adapter_key": "hl7_v2",
            "protocol_code": "hl7_v2",
            "transport_code": "local_agent",
            "mapping_profile": {
                "analyte_codes": {"HGB": "hgb"},
                "unit_codes": {"HGB": {"SYNTHETIC-UNIT": "g_per_l"}},
                "flag_codes": {"H": "HIGH"},
            },
            "transport_settings": {"agent_id": "synthetic-agent", "channel": "results"},
            "device_settings": {"specimen_id_field": "SPM-2"},
        },
        headers=admin_auth_headers,
    )
    assert created.status_code == 201
    version = created.json()
    assert version["status"] == "DRAFT"
    assert version["simulator_validation_status"] == "NOT_RUN"
    assert version["physical_validation_status"] == "NOT_RUN"

    simulator = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/simulator-check",
        json={"message": SYNTHETIC_HL7},
        headers=admin_auth_headers,
    )
    assert simulator.status_code == 200
    assert simulator.json()["status"] == "PASS"
    refreshed = db_session.get(LabEquipmentIntegrationProfileVersion, version["id"])
    assert refreshed.simulator_validation_status == "PASS"
    assert refreshed.physical_validation_status == "NOT_RUN"

    blocked = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/activate",
        headers=admin_auth_headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "simulator_and_physical_validation_required"

    physical = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/physical-validation",
        json={
            "status": "PASS",
            "evidence_ref": "clinic-evidence://synthetic/physical-check-1",
        },
        headers=admin_auth_headers,
    )
    assert physical.status_code == 200
    assert physical.json()["simulator_validation_status"] == "PASS"
    assert physical.json()["physical_validation_status"] == "PASS"
    before_approval = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/activate",
        headers=admin_auth_headers,
    )
    assert before_approval.status_code == 409
    assert before_approval.json()["detail"]["code"] == "current_lab_physician_approval_required"

    approval_inbox = client.get(
        "/api/v1/clinic/lab-equipment-integration-approvals",
        headers=_auth_headers(substitute),
    )
    assert approval_inbox.status_code == 200
    assert len(approval_inbox.json()) == 1
    assert "transport_settings" not in approval_inbox.json()[0]
    assert "192.0.2.10" not in approval_inbox.text

    unassigned_inbox = client.get(
        "/api/v1/clinic/lab-equipment-integration-approvals",
        headers=_auth_headers(unassigned),
    )
    assert unassigned_inbox.status_code == 200
    assert unassigned_inbox.json() == []
    unassigned_approval = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/clinical-approval",
        headers=_auth_headers(unassigned),
    )
    assert unassigned_approval.status_code == 403
    assert unassigned_approval.json()["detail"]["code"] == (
        "assigned_lab_physician_approval_required"
    )
    clinical_approval = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/clinical-approval",
        headers=_auth_headers(substitute),
    )
    assert clinical_approval.status_code == 200
    assert clinical_approval.json()["clinical_approved_by_user_id"] == substitute.id
    assert clinical_approval.json()["clinical_approval_configuration_version_id"] == configuration.id
    assert clinical_approval.json()["clinical_approval_authority_snapshot"]["assignment"] == "substitute"
    activated = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/activate",
        headers=admin_auth_headers,
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "ACTIVE"
    assert db_session.scalar(
        select(LabEquipmentIntegrationProfile.id).where(
            LabEquipmentIntegrationProfile.equipment_id == equipment.id
        )
    ) == profile["id"]


def test_clinical_approval_is_bound_to_the_configuration_version(
    client, db_session, admin_user, admin_auth_headers
):
    primary = _lab_user(db_session, "stale-primary")
    substitute = _lab_user(db_session, "stale-substitute")
    configuration = _approved_clinical_configuration(
        db_session, admin_user, primary, substitute
    )
    equipment = _equipment(db_session)
    profile = client.post(
        f"/api/v1/clinic/equipment/{equipment.id}/lab-integration",
        json={"device_role": "analyzer"},
        headers=admin_auth_headers,
    ).json()
    version = client.post(
        f"/api/v1/clinic/lab-equipment-integrations/{profile['id']}/versions",
        json={
            "adapter_key": "hl7_v2",
            "protocol_code": "hl7_v2",
            "transport_code": "local_agent",
            "mapping_profile": {
                "analyte_codes": {"HGB": "hgb"},
                "unit_codes": {"HGB": {"SYNTHETIC-UNIT": "g_per_l"}},
            },
            "transport_settings": {"agent_id": "synthetic-agent", "channel": "results"},
            "device_settings": {},
        },
        headers=admin_auth_headers,
    ).json()
    client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/simulator-check",
        json={"message": SYNTHETIC_HL7},
        headers=admin_auth_headers,
    ).raise_for_status()
    client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/physical-validation",
        json={"status": "PASS", "evidence_ref": "clinic-evidence://synthetic/physical-check-stale"},
        headers=admin_auth_headers,
    ).raise_for_status()
    client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/clinical-approval",
        headers=_auth_headers(primary),
    ).raise_for_status()

    next_configuration = client.post(
        "/api/v1/clinic/lab-clinical-configurations",
        json={
            "configuration_snapshot": _clinical_configuration_snapshot(),
            "primary_lab_physician_user_id": primary.id,
            "substitute_lab_physician_user_id": substitute.id,
        },
        headers=admin_auth_headers,
    )
    assert next_configuration.status_code == 201, next_configuration.text
    next_configuration_id = next_configuration.json()["id"]
    submitted = client.post(
        f"/api/v1/clinic/lab-clinical-configurations/{next_configuration_id}/submit",
        headers=admin_auth_headers,
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"/api/v1/clinic/lab-clinical-configurations/{next_configuration_id}/approve",
        headers=_auth_headers(primary),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["id"] != configuration.id

    activated = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version['id']}/activate",
        headers=admin_auth_headers,
    )
    assert activated.status_code == 409
    assert activated.json()["detail"]["code"] == "current_lab_physician_approval_required"


def test_simulator_never_accepts_patient_segments_or_stores_secrets(
    client, db_session, admin_user, admin_auth_headers
):
    equipment = _equipment(db_session)
    profile_response = client.post(
        f"/api/v1/clinic/equipment/{equipment.id}/lab-integration",
        json={"device_role": "analyzer"},
        headers=admin_auth_headers,
    )
    version_response = client.post(
        f"/api/v1/clinic/lab-equipment-integrations/{profile_response.json()['id']}/versions",
        json={
            "adapter_key": "hl7_v2",
            "protocol_code": "hl7_v2",
            "transport_code": "tcp_ip",
            "mapping_profile": {
                "analyte_codes": {"HGB": "hgb"},
                "unit_codes": {"HGB": {"SYNTHETIC-UNIT": "g_per_l"}},
            },
            "transport_settings": {
                "host": "192.0.2.10",
                "port": 2575,
                "token": "SYNTHETIC-SECRET-MUST-NOT-PERSIST",
            },
            "device_settings": {},
        },
        headers=admin_auth_headers,
    )
    assert version_response.status_code == 400
    assert version_response.json()["detail"] == {"code": "credentials_must_not_be_stored"}

    version_response = client.post(
        f"/api/v1/clinic/lab-equipment-integrations/{profile_response.json()['id']}/versions",
        json={
            "adapter_key": "hl7_v2",
            "protocol_code": "hl7_v2",
            "transport_code": "local_agent",
            "mapping_profile": {
                "analyte_codes": {"HGB": "hgb"},
                "unit_codes": {"HGB": {"SYNTHETIC-UNIT": "g_per_l"}},
            },
            "transport_settings": {"agent_id": "synthetic-agent", "channel": "results"},
            "device_settings": {},
        },
        headers=admin_auth_headers,
    )
    version_id = version_response.json()["id"]
    real_segment_payload = SYNTHETIC_HL7.replace(
        "OBR|1|", "PID|1||SYNTHETIC-IDENTIFIER\rOBR|1|"
    )
    rejected = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version_id}/simulator-check",
        json={"message": real_segment_payload},
        headers=admin_auth_headers,
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "synthetic_payload_must_omit_patient_segments"
    assert "SYNTHETIC-IDENTIFIER" not in rejected.text
    stored = db_session.get(LabEquipmentIntegrationProfileVersion, version_id)
    assert stored.simulator_evidence_ref.startswith("synthetic-test://sha256/")
    assert "SYNTHETIC-IDENTIFIER" not in stored.simulator_evidence_ref


def test_only_admin_can_manage_lab_equipment_profiles(
    client, db_session, admin_user, registrar_auth_headers
):
    equipment = _equipment(db_session)
    denied = client.post(
        f"/api/v1/clinic/equipment/{equipment.id}/lab-integration",
        json={"device_role": "analyzer"},
        headers=registrar_auth_headers,
    )
    assert denied.status_code == 403
    assert db_session.scalar(select(LabEquipmentIntegrationProfile.id)) is None


@pytest.mark.parametrize(
    ("role", "transport", "transport_settings", "device_settings", "probe"),
    [
        (
            "printer",
            "file_drop",
            {"path_alias": "synthetic-print-output"},
            {"media_width_mm": 80, "media_height_mm": 200},
            '{"probe_id":"SYNTHETIC-PRINT-1","dimensions_mm":{"width":40,"height":50}}',
        ),
        (
            "label_printer",
            "file_drop",
            {"path_alias": "synthetic-label-output"},
            {
                "label_width_mm": 60,
                "label_height_mm": 40,
                "barcode_symbology": "Code128",
            },
            '{"probe_id":"SYNTHETIC-LABEL-1","dimensions_mm":{"width":50,"height":20},"barcode":{"symbology":"Code128","value":"SYNTHETIC-SPECIMEN-1"}}',
        ),
        (
            "scanner",
            "file_drop",
            {"path_alias": "synthetic-scan-input"},
            {"barcode_symbologies": ["Code128"]},
            "Code128|SYNTHETIC-SPECIMEN-1",
        ),
        (
            "local_agent",
            "local_agent",
            {"agent_id": "synthetic-agent", "channel": "synthetic-results"},
            {},
            '{"probe_id":"SYNTHETIC-AGENT-1","agent_id":"synthetic-agent","channel":"synthetic-results","agent_version":"SYNTHETIC-1"}',
        ),
    ],
)
def test_peripheral_simulator_checks_are_synthetic_and_do_not_claim_physical_acceptance(
    client,
    db_session,
    admin_auth_headers,
    role,
    transport,
    transport_settings,
    device_settings,
    probe,
):
    equipment = _equipment(db_session)
    profile_response = client.post(
        f"/api/v1/clinic/equipment/{equipment.id}/lab-integration",
        json={"device_role": role},
        headers=admin_auth_headers,
    )
    assert profile_response.status_code == 201
    version_response = client.post(
        f"/api/v1/clinic/lab-equipment-integrations/{profile_response.json()['id']}/versions",
        json={
            "adapter_key": "manual",
            "protocol_code": "manual",
            "transport_code": transport,
            "mapping_profile": {},
            "transport_settings": transport_settings,
            "device_settings": device_settings,
        },
        headers=admin_auth_headers,
    )
    assert version_response.status_code == 201, version_response.text
    version_id = version_response.json()["id"]

    checked = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version_id}/simulator-check",
        json={"message": probe},
        headers=admin_auth_headers,
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == "PASS"
    assert checked.json()["result_count"] == 1
    stored = db_session.get(LabEquipmentIntegrationProfileVersion, version_id)
    assert stored.simulator_validation_status == "PASS"
    assert stored.simulator_evidence_ref.startswith("synthetic-test://sha256/")
    assert stored.physical_validation_status == "NOT_RUN"
    assert stored.physical_evidence_ref is None

    blocked = client.post(
        f"/api/v1/clinic/lab-equipment-integration-versions/{version_id}/activate",
        headers=admin_auth_headers,
    )
    assert blocked.status_code == 409


def test_simulator_request_validation_never_echoes_submitted_payload(
    client, admin_auth_headers
):
    marker = "SYNTHETIC-REQUEST-ERROR-ECHO-CHECK"
    rejected = client.post(
        "/api/v1/clinic/lab-equipment-integration-versions/999999/simulator-check",
        json={"message": marker, "unexpected": marker},
        headers=admin_auth_headers,
    )
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": {"code": "simulator_request_invalid"}}
    assert marker not in rejected.text

    oversized_marker = "SYNTHETIC-OVERSIZE-ECHO-CHECK-"
    oversized = client.post(
        "/api/v1/clinic/lab-equipment-integration-versions/999999/simulator-check",
        json={"message": oversized_marker + "x" * 1_000_001},
        headers=admin_auth_headers,
    )
    assert oversized.status_code == 422
    assert oversized.json() == {"detail": {"code": "simulator_request_invalid"}}
    assert oversized_marker not in oversized.text
