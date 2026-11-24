from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.lab import (
    LabOrder,
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
)
from app.models.lab_specimen import LabSpecimenEvent
from app.models.patient import Patient
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.repositories.lab_specimen_repository import SpecimenRepository
from app.services.authentication_service import authentication_service

LAB_API = "/api/v1/lab"


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


def _user(db, role: str, *, active: bool = True) -> User:
    suffix = uuid4().hex[:8]
    user = User(
        username=f"synthetic_specimen_{role.lower()}_{suffix}",
        email=f"specimen-{suffix}@test.invalid",
        full_name=f"SYNTHETIC-{role}",
        hashed_password="unused-by-token-test",
        role=role,
        is_active=active,
    )
    db.add(user)
    db.flush()
    return user


def _visit(db) -> tuple[Patient, Visit, VisitService]:
    patient = Patient(first_name="SYNTHETIC-LAB", last_name=uuid4().hex[:8])
    db.add(patient)
    db.flush()
    visit = Visit(
        patient_id=patient.id,
        visit_date=date(2026, 11, 24),
        status="open",
        source="desk",
    )
    db.add(visit)
    db.flush()
    test = VisitService(
        visit_id=visit.id, service_id=123456, code="L01", name="SYNTHETIC-LAB-TEST"
    )
    db.add(test)
    db.flush()
    return patient, visit, test


def _report(db, order: LabOrder, status: str = "DRAFT") -> LabReportInstance:
    template = LabReportTemplate(
        code=f"synthetic_{uuid4().hex[:8]}", name="SYNTHETIC LAB", family="lab"
    )
    db.add(template)
    db.flush()
    version = LabReportTemplateVersion(
        template_id=template.id,
        version_no=1,
        status="PUBLISHED",
        layout_preset="a4",
    )
    db.add(version)
    db.flush()
    report = LabReportInstance(
        order_id=order.id,
        visit_id=order.visit_id,
        patient_id=order.patient_id,
        template_id=template.id,
        template_version_id=version.id,
        status=status,
    )
    db.add(report)
    db.flush()
    return report


@pytest.fixture
def specimen_context(db_session):
    first_actor = _user(db_session, "Lab")
    second_actor = _user(db_session, "Lab")
    patient, visit, test = _visit(db_session)
    other_patient, other_visit, other_test = _visit(db_session)
    other_order = LabOrder(visit_id=other_visit.id, patient_id=other_patient.id)
    db_session.add(other_order)
    db_session.flush()
    db_session.commit()
    return first_actor, second_actor, patient, visit, test, other_order, other_test


def _create(test_id: int, *, material_code: str = "blood", **fields) -> dict:
    return {
        "request_id": str(uuid4()),
        "material_code": material_code,
        "container_code": "tube",
        "visit_service_ids": [test_id],
        **fields,
    }


def _post_event(client, headers, row, action, **fields):
    command = {
        "request_id": str(uuid4()),
        "expected_revision": row["revision"],
        "action": action,
        **fields,
    }
    return client.post(
        f"{LAB_API}/specimens/{row['id']}/events", json=command, headers=headers
    )


def test_first_collection_preserves_subject_and_resolves_only_its_barcode(
    client, db_session, specimen_context
):
    actor, _, patient, visit, test, other_order, other_test = specimen_context
    headers = _headers(actor)
    path = f"{LAB_API}/visits/{visit.id}/specimens"
    assert (
        client.post(path, json=_create(other_test.id), headers=headers).status_code
        == 404
    )

    command = _create(test.id)
    response = client.post(path, json=command, headers=headers)
    assert response.status_code == 201, response.text
    blood = response.json()
    assert blood["visit_id"] == visit.id
    assert blood["collected_at"] is None
    assert blood["events"][0]["actor_user_id"] == actor.id
    assert blood["events"][0]["happened_at"].endswith("Z")
    assert blood["visit_service_ids"] == [test.id]
    assert blood["status"] == "expected"
    assert client.post(path, json=command, headers=headers).json()["id"] == blood["id"]

    orders = list(
        db_session.scalars(select(LabOrder).where(LabOrder.visit_id == visit.id))
    )
    assert [order.id for order in orders] == [blood["order_id"]]
    assert orders[0].patient_id == patient.id

    urine_response = client.post(
        path, json=_create(test.id, material_code="urine"), headers=headers
    )
    assert urine_response.status_code == 201, urine_response.text
    urine = urine_response.json()
    assert urine["order_id"] == blood["order_id"]
    assert urine["barcode"] != blood["barcode"]

    scan = f"{LAB_API}/specimens/scan"
    assert (
        client.post(
            scan,
            json={"barcode": blood["barcode"], "order_id": other_order.id},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            scan,
            json={"barcode": "SP-0000000000000000"},
            headers=headers,
        ).status_code
        == 404
    )
    response = client.post(
        scan, json={"barcode": blood["barcode"].lower()}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == blood["id"]
    assert response.headers["cache-control"] == "no-store"
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(PatientAccessAuditLog)
            .where(
                PatientAccessAuditLog.resource_type == "lab_specimen",
                PatientAccessAuditLog.resource_id == str(blood["id"]),
                PatientAccessAuditLog.subject_patient_id == patient.id,
                PatientAccessAuditLog.actor_staff_user_id == actor.id,
            )
        )
        == 1
    )


