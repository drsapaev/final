"""The managed path never publishes a version the reviewer did not inspect."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core.config import settings
from app.crud import audit as audit_crud
from app.models.lab import LabOrderTest
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.role_permission import Permission, Role, user_roles_table
from app.models.service import Service
from app.models.user import User
from app.models.visit import VisitService
from app.schemas.lab_release import LabReportQCIn
from app.services.authentication_service import authentication_service
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


def _accepted_specimen(db, report, barcode, *, replaces_specimen_id=None):
    specimen = LabSpecimen(
        order_id=report.order_id,
        barcode=barcode,
        material_code="synthetic-blood",
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
    assert service.workflow_history(revision.id)[0].reason == "SYNTHETIC correction"
    same_revision = service.revise(
        report_id,
        actor_user_id=actor_id,
        expected_updated_at=released_version,
        reason="SYNTHETIC correction",
    )
    assert same_revision.id == revision.id
    assert service.get_instance(report_id).status == "FINALIZED"


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
    assert report["available_actions"] == [
        "preview",
        "edit",
        "save_draft",
        "submit_review",
    ]
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
