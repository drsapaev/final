"""The managed path never publishes a version the reviewer did not inspect."""

from copy import deepcopy
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core.config import settings
from app.crud import audit as audit_crud
from app.models.lab import LabClinicalConfigurationVersion, LabOrderTest
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.role_permission import Permission, Role, user_roles_table
from app.models.service import Service
from app.models.user import User
from app.models.visit import VisitService
from app.schemas.lab_release import LabReportQCIn
from app.services.authentication_service import authentication_service
from app.services.lab_report_pdf_service import lab_report_pdf_service
from app.services.lab_reporting_service import (
    LabReportingDomainError,
    LabReportingService,
)


def _staff(db, name, permissions):
    actor = User(
        username=f"SYNTHETIC-{name}",
        full_name=f"SYNTHETIC {name}",
        hashed_password=f"unusable-{uuid4()}",
        role="Lab",
        is_active=True,
    )
    db.add(actor)
    db.flush()
    if permissions:
        role = Role(
            name=f"synthetic-{name}",
            display_name=f"SYNTHETIC {name}",
            permissions=permissions,
        )
        db.add(role)
        db.flush()
        db.execute(user_roles_table.insert().values(user_id=actor.id, role_id=role.id))
    return actor


def _auth(actor):
    token = authentication_service.create_access_token(
        {
            "sub": str(actor.id),
            "username": actor.username,
            "role": actor.role,
            "is_active": actor.is_active,
            "is_superuser": actor.is_superuser,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _accepted_specimen(
    db, report, barcode, *, replaces_specimen_id=None, material_code="synthetic-blood",
):
    specimen = LabSpecimen(
        order_id=report.order_id,
        barcode=barcode,
        material_code=material_code,
        container_code="synthetic-tube",
        status="accepted",
        revision=4,
        replaces_specimen_id=replaces_specimen_id,
        create_request_id=str(uuid4()),
        created_at=datetime.now(UTC),
    )
    db.add(specimen)
    db.flush()
    db.add(LabSpecimenAssignment(specimen_id=specimen.id, report_instance_id=report.id))
    db.commit()
    return specimen


def _approved_clinical_configuration(db, primary, substitute):
    approved_at = datetime.now(UTC)
    version = LabClinicalConfigurationVersion(
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
            "actor_role_code": "Lab",
            "assignment": "primary",
        },
        created_by_user_id=primary.id,
        approved_at=approved_at,
    )
    db.add(version)
    db.commit()
    return version


@pytest.mark.unit
def test_configuration_bound_review_and_release_require_assigned_active_lab_physician(
    db_session, test_patient, monkeypatch
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "LAB_RELEASE_REQUIRE_DISTINCT_REVIEWER", True)
    review_permission = Permission(name="lab:review", codename="lab:review")
    release_permission = Permission(name="lab:release", codename="lab:release")
    qc_permission = Permission(name="lab:qc", codename="lab:qc")
    entrant = _staff(db_session, "configured-entry", [])
    primary = _staff(
        db_session,
        "configured-primary",
        [review_permission, release_permission, qc_permission],
    )
    substitute = _staff(
        db_session,
        "configured-substitute",
        [review_permission, release_permission],
    )
    unassigned = _staff(
        db_session,
        "configured-unassigned",
        [review_permission, release_permission],
    )
    db_session.commit()
    configuration = _approved_clinical_configuration(db_session, primary, substitute)

    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_name=entrant.full_name,
        actor_user_id=entrant.id,
    )
    assert report.clinical_configuration_version_id == configuration.id
    specimen = _accepted_specimen(db_session, report, "SYNTHETIC-AUTHORITY")
    report, _ = service.bulk_upsert_values(
        report.id,
        [
            {"field_key": "hgb", "value_text": "135"},
            {"field_key": "wbc", "value_text": "5.2"},
        ],
        expected_updated_at=report.updated_at.isoformat(),
        actor_user_id=entrant.id,
    )
    report = service.record_report_qc(
        report.id,
        actor_user_id=primary.id,
        command=LabReportQCIn(
            expected_updated_at=report.updated_at.isoformat(),
            status="accepted",
            method="SYNTHETIC-QC",
            series_ref="SYNTHETIC-AUTHORITY-QC",
        ),
    )
    report = service.submit_for_review(
        report.id,
        actor_user_id=entrant.id,
        expected_updated_at=report.updated_at.isoformat(),
    )

    assert "review" not in service.instance_available_actions(report, unassigned.id)
    assert "review" in service.instance_available_actions(report, primary.id)
    with pytest.raises(
        LabReportingDomainError, match="Assigned active laboratory physician"
    ):
        service.review_report(
            report.id,
            actor_user_id=unassigned.id,
            expected_updated_at=report.updated_at.isoformat(),
        )

    primary.is_active = False
    db_session.commit()
    assert "review" not in service.instance_available_actions(report, primary.id)
    with pytest.raises(
        LabReportingDomainError, match="workflow access denied"
    ):
        service.review_report(
            report.id,
            actor_user_id=primary.id,
            expected_updated_at=report.updated_at.isoformat(),
        )
    primary.is_active = True
    db_session.commit()

    report = service.review_report(
        report.id,
        actor_user_id=primary.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert "finalize" not in service.instance_available_actions(report, unassigned.id)
    assert "finalize" in service.instance_available_actions(report, substitute.id)
    with pytest.raises(
        LabReportingDomainError, match="Assigned active laboratory physician"
    ):
        service.finalize(
            report.id,
            actor_user_id=unassigned.id,
            expected_updated_at=report.updated_at.isoformat(),
        )
    released = service.finalize(
        report.id,
        actor_user_id=substitute.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert released.status == "FINALIZED"
    assert released.signer_snapshot["approver_name"] == substitute.full_name
    assert specimen.status == "accepted"


@pytest.mark.unit
def test_clinic_configuration_automatically_enables_managed_release(
    db_session, test_patient, monkeypatch
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", False)
    primary = _staff(db_session, "legacy-config-primary", [])
    substitute = _staff(db_session, "legacy-config-substitute", [])
    db_session.commit()
    _approved_clinical_configuration(db_session, primary, substitute)

    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_user_id=primary.id,
    )
    assert report.clinical_configuration_version_id is not None
    assert report.managed_release is True
    assert "finalize" not in service.instance_available_actions(report, primary.id)


@pytest.mark.unit
def test_managed_release_versions_permissions_and_correction_history(
    db_session, test_patient, monkeypatch
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "LAB_RELEASE_REQUIRE_DISTINCT_REVIEWER", True)
    permissions = [
        Permission(name=code, codename=code)
        for code in ("lab:review", "lab:release", "lab:qc")
    ]
    entrant = _staff(db_session, "lab-entered", [permissions[0]])
    editor = _staff(db_session, "lab-draft-editor", permissions)
    reviewer = _staff(db_session, "lab-reviewed", permissions)
    no_grant = _staff(db_session, "lab-no-grant", [])
    db_session.commit()
    _approved_clinical_configuration(db_session, reviewer, entrant)

    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_name=entrant.full_name,
        actor_user_id=entrant.id,
    )
    assert report.managed_release
    report_id = report.id
    actor_id = entrant.id
    reviewer_id = reviewer.id
    no_grant_id = no_grant.id
    initial_version = report.updated_at.isoformat()
    with pytest.raises(
        LabReportingDomainError, match="requires a reviewed report"
    ) as premature:
        service.finalize(
            report_id, actor_user_id=reviewer_id, expected_updated_at=initial_version
        )
    assert premature.value.status_code == 409
    assert service.report_release_holds(report) == ["specimen_required", "qc_missing"]
    specimen = _accepted_specimen(db_session, report, "SYNTHETIC-RELEASE")

    report, updated = service.bulk_upsert_values(
        report_id,
        [
            {"field_key": "hgb", "value_text": "100"},
            {"field_key": "wbc", "value_text": "5.2"},
        ],
        expected_updated_at=initial_version,
        actor_user_id=actor_id,
    )
    assert {value.result_payload["source_specimen_id"] for value in updated} == {
        specimen.id
    }
    report = service.update_instance(
        report_id,
        {
            "signer_snapshot": {"lab_technician_name": editor.full_name},
            "branding_snapshot": {"clinic_name": "SYNTHETIC Branding"},
            "study_date": date(2026, 11, 24),
        },
        expected_updated_at=report.updated_at.isoformat(),
        actor_user_id=editor.id,
    )
    report, _ = service.bulk_upsert_values(
        report_id,
        [{"field_key": "hgb", "value_text": "100", "comment": "SYNTHETIC comment"}],
        expected_updated_at=report.updated_at.isoformat(),
        actor_user_id=editor.id,
    )
    report, _ = service.bulk_upsert_values(
        report_id,
        [{"field_key": "hgb", "value_text": "100", "comment": "SYNTHETIC comment"}],
        expected_updated_at=report.updated_at.isoformat(),
        actor_user_id=reviewer_id,
    )
    assert [
        event.actor_user_id for event in service.workflow_history(report_id)
        if event.kind == "entered"
    ] == [actor_id]
    draft_audit = audit_crud.list_logs(
        db_session,
        action="LAB_REPORT_DRAFT_EDITED",
        entity_type="lab_report",
        entity_id=report_id,
    )
    assert [entry.actor_user_id for entry in draft_audit] == [editor.id, editor.id]
    assert all(entry.payload is None for entry in draft_audit)
    assert service.report_release_holds(report) == ["qc_missing"]
    draft_token = report.updated_at.isoformat()
    report = service.record_report_qc(
        report_id,
        actor_user_id=reviewer_id,
        command=LabReportQCIn(
            expected_updated_at=draft_token,
            status="accepted",
            method="SYNTHETIC",
            series_ref="SYNTHETIC-QC",
        ),
    )
    report = service.submit_for_review(
        report_id,
        actor_user_id=actor_id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert report.status == "IN_REVIEW"
    submitted_version = report.updated_at.isoformat()
    assert "review" not in service.instance_available_actions(report, actor_id)
    assert "review" not in service.instance_available_actions(report, editor.id)
    assert "review" not in service.instance_available_actions(report, no_grant_id)
    assert "review" in service.instance_available_actions(report, reviewer_id)
    with pytest.raises(LabReportingDomainError, match="workflow permission required"):
        service.review_report(
            report_id, actor_user_id=no_grant_id, expected_updated_at=submitted_version
        )
    with pytest.raises(LabReportingDomainError, match="reviewer who did not enter"):
        service.review_report(
            report_id, actor_user_id=actor_id, expected_updated_at=submitted_version
        )
    with pytest.raises(LabReportingDomainError, match="Return the report to draft"):
        service.bulk_upsert_values(
            report_id, [], expected_updated_at=submitted_version, actor_user_id=actor_id
        )

    report = service.review_report(
        report_id, actor_user_id=reviewer_id, expected_updated_at=submitted_version
    )
    assert report.status == "REVIEWED"
    reviewed_version = report.updated_at.isoformat()
    with pytest.raises(LabReportingDomainError) as stale:
        service.finalize(
            report_id, actor_user_id=reviewer_id, expected_updated_at=submitted_version
        )
    assert stale.value.status_code == 409

    # Accepted can change after review without the report token changing.
    specimen.revision += 1
    db_session.commit()
    with pytest.raises(LabReportingDomainError, match="Specimen or QC changed"):
        service.finalize(
            report_id, actor_user_id=reviewer_id, expected_updated_at=reviewed_version
        )

    report = service.return_report_to_draft(
        report_id,
        actor_user_id=reviewer_id,
        expected_updated_at=reviewed_version,
        reason="SYNTHETIC specimen evidence changed",
    )
    report = service.submit_for_review(
        report_id,
        actor_user_id=actor_id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    report = service.review_report(
        report_id,
        actor_user_id=reviewer_id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    token = report.updated_at.isoformat()
    released = service.finalize(
        report_id, actor_user_id=reviewer_id, expected_updated_at=token
    )
    assert released.status == "FINALIZED"
    assert released.signer_snapshot["lab_technician_name"] == entrant.full_name
    assert released.signer_snapshot["approver_name"] == reviewer.full_name
    released_version = released.updated_at.isoformat()
    repeated = service.finalize(
        report_id, actor_user_id=reviewer_id, expected_updated_at=token
    )
    assert repeated.updated_at.isoformat() == released_version
    events = service.workflow_history(report_id)
    assert [item.actor_user_id for item in events if item.kind == "finalized"] == [
        reviewer_id
    ]

    with pytest.raises(LabReportingDomainError, match="Provide a reason"):
        service.revise(
            report_id, actor_user_id=actor_id, expected_updated_at=released_version
        )
    revision = service.revise(
        report_id,
        actor_user_id=actor_id,
        expected_updated_at=released_version,
        reason="SYNTHETIC correction",
    )
    assert revision.supersedes_instance_id == report_id
    assert revision.status == "DRAFT"
    assert "specimen_result_mismatch" in service.report_release_holds(revision)
    assert {
        value.result_payload["source_specimen_id"] for value in revision.values
    } == {specimen.id}
    revision_event = service.workflow_history(revision.id)[0]
    assert revision_event.kind == "revision_created"
    assert revision_event.reason == "SYNTHETIC correction"
    assert revision_event.actor_user_id == actor_id
    assert revision_event.occurred_at is not None
    same_revision = service.revise(
        report_id,
        actor_user_id=actor_id,
        expected_updated_at=released_version,
        reason="SYNTHETIC correction",
    )
    assert same_revision.id == revision.id
    assert service.get_instance(report_id).status == "FINALIZED"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("qc_status", "mixed_material", "expected_hold"),
    [
        (None, False, "qc_missing"),
        ("rejected", False, "qc_rejected"),
        ("not_applicable", True, "specimen_context_ambiguous"),
        ("not_applicable", False, None),
    ],
)
def test_managed_review_surfaces_qc_and_material_holds(
    client, db_session, test_patient, monkeypatch, qc_status, mixed_material, expected_hold,
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "LAB_RELEASE_REQUIRE_DISTINCT_REVIEWER", True)
    entrant = _staff(db_session, "managed-qc-entry", [])
    reviewer = _staff(
        db_session, "managed-qc-review",
        [Permission(name=code, codename=code) for code in ("lab:review", "lab:qc")],
    )
    _approved_clinical_configuration(db_session, reviewer, entrant)
    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_user_id=entrant.id,
    )
    _accepted_specimen(db_session, report, "SYNTHETIC-QC-PRIMARY")
    report, _ = service.bulk_upsert_values(
        report.id,
        [
            {"field_key": "hgb", "value_text": "135"},
            {"field_key": "wbc", "value_text": "5.2"},
        ],
        expected_updated_at=report.updated_at.isoformat(), actor_user_id=entrant.id,
    )
    if mixed_material:
        _accepted_specimen(
            db_session, report, "SYNTHETIC-QC-OTHER", material_code="synthetic-serum",
        )
    path = f"/api/v1/lab/report-instances/{report.id}"
    headers = _auth(reviewer)
    if qc_status:
        payload = {"expected_updated_at": report.updated_at.isoformat(), "status": qc_status}
        if qc_status == "not_applicable":
            undocumented = client.post(f"{path}/qc", headers=headers, json=payload)
            assert undocumented.status_code == 422, undocumented.text
        else:
            payload.update(method="SYNTHETIC-QC", series_ref="SYNTHETIC-LOT")
        recorded = client.post(
            f"{path}/qc", headers=headers,
            json={**payload, "reason": "SYNTHETIC disposition"},
        )
        assert recorded.status_code == 200, recorded.text
        report = service.get_instance(report.id)
    report = service.submit_for_review(
        report.id, expected_updated_at=report.updated_at.isoformat(), actor_user_id=entrant.id,
    )
    current = client.get(path, headers=headers)
    assert current.status_code == 200, current.text
    saved = current.json()
    assert saved["release_holds"] == ([expected_hold] if expected_hold else [])
    assert "return_to_draft" in saved["available_actions"]
    if qc_status:
        qc, = [event for event in saved["workflow_events"] if event["kind"] == "qc_recorded"]
        assert qc["reason"] == "SYNTHETIC disposition"
        assert qc["evidence"]["qc"]["status"] == qc_status
    command = {"expected_updated_at": saved["updated_at"]}
    if expected_hold is None:
        denied = client.post(f"{path}/review", headers=_auth(entrant), json=command)
        assert denied.status_code == 403, denied.text
        forged = client.post(
            f"{path}/review", headers=_auth(entrant),
            json={**command, "actor_user_id": reviewer.id},
        )
        assert forged.status_code == 422, forged.text
    reviewed = client.post(
        f"{path}/review", headers=headers, json=command,
    )
    if expected_hold:
        assert reviewed.status_code == 409, reviewed.text
        assert reviewed.json()["detail"] == expected_hold
    else:
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["status"] == "REVIEWED"
        reviewed_event, = [
            event for event in reviewed.json()["workflow_events"] if event["kind"] == "reviewed"
        ]
        assert reviewed_event["actor_user_id"] == reviewer.id


@pytest.mark.unit
@pytest.mark.parametrize(("instrument_warning", "hold"), [
    (True, "instrument_warning"),
    (False, "unusual_change"),
])
def test_managed_review_requires_a_recorded_disposition_for_manual_findings(
    client, db_session, test_patient, monkeypatch, instrument_warning, hold,
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    entered_by = _staff(db_session, "finding-entry", [])
    reviewer = _staff(db_session, "finding-review", [
        Permission(name=code, codename=code) for code in ("lab:review", "lab:qc")
    ])
    _approved_clinical_configuration(db_session, reviewer, entered_by)
    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id}, actor_user_id=entered_by.id,
    )
    _accepted_specimen(db_session, report, "SYNTHETIC-MANUAL-REVIEW")
    report, _ = service.bulk_upsert_values(
        report.id, [{"field_key": "hgb", "value_text": "135"}, {"field_key": "wbc", "value_text": "5.2"}],
        expected_updated_at=report.updated_at.isoformat(), actor_user_id=entered_by.id,
    )
    if instrument_warning:
        value = next(item for item in report.values if item.field_key == "hgb")
        value.result_payload = {**value.result_payload, "import_origin": {
            "source": "csv", "message_id": str(uuid4()), "instrument_flags": ["SYNTHETIC-WARNING"],
        }}
        db_session.commit()
    report = service.record_report_qc(report.id, actor_user_id=reviewer.id, command=LabReportQCIn(
        expected_updated_at=report.updated_at.isoformat(), status="not_applicable", reason="SYNTHETIC QC",
    ))
    report = service.submit_for_review(
        report.id, actor_user_id=entered_by.id, expected_updated_at=report.updated_at.isoformat(),
    )
    path = f"/api/v1/lab/report-instances/{report.id}"
    headers = _auth(reviewer)
    if not instrument_warning:
        for unusual_change in (True, False):
            returned = client.post(f"{path}/return-to-draft", headers=headers, json={
                "expected_updated_at": report.updated_at.isoformat(),
                "reason": "SYNTHETIC manual observation",
                "unusual_change": unusual_change,
            })
            assert returned.status_code == 200, returned.text
            assert returned.json()["release_holds"] == [hold]
            assert returned.json()["workflow_events"][-1]["evidence"]["unusual_change"] is True
            report = service.submit_for_review(
                report.id, actor_user_id=entered_by.id, expected_updated_at=returned.json()["updated_at"],
            )

    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["release_holds"] == [hold]
    assert "review" in response.json()["available_actions"]
    command = {"expected_updated_at": response.json()["updated_at"]}
    denied = client.post(f"{path}/review", headers=headers, json=command)
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"] == hold

    reviewed_command = {**command, "reason": "SYNTHETIC disposition of the manual finding"}
    reviewed = client.post(f"{path}/review", headers=headers, json=reviewed_command)
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "REVIEWED"
    assert reviewed.json()["release_holds"] == []
    event = reviewed.json()["workflow_events"][-1]
    assert event["actor_user_id"] == reviewer.id
    assert event["reason"] == reviewed_command["reason"]
    replay = client.post(f"{path}/review", headers=headers, json=reviewed_command)
    assert replay.status_code == 200
    assert replay.json()["workflow_events"] == reviewed.json()["workflow_events"]


@pytest.mark.unit
def test_managed_submission_accepts_documented_absence_for_required_results(
    db_session, test_patient, monkeypatch,
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    entrant = _staff(db_session, "managed-completeness", [])
    service = LabReportingService(db_session)
    template = service.create_template(
        {
            "code": "SYNTHETIC-COMPLETENESS",
            "name": "SYNTHETIC completeness",
            "family": "synthetic",
            "initial_version": {
                "layout_preset": "lab_table_classic_v1",
                "sections": [{
                    "key": "results",
                    "fields": [
                        {"field_key": "optional", "label": "SYNTHETIC 1", "value_type": "numeric"},
                        {"field_key": "required", "label": "SYNTHETIC 2", "value_type": "numeric", "required": True},
                    ],
                }],
            },
        },
    )
    service.publish_template_version(template.versions[0].id)
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_user_id=entrant.id,
    )
    _accepted_specimen(db_session, report, "SYNTHETIC-COMPLETENESS")
    with pytest.raises(LabReportingDomainError, match="Required results missing") as empty:
        service.submit_for_review(
            report.id, expected_updated_at=report.updated_at.isoformat(), actor_user_id=entrant.id,
        )
    assert empty.value.status_code == 400
    report, _ = service.bulk_upsert_values(
        report.id, [{"field_key": "optional", "value_text": "135"}],
        expected_updated_at=report.updated_at.isoformat(), actor_user_id=entrant.id,
    )
    with pytest.raises(LabReportingDomainError, match="Required results missing: required"):
        service.submit_for_review(
            report.id, expected_updated_at=report.updated_at.isoformat(), actor_user_id=entrant.id,
        )
    report, _ = service.bulk_upsert_values(
        report.id,
        [{
            "field_key": "required", "result_kind": "absent",
            "absence_reason": "SYNTHETIC documented absence",
        }],
        expected_updated_at=report.updated_at.isoformat(), actor_user_id=entrant.id,
    )
    report = service.submit_for_review(
        report.id, expected_updated_at=report.updated_at.isoformat(), actor_user_id=entrant.id,
    )
    assert report.status == "IN_REVIEW"
    absence = next(value for value in report.values if value.field_key == "required")
    assert absence.result_payload["absence_reason"] == "SYNTHETIC documented absence"


@pytest.mark.unit
def test_draft_template_can_preview_but_cannot_replace_released_pdf(
    client, db_session, test_patient, auth_headers, monkeypatch,
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", False)
    service = LabReportingService(db_session)
    monkeypatch.setattr(service, "_emit_lab_results_ready_notification", lambda _: None)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    create_data = {"patient_id": test_patient.id, "template_id": template.id}
    released = service.create_instance(create_data)
    values = [
        {"field_key": "hgb", "value_text": "135"},
        {"field_key": "wbc", "value_text": "5.2"},
    ]
    service.bulk_upsert_values(released.id, values)
    released = service.finalize(released.id)
    released_version = released.template_version_id
    payloads = []
    render_report = lab_report_pdf_service.render_report

    def capture_report(context):
        payloads.append(deepcopy(context))
        return render_report(context)

    monkeypatch.setattr(lab_report_pdf_service, "render_report", capture_report)
    released_path = f"/api/v1/lab/report-instances/{released.id}/pdf"
    before = client.get(released_path, headers=auth_headers)
    assert before.status_code == 200 and before.content.startswith(b"%PDF")
    frozen_context = payloads.pop()
    draft = service.create_template_version(template.id, source_version_id=released_version)
    draft_report = service.create_instance({**create_data, "template_version_id": draft.id})
    service.bulk_upsert_values(draft_report.id, values)
    draft_path = f"/api/v1/lab/report-instances/{draft_report.id}"

    preview = client.get(f"{draft_path}/preview", headers=auth_headers)
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF")
    assert payloads.pop()["watermark_text"]
    with pytest.raises(LabReportingDomainError, match="Release requires a published template"):
        service.finalize(draft_report.id)
    assert service.get_instance(draft_report.id).status in {"DRAFT", "IN_PROGRESS"}

    service.update_template_version(
        draft.id,
        {
            "layout_preset": draft.layout_preset,
            "page_settings": draft.page_settings,
            "branding_overrides": draft.branding_overrides,
            "signer_defaults": draft.signer_defaults,
            "sections": service._sections_to_payload(draft.sections),
            "footer_notes": "SYNTHETIC updated footer",
        },
    )
    changed_preview = client.get(f"{draft_path}/preview", headers=auth_headers)
    assert changed_preview.status_code == 200 and changed_preview.content.startswith(b"%PDF")
    assert payloads.pop()["footer_notes"] == "SYNTHETIC updated footer"
    service.publish_template_version(draft.id)
    after = client.get(released_path, headers=auth_headers)
    assert after.status_code == 200 and after.content.startswith(b"%PDF")
    assert service.get_instance(released.id).template_version_id == released_version
    assert payloads.pop() == frozen_context


@pytest.mark.unit
def test_recollection_does_not_silently_rebind_a_measured_value(
    db_session, test_patient, monkeypatch
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    entrant = _staff(db_session, "recollection", [])
    importer = _staff(db_session, "recollection-import", [])
    db_session.commit()
    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_user_id=entrant.id,
    )
    original = _accepted_specimen(db_session, report, "SYNTHETIC-FIRST")
    report, values = service.bulk_upsert_values(
        report.id,
        [{"field_key": "hgb", "value_text": "100"}],
        actor_user_id=entrant.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert values[0].result_payload["source_specimen_id"] == original.id
    original.status = "rejected"
    original.revision += 1
    replacement = _accepted_specimen(
        db_session,
        report,
        "SYNTHETIC-SECOND",
        replaces_specimen_id=original.id,
    )
    report, values = service.bulk_upsert_values(
        report.id,
        [{"field_key": "hgb", "value_text": "100", "comment": "SYNTHETIC comment"}],
        actor_user_id=entrant.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert values[0].result_payload["source_specimen_id"] == original.id
    assert "specimen_result_mismatch" in service.report_release_holds(report)
    with pytest.raises(LabReportingDomainError, match="specimen_result_mismatch"):
        service.submit_for_review(
            report.id,
            actor_user_id=entrant.id,
            expected_updated_at=report.updated_at.isoformat(),
        )

    # A validated import anchored to the replacement can carry the same number.
    report, values = service.bulk_upsert_values(
        report.id,
        [{"field_key": "hgb", "value_text": "100"}],
        actor_user_id=importer.id,
        expected_updated_at=report.updated_at.isoformat(),
        source_specimen_id=replacement.id,
    )
    assert values[0].result_payload["source_specimen_id"] == replacement.id
    assert [
        event.actor_user_id for event in service.workflow_history(report.id)
        if event.kind == "entered"
    ] == [entrant.id, importer.id]
    report = service.submit_for_review(
        report.id,
        actor_user_id=entrant.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert report.values[0].result_payload["source_specimen_id"] == replacement.id


@pytest.mark.unit
def test_changed_absence_is_an_entry_but_resending_it_is_not(
    db_session, test_patient, monkeypatch
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    entrant = _staff(db_session, "absence-entrant", [])
    editor = _staff(db_session, "absence-editor", [])
    db_session.commit()
    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_user_id=entrant.id,
    )
    absence = {
        "field_key": "hgb",
        "result_kind": "absent",
        "absence_reason": "SYNTHETIC no reading",
    }
    report, _ = service.bulk_upsert_values(
        report.id,
        [absence],
        actor_user_id=entrant.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    report, _ = service.bulk_upsert_values(
        report.id,
        [{**absence, "comment": "SYNTHETIC annotation"}],
        actor_user_id=editor.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert [event.actor_user_id for event in service.workflow_history(report.id)] == [
        entrant.id
    ]
    report, _ = service.bulk_upsert_values(
        report.id,
        [{**absence, "absence_reason": "SYNTHETIC revised reason"}],
        actor_user_id=editor.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    assert [event.actor_user_id for event in service.workflow_history(report.id)] == [
        entrant.id, editor.id,
    ]


@pytest.mark.unit
def test_managed_draft_is_hidden_from_assigned_doctor(
    db_session,
    test_patient,
    test_visit,
    test_doctor,
    client,
    monkeypatch,
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    operator = _staff(db_session, "lab-access", [])
    doctor = db_session.get(User, test_doctor.user_id)
    doctor.role = "doctor"
    test_patient.first_name = "SYNTHETIC"
    catalog_entry = Service(code="L01", name="SYNTHETIC CBC", queue_tag="laboratory")
    db_session.add(catalog_entry)
    db_session.flush()
    ordered_line = VisitService(
        visit_id=test_visit.id,
        service_id=catalog_entry.id,
        code="L01",
        name="SYNTHETIC CBC",
    )
    db_session.add(ordered_line)
    db_session.commit()
    substitute = _staff(db_session, "lab-access-substitute", [])
    db_session.commit()
    _approved_clinical_configuration(db_session, operator, substitute)

    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    response = client.post(
        "/api/v1/lab/report-instances",
        headers=_auth(operator),
        json={
            "patient_id": test_patient.id,
            "visit_id": test_visit.id,
            "template_id": template.id,
            "visit_service_ids": [ordered_line.id],
        },
    )
    assert response.status_code == 200, response.json()
    report = response.json()
    assert report["managed_release"] is True
    assert report["available_actions"] == ["preview", "edit", "save_draft"]
    assert {"specimen_required", "qc_missing"} <= set(report["release_holds"])
    allocation = (
        db_session.query(LabOrderTest).filter_by(visit_service_id=ordered_line.id).one()
    )
    assert allocation.report_instance_id == report["id"]

    response = client.get(
        f"/api/v1/lab/report-instances/{report['id']}", headers=_auth(doctor)
    )
    assert response.status_code == 404
    response = client.get(
        "/api/v1/lab/report-instances",
        params={"visit_ids": test_visit.id},
        headers=_auth(doctor),
    )
    assert response.status_code == 200
    assert response.json() == []