def test_specimen_custody_requires_revision_and_preserves_rejected_history(
    client, db_session, specimen_context
):
    collector, checker, _, visit, test, _, _ = specimen_context
    collector_headers = _headers(collector)
    checker_headers = _headers(checker)
    row = client.post(
        f"{LAB_API}/visits/{visit.id}/specimens",
        json=_create(test.id),
        headers=collector_headers,
    ).json()
    order_id = row["order_id"]
    order = db_session.get(LabOrder, order_id)
    report = _report(db_session, order)
    db_session.commit()
    assignment_path = f"{LAB_API}/specimens/{row['id']}/assignments"
    assignment = client.post(
        assignment_path,
        json={
            "request_id": str(uuid4()),
            "expected_revision": row["revision"],
            "report_instance_ids": [report.id],
        },
        headers=collector_headers,
    )
    assert assignment.status_code == 200, assignment.text
    row = assignment.json()
    assert row["report_instance_ids"] == [report.id]

    received_before_collection = _post_event(client, checker_headers, row, "receive")
    assert received_before_collection.status_code == 409
    collect = {
        "request_id": str(uuid4()),
        "expected_revision": row["revision"],
        "action": "collect",
    }
    events_url = f"{LAB_API}/specimens/{row['id']}/events"
    collected_rsp = client.post(events_url, json=collect, headers=collector_headers)
    assert collected_rsp.status_code == 200, collected_rsp.text
    collected = collected_rsp.json()
    assert collected["collected_at"] is not None
    replay = client.post(events_url, json=collect, headers=collector_headers)
    assert replay.status_code == 200
    assert replay.json()["events"] == collected["events"]
    assert (
        client.post(events_url, json=collect, headers=checker_headers).status_code
        == 409
    )
    assert (
        _post_event(
            client, checker_headers, row, "reject", reason="SYNTHETIC-REJECT"
        ).status_code
        == 409
    )

    held = _post_event(
        client, checker_headers, collected, "hold", reason="SYNTHETIC-HOLD"
    ).json()
    assert held["status"] == "held"
    assert held["latest_reason"] == "SYNTHETIC-HOLD"
    received = _post_event(client, checker_headers, held, "receive").json()
    assert received["received_at"] is not None
    accepted = _post_event(client, checker_headers, received, "accept").json()
    assert accepted["accepted_at"] is not None
    assert accepted["events"][-1]["actor_user_id"] == checker.id

    order_path = f"{LAB_API}/orders/{order_id}/specimens"
    aliquot_rsp = client.post(
        order_path,
        json=_create(test.id, parent_specimen_id=accepted["id"]),
        headers=checker_headers,
    )
    assert aliquot_rsp.status_code == 201, aliquot_rsp.text
    assert aliquot_rsp.json()["parent_specimen_id"] == accepted["id"]
    assert aliquot_rsp.json()["events"][0]["action"] == "aliquot"
    rejected = _post_event(
        client, checker_headers, accepted, "reject", reason="SYNTHETIC-REJECT"
    ).json()
    recollect_rsp = client.post(
        order_path,
        json=_create(
            test.id,
            replaces_specimen_id=rejected["id"],
            report_instance_ids=[report.id],
        ),
        headers=collector_headers,
    )
    assert recollect_rsp.status_code == 201, recollect_rsp.text
    recollected = recollect_rsp.json()
    assert recollected["barcode"] != rejected["barcode"]
    assert recollected["replaces_specimen_id"] == rejected["id"]
    assert recollected["events"][0]["action"] == "recollect"
    assert [
        item.id for item in SpecimenRepository(db_session).list_for_release(report.id)
    ] == [recollected["id"]]
    assert (
        client.post(
            order_path,
            json=_create(test.id, replaces_specimen_id=rejected["id"]),
            headers=collector_headers,
        ).status_code
        == 409
    )
    old = next(
        item
        for item in client.get(order_path, headers=collector_headers).json()["items"]
        if item["id"] == rejected["id"]
    )
    assert old["status"] == "rejected"
    assert old["latest_reason"] == "SYNTHETIC-REJECT"
    assert "recollect" not in old["available_actions"]


