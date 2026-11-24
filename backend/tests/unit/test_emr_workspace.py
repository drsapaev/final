"""Synthetic contracts for the clinician workspace and its clinical writes."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.emr import Prescription
from app.models.lab import (
    LabOrder,
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
)
from app.models.patient import Patient
from app.models.visit import Visit


def emr_path(visit_id):
    return f"/api/v1/v2/emr/{visit_id}"


def test_longitudinal_versions_are_scoped_and_do_not_change_the_visit_emr(
    client,
    db_session,
    auth_headers,
    test_visit,
):
    root = emr_path(test_visit.id)
    workspace = f"{root}/workspace"
    alternative = Patient(first_name="SYNTHETIC-Workspace", last_name="Other")
    db_session.add(alternative)
    db_session.flush()
    initial = client.get(workspace, headers=auth_headers).json()
    assert initial["allergy_state"] == "not_checked"
    assert initial["visit"]["id"] == test_visit.id
    entry = f"{workspace}/entries/{uuid4()}"
    body = {
        "patient_id": test_visit.patient_id,
        "expected_version": 0,
        "source": "patient_report",
        "confirmed": True,
        "clinical_details": {
            "kind": "allergy_check",
            "status": "none_reported",
            "event_on": "2026-11",
        },
    }
    wrong = client.put(
        entry, headers=auth_headers, json={**body, "patient_id": alternative.id}
    )
    assert wrong.status_code == 409
    first = client.put(entry, headers=auth_headers, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 1
    assert first.json()["clinical_details"]["event_on"] == "2026-11"
    assert first.json()["confirmed_at"]
    assert (
        client.get(workspace, headers=auth_headers).json()["allergy_state"]
        == "none_reported"
    )

    changed = {
        **body,
        "expected_version": 1,
        "clinical_details": {"kind": "allergy_check", "status": "unknown"},
    }
    assert client.put(entry, headers=auth_headers, json=changed).status_code == 200
    assert client.put(entry, headers=auth_headers, json=changed).status_code == 409
    revisions = client.get(f"{entry}/history", headers=auth_headers).json()
    assert [
        (row["version"], row["clinical_details"]["status"]) for row in revisions
    ] == [
        (2, "unknown"),
        (1, "none_reported"),
    ]
    assert client.get(root, headers=auth_headers).status_code == 404


def test_transfer_uses_the_signed_source_and_rx_uses_the_exact_saved_revision(
    client,
    db_session,
    auth_headers,
    test_visit,
):
    prior = Visit(
        patient_id=test_visit.patient_id,
        doctor_id=test_visit.doctor_id,
        visit_date=test_visit.visit_date,
    )
    db_session.add(prior)
    db_session.flush()
    prior_root = emr_path(prior.id)
    original = {"specialty": "cardiology", "recommendations": "SYNTHETIC-Previous plan"}
    saved_prior = client.post(
        prior_root, headers=auth_headers, json={"data": original, "is_draft": False}
    ).json()
    signed_response = client.post(
        f"{prior_root}/sign",
        headers=auth_headers,
        json={"data": original, "row_version": saved_prior["row_version"]},
    )
    assert signed_response.status_code == 200, signed_response.text
    signed = signed_response.json()

    root = emr_path(test_visit.id)
    document = {
        "specialty": "cardiology",
        "follow_up": {
            "mode": "follow_up",
            "transferred_fields": [
                {
                    "source_visit_id": prior.id,
                    "source_version": signed["version"],
                    "field": "recommendations",
                    "confirmed_current": False,
                    "text": "SYNTHETIC-Ignored client text",
                }
            ],
        },
        "medications": {
            "list": [
                {
                    "name": "SYNTHETIC-Item",
                    "dose": "SYNTHETIC dose",
                    "frequency": "SYNTHETIC schedule",
                    "duration": "SYNTHETIC duration",
                    "quantity": "2",
                }
            ]
        },
    }

    response = client.post(
        root, headers=auth_headers, json={"data": document, "is_draft": False}
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    transfer = saved["data"]["follow_up"]["transferred_fields"][0]
    assert transfer["source_patient_id"] == test_visit.patient_id
    assert transfer["text"] == original["recommendations"]
    assert transfer["transferred_at"]
    assert "recommendations" not in saved["data"]
    assert db_session.query(Prescription).filter_by(visit_id=test_visit.id).count() == 0

    rx = f"{root}/workspace/prescription"
    request = {
        "patient_id": test_visit.patient_id,
        "expected_row_version": saved["row_version"],
    }
    issued = client.post(rx, headers=auth_headers, json=request)
    assert issued.status_code == 200, issued.text
    assert issued.json()["is_draft"] is False
    assert issued.json()["emr_version"] == saved["version"]
    assert client.post(rx, headers=auth_headers, json=request).json() == issued.json()
    assert db_session.query(Prescription).filter_by(visit_id=test_visit.id).count() == 1
    assert (
        client.post(
            rx, headers=auth_headers, json={**request, "expected_row_version": 9999}
        ).status_code
        == 409
    )
    assert (
        client.get(prior_root, headers=auth_headers).json()["row_version"]
        == signed["row_version"]
    )
    amended_response = client.post(
        f"{prior_root}/amend",
        headers=auth_headers,
        json={
            "data": {**original, "recommendations": "SYNTHETIC updated previous plan"},
            "reason": "SYNTHETIC correction to the previous plan",
            "row_version": signed["row_version"],
        },
    )
    assert amended_response.status_code == 200, amended_response.text
    amended = amended_response.json()
    history = f"{root}/workspace/history/{prior.id}"
    original_version = client.get(f"{history}/{signed['version']}", headers=auth_headers)
    assert original_version.status_code == 200, original_version.text
    assert original_version.json()["status"] == "signed"
    assert original_version.json()["recommendations"] == original["recommendations"]
    amended_version = client.get(f"{history}/{amended['version']}", headers=auth_headers)
    assert amended_version.status_code == 200, amended_version.text
    assert amended_version.json()["status"] == "amended"
    assert amended_version.json()["recommendations"] == "SYNTHETIC updated previous plan"


def test_lab_review_belongs_to_the_exact_report_version_and_order(
    client,
    db_session,
    auth_headers,
    test_visit,
):
    order = LabOrder(
        patient_id=test_visit.patient_id, visit_id=test_visit.id, status="ordered"
    )
    template = LabReportTemplate(
        code="SYNTHETIC-EMR", name="SYNTHETIC Lab", family="test"
    )
    db_session.add_all([order, template])
    db_session.flush()
    version = LabReportTemplateVersion(
        template_id=template.id,
        version_no=1,
        status="PUBLISHED",
        layout_preset="standard",
    )
    db_session.add(version)
    db_session.flush()
    common = {
        "order_id": order.id,
        "patient_id": test_visit.patient_id,
        "visit_id": test_visit.id,
        "template_id": template.id,
        "template_version_id": version.id,
    }
    first = LabReportInstance(
        **common, status="PRINTED", finalized_at=datetime.now(UTC)
    )
    db_session.add(first)
    db_session.flush()
    labs = f"{emr_path(test_visit.id)}/workspace/labs"
    mark = f"{labs}/{first.id}/review"
    before = client.get(labs, headers=auth_headers).json()
    assert before["orders"][0]["status"] == "ordered"
    assert before["orders"][0]["reports"][0]["reviews"] == []
    review_request = {
        "patient_id": test_visit.patient_id,
        "next_action": "SYNTHETIC follow-up",
    }
    reviewed = client.post(mark, headers=auth_headers, json=review_request)
    assert reviewed.status_code == 200, reviewed.text
    assert (
        client.post(mark, headers=auth_headers, json=review_request).json()
        == reviewed.json()
    )

    revision = LabReportInstance(
        **common,
        status="FINALIZED",
        finalized_at=datetime.now(UTC),
        supersedes_instance_id=first.id,
    )
    db_session.add(revision)
    db_session.flush()
    grouped = client.get(labs, headers=auth_headers).json()["orders"]
    assert len(grouped) == 1
    correction, previous = grouped[0]["reports"]
    assert correction["id"] == revision.id and correction["is_current_final"]
    assert correction["reviews"] == []
    assert previous["id"] == first.id and not previous["is_current_final"]
    assert previous["reviews"] == [reviewed.json()]


def test_editing_a_reviewed_template_requires_review_of_the_new_version(
    client,
    db_session,
    auth_headers,
    admin_user,
):
    from app.services.section_templates_service import DoctorSectionTemplatesService

    service = DoctorSectionTemplatesService(db_session)
    item = service.learn_from_signed_emr(
        doctor_id=admin_user.id,
        section_type="recommendations",
        text="SYNTHETIC generic text",
    )
    path = f"/api/v1/section-templates/recommendations/{item.id}"
    revision = item.template_revision
    response = client.post(
        f"{path}/review", headers=auth_headers, json={"expected_revision": revision}
    )
    assert response.status_code == 200, response.text
    assert response.json()["reviewed_at"]
    shortcut = client.put(
        path,
        headers=auth_headers,
        json={
            "new_text": item.template_text,
            "shortcut": "синт-qa",
            "expected_revision": revision,
        },
    )
    assert shortcut.status_code == 200, shortcut.text
    assert shortcut.json()["shortcut"] == "синт-qa"
    assert shortcut.json()["template_revision"] == revision
    assert shortcut.json()["reviewed_at"] == response.json()["reviewed_at"]
    listing = client.get(
        "/api/v1/section-templates/recommendations", headers=auth_headers
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["templates"][0]["shortcut"] == "синт-qa"
    invalid_shortcut = client.put(
        path,
        headers=auth_headers,
        json={"new_text": item.template_text, "shortcut": "two words"},
    )
    assert invalid_shortcut.status_code == 422, invalid_shortcut.text
    updated = client.put(
        path, headers=auth_headers, json={"new_text": "SYNTHETIC changed generic text"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["template_revision"] == revision + 1
    assert updated.json()["reviewed_at"] is None
    assert updated.json()["shortcut"] == "синт-qa"
    stale_edit = client.put(
        path,
        headers=auth_headers,
        json={
            "new_text": "SYNTHETIC generic text",
            "shortcut": "qa",
            "expected_revision": revision,
        },
    )
    assert stale_edit.status_code == 409, stale_edit.text
    assert (
        client.post(
            f"{path}/review", headers=auth_headers, json={"expected_revision": revision}
        ).status_code
        == 409
    )


def test_transfer_rejects_a_signed_note_from_a_different_patient(
    client,
    db_session,
    auth_headers,
    test_visit,
):
    other = Patient(first_name="SYNTHETIC-Workspace", last_name="Other")
    db_session.add(other)
    db_session.flush()
    prior = Visit(
        patient_id=other.id,
        doctor_id=test_visit.doctor_id,
        visit_date=test_visit.visit_date,
    )
    db_session.add(prior)
    db_session.flush()
    prior_root = emr_path(prior.id)
    original = {
        "specialty": "cardiology",
        "recommendations": "SYNTHETIC separate patient",
    }
    saved = client.post(
        prior_root, headers=auth_headers, json={"data": original, "is_draft": False}
    ).json()
    signed = client.post(
        f"{prior_root}/sign",
        headers=auth_headers,
        json={"data": original, "row_version": saved["row_version"]},
    ).json()
    root = emr_path(test_visit.id)
    preview = client.get(
        f"{root}/workspace/history/{prior.id}/{signed['version']}", headers=auth_headers
    )
    assert preview.status_code == 409
    blocked = client.post(
        root,
        headers=auth_headers,
        json={
            "data": {
                "follow_up": {
                    "transferred_fields": [
                        {
                            "source_visit_id": prior.id,
                            "source_version": signed["version"],
                            "field": "recommendations",
                        }
                    ]
                }
            }
        },
    )
    assert blocked.status_code == 409
    assert client.get(root, headers=auth_headers).status_code == 404
