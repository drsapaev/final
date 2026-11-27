from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.lab import LabClinicalConfigurationVersion
from app.models.user import User
from app.services.authentication_service import authentication_service
from app.services.lab_reporting_service import LabReportingService

pytestmark = pytest.mark.integration


def _lab_user(db_session, label: str) -> User:
    user = User(
        username=f"synthetic_lab_{label}_{uuid4().hex[:8]}",
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


def _headers(user: User) -> dict[str, str]:
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


def _snapshot():
    return {
        "method_instructions": [
            {
                "method_code": "SYNTHETIC-METHOD",
                "method_version": "SYNTHETIC-1",
                "language_code": "ru",
                "instruction_text": "Synthetic method instruction for contract coverage.",
                "source_ref": "clinic-document://synthetic/method-1",
            }
        ],
        "reference_intervals": [
            {
                "rule_code": "SYNTHETIC-RANGE-1",
                "analyte_code": "SYNTHETIC-ANALYTE",
                "method_code": "SYNTHETIC-METHOD",
                "unit_code": "synthetic_unit",
                "low": 1.0,
                "high": 10.0,
                "source_ref": "clinic-document://synthetic/reference-1",
            }
        ],
        "critical_values": [],
        "qc_rules": [],
        "not_applicable_reasons": {
            "critical_values": "No separate critical threshold in this synthetic profile.",
            "qc_rules": "No instrument-specific QC rule in this synthetic profile.",
        },
    }


def test_clinical_configuration_requires_assigned_lab_physician_and_binds_history(
    client,
    db_session,
    admin_user,
    admin_auth_headers,
    test_patient,
    test_visit,
):
    primary = _lab_user(db_session, "primary")
    substitute = _lab_user(db_session, "substitute")
    unassigned = _lab_user(db_session, "unassigned")
    path = "/api/v1/clinic/lab-clinical-configurations"
    created = client.post(
        path,
        json={
            "configuration_snapshot": _snapshot(),
            "primary_lab_physician_user_id": primary.id,
            "substitute_lab_physician_user_id": substitute.id,
        },
        headers=admin_auth_headers,
    )
    assert created.status_code == 201, created.text
    version_id = created.json()["id"]
    assert created.json()["status"] == "DRAFT"

    submitted = client.post(
        f"{path}/{version_id}/submit", headers=admin_auth_headers
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "PENDING_APPROVAL"

    admin_cannot_approve = client.post(
        f"{path}/{version_id}/approve", headers=admin_auth_headers
    )
    assert admin_cannot_approve.status_code == 403

    unassigned_cannot_approve = client.post(
        f"{path}/{version_id}/approve", headers=_headers(unassigned)
    )
    assert unassigned_cannot_approve.status_code == 403
    assert unassigned_cannot_approve.json()["detail"]["code"] == (
        "assigned_lab_physician_approval_required"
    )

    approved = client.post(
        f"{path}/{version_id}/approve", headers=_headers(primary)
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["approved_by_user_id"] == primary.id
    assert approved.json()["approval_authority_snapshot"]["assignment"] == "primary"

    immutable = client.put(
        f"{path}/{version_id}",
        json={
            "configuration_snapshot": _snapshot(),
            "primary_lab_physician_user_id": primary.id,
            "substitute_lab_physician_user_id": substitute.id,
        },
        headers=admin_auth_headers,
    )
    assert immutable.status_code == 409

    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    instance = service.create_instance(
        {
            "patient_id": test_patient.id,
            "template_id": template.id,
        }
    )
    assert instance.clinical_configuration_version_id == version_id

    # This contract test only needs a finalized source state to exercise revision
    # provenance; the report mutation itself is covered by workflow tests.
    instance.status = "FINALIZED"
    instance.finalized_at = datetime.now(UTC)
    db_session.commit()
    revision_author = _lab_user(db_session, "correction-author")
    revision = service.revise(
        instance.id,
        actor_user_id=revision_author.id,
        expected_updated_at=instance.updated_at.isoformat(),
        reason="SYNTHETIC correction",
    )
    assert revision.clinical_configuration_version_id == version_id
    assert db_session.get(LabClinicalConfigurationVersion, version_id).status == "APPROVED"


def test_clinical_configuration_rejects_inactive_or_non_lab_assignees(
    client, db_session, admin_auth_headers, registrar_user
):
    inactive = _lab_user(db_session, "inactive")
    inactive.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/clinic/lab-clinical-configurations",
        json={
            "configuration_snapshot": {},
            "primary_lab_physician_user_id": inactive.id,
        },
        headers=admin_auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "assigned_lab_physician_must_be_active"

    denied = client.post(
        "/api/v1/clinic/lab-clinical-configurations",
        json={"configuration_snapshot": {}},
        headers=_headers(registrar_user),
    )
    assert denied.status_code == 403


def test_report_without_approved_clinic_configuration_cannot_be_released(
    client, db_session, test_patient, admin_user, admin_auth_headers
):
    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_user_id=admin_user.id,
    )

    detail = client.get(
        f"/api/v1/lab/report-instances/{report.id}",
        headers=admin_auth_headers,
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert "clinical_configuration_required" in payload["release_holds"]
    assert "finalize" not in payload["available_actions"]
    assert "submit_review" not in payload["available_actions"]

    summary = client.get(
        "/api/v1/lab/report-instances",
        headers=admin_auth_headers,
        params={"patient_id": test_patient.id},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()[0]["can_finalize"] is False

    blocked = client.post(
        f"/api/v1/lab/report-instances/{report.id}/finalize",
        headers=admin_auth_headers,
    )
    assert blocked.status_code == 409
    assert "Approved clinic clinical configuration" in blocked.json()["detail"]
    db_session.refresh(report)
    assert report.status == "DRAFT"
    assert report.finalized_at is None