def test_lab_specimen_labels_and_reads_require_active_staff(
    client, db_session, specimen_context
):
    actor, _, _, visit, test, other_order, _ = specimen_context
    doctor = _user(db_session, "Doctor")
    inactive_lab = _user(db_session, "Lab", active=False)
    db_session.commit()
    headers = _headers(actor)
    read_path = f"{LAB_API}/orders/{other_order.id}/specimens"
    assert client.get(read_path, headers=_headers(doctor)).status_code == 403
    assert client.get(read_path, headers=_headers(inactive_lab)).status_code == 403
    assert client.get(read_path, headers=headers).json() == {
        "items": [],
        "data_status": "unknown",
    }

    row = client.post(
        f"{LAB_API}/visits/{visit.id}/specimens",
        json=_create(test.id),
        headers=headers,
    ).json()
    label_url = f"{LAB_API}/specimens/{row['id']}/label"
    body = {"request_id": str(uuid4()), "expected_revision": row["revision"]}
    result = client.post(label_url, json=body, headers=headers)
    assert result.status_code == 200, result.text
    assert result.headers["content-type"] == "application/pdf"
    assert result.content.startswith(b"%PDF")
    assert client.post(label_url, json=body, headers=headers).content == result.content
    listed = client.get(
        f"{LAB_API}/orders/{row['order_id']}/specimens", headers=headers
    ).json()
    assert [event["action"] for event in listed["items"][0]["events"]] == [
        "create",
        "print_label",
    ]

    printed = listed["items"][0]
    reprint_body = {"request_id": str(uuid4()), "expected_revision": printed["revision"]}
    reprint = client.post(label_url, json=reprint_body, headers=headers)
    assert reprint.status_code == 200, reprint.text
    assert reprint.headers["content-disposition"] == result.headers["content-disposition"]
    assert reprint.content == result.content

    replay = client.post(label_url, json=reprint_body, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.content == result.content
    reprinted = client.get(
        f"{LAB_API}/orders/{row['order_id']}/specimens", headers=headers
    ).json()["items"][0]
    assert reprinted["id"] == row["id"]
    assert reprinted["barcode"] == row["barcode"]
    assert reprinted["revision"] == row["revision"] + 2
    assert [
        (event["action"], event["actor_user_id"], event["revision"])
        for event in reprinted["events"]
    ] == [
        ("create", actor.id, row["revision"]),
        ("print_label", actor.id, row["revision"] + 1),
        ("print_label", actor.id, row["revision"] + 2),
    ]


def test_specimen_openapi_documents_context_and_binary_labels(client):
    paths = client.get("/openapi.json").json()["paths"]
    order_path = paths[f"{LAB_API}/orders/{{order_id}}/specimens"]
    assert order_path["get"]["operationId"] == "lab_list_order_specimens"
    assert {"201", "403", "404", "409", "422"} <= set(order_path["post"]["responses"])
    issue_label = paths[f"{LAB_API}/specimens/{{specimen_id}}/label"]["post"]
    assert issue_label["responses"]["200"]["content"]["application/pdf"]["schema"] == {
        "type": "string",
        "format": "binary",
    }


def test_assignment_correction_is_audited_and_aliquot_requires_its_source(
    client,
    db_session,
    specimen_context,
):
    actor, _, _, visit, test, other_order, _ = specimen_context
    headers = _headers(actor)
    row = client.post(
        f"{LAB_API}/visits/{visit.id}/specimens",
        json=_create(test.id),
        headers=headers,
    ).json()
    order = db_session.get(LabOrder, row["order_id"])
    report = _report(db_session, order)
    foreign_report = _report(db_session, other_order)
    released_report = _report(db_session, order, status="FINALIZED")
    db_session.commit()

    assign_path = f"{LAB_API}/specimens/{row['id']}/assignments"
    for report_id, expected_status in [
        (foreign_report.id, 404),
        (released_report.id, 409),
    ]:
        response = client.post(
            assign_path,
            json={
                "request_id": str(uuid4()),
                "expected_revision": row["revision"],
                "report_instance_ids": [report_id],
            },
            headers=headers,
        )
        assert response.status_code == expected_status, response.text

    collected = _post_event(client, headers, row, "collect").json()
    received = _post_event(client, headers, collected, "receive").json()
    accepted = _post_event(client, headers, received, "accept").json()
    aliquot_rsp = client.post(
        f"{LAB_API}/orders/{order.id}/specimens",
        json=_create(
            test.id, parent_specimen_id=accepted["id"], report_instance_ids=[report.id]
        ),
        headers=headers,
    )
    assert aliquot_rsp.status_code == 201, aliquot_rsp.text
    aliquot = aliquot_rsp.json()
    checked = SpecimenRepository(db_session).list_for_release(report.id)
    assert [specimen.id for specimen in checked] == [accepted["id"], aliquot["id"]]
    correction = {
        "operation": "remove",
        "request_id": str(uuid4()),
        "expected_revision": aliquot["revision"],
        "report_instance_ids": [report.id],
    }
    correction_path = f"{LAB_API}/specimens/{aliquot['id']}/assignments"
    assert (
        client.post(correction_path, json=correction, headers=headers).status_code
        == 422
    )
    corrected_rsp = client.post(
        correction_path,
        json={**correction, "reason": "SYNTHETIC-CORRECTION"},
        headers=headers,
    )
    assert corrected_rsp.status_code == 200, corrected_rsp.text
    corrected = corrected_rsp.json()
    assert corrected["report_instance_ids"] == []
    assert corrected["events"][-1]["action"] == "unassign"
    assert corrected["events"][-1]["report_instance_ids"] == [report.id]
    assert corrected["events"][-1]["reason"] == "SYNTHETIC-CORRECTION"
    assert SpecimenRepository(db_session).list_for_release(report.id) == []


def test_specimen_validation_does_not_echo_rejected_clinical_input(
    client, specimen_context, caplog
):
    actor, _, _, visit, test, _, _ = specimen_context
    headers = _headers(actor)
    # Invalid structure must not put a specimen identifier or unstructured
    # text into a 422 response or the validation warning.
    marker = "SYNTHETIC-UNSTRUCTURED-CLINICAL-TEXT"
    scan = client.post(
        f"{LAB_API}/specimens/scan", json={"barcode": marker * 5}, headers=headers
    )
    assert scan.status_code == 422
    assert marker not in scan.text
    assert scan.json()["detail"][0]["loc"] == ["body", "barcode"]

    row = client.post(
        f"{LAB_API}/visits/{visit.id}/specimens", json=_create(test.id), headers=headers
    ).json()
    invalid_reason = _post_event(client, headers, row, "hold", reason=marker * 10)
    assert invalid_reason.status_code == 422
    assert marker not in invalid_reason.text
    extra_field = _post_event(client, headers, row, "collect", **{marker: marker})
    assert extra_field.status_code == 422
    assert marker not in extra_field.text
    assert marker not in caplog.text


def test_rejection_metrics_count_only_coded_reasons_and_unknown_history(
    client,
    db_session,
    specimen_context,
    auth_headers,
):
    actor, _, _, visit, test, _, _ = specimen_context
    headers = _headers(actor)
    create_path = f"{LAB_API}/visits/{visit.id}/specimens"
    private_note = "SYNTHETIC-PRIVATE-CUSTODY-NOTE"

    def create():
        result = client.post(create_path, json=_create(test.id), headers=headers)
        assert result.status_code == 201, result.text
        return result.json()

    row = create()
    invalid = _post_event(
        client, headers, row, "reject", reason=private_note, reason_code=private_note
    )
    assert invalid.status_code == 422
    assert private_note not in invalid.text
    rejected_code_on_collect = _post_event(
        client, headers, row, "collect", reason_code="label_mismatch"
    )
    assert rejected_code_on_collect.status_code == 422

    command = {
        "request_id": str(uuid4()),
        "expected_revision": row["revision"],
        "action": "reject",
        "reason": private_note,
        "reason_code": "label_mismatch",
    }
    events_path = f"{LAB_API}/specimens/{row['id']}/events"
    coded = client.post(events_path, json=command, headers=headers)
    assert coded.status_code == 200, coded.text
    assert coded.json()["events"][-1]["reason_code"] == "label_mismatch"
    assert client.post(events_path, json=command, headers=headers).status_code == 200

    legacy = _post_event(client, headers, create(), "reject", reason=private_note)
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["events"][-1]["reason_code"] is None

    old = _post_event(
        client,
        headers,
        create(),
        "reject",
        reason=private_note,
        reason_code="transport_issue",
    )
    assert old.status_code == 200, old.text
    historic = db_session.get(LabSpecimenEvent, old.json()["events"][-1]["id"])
    historic.happened_at = datetime.now(UTC) - timedelta(days=3)
    db_session.commit()

    collected = _post_event(client, headers, create(), "collect")
    assert collected.status_code == 200, collected.text
    held = _post_event(client, headers, collected.json(), "hold", reason=private_note)
    assert held.status_code == 200, held.text

    metrics_path = f"{LAB_API}/metrics?days=1"
    assert client.get(metrics_path, headers=headers).status_code == 403
    metrics = client.get(metrics_path, headers=auth_headers)
    assert metrics.status_code == 200, metrics.text
    assert private_note not in metrics.text
    assert metrics.json()["rejected_samples"] == 2
    assert metrics.json()["rejected_samples_by_reason"] == {
        "label_mismatch": 1,
        "unknown": 1,
    }
    assert metrics.json()["held_samples"] == 1
