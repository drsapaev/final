from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models.lab import (
    LabOrder,
    LabOrderTest,
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
)
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.patient import Patient
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.repositories.lab_worklist_repository import (
    InvalidWorklistCursor,
    count_lab_worklist,
    search_lab_worklist,
)
from app.schemas.lab_worklist import LabWorklistSearch
from app.services.lab_reporting import LabReportingDomainError, LabReportingService

CLINIC_TZ = ZoneInfo("Asia/Tashkent")
NOW = datetime(2012, 1, 4, 19, 15, tzinfo=UTC)
TODAY = date(2012, 1, 5)
YESTERDAY = date(2012, 1, 4)


def _new_visit(db, suffix, service, *, patient=None, day=YESTERDAY, status="closed"):
    if patient is None:
        patient = Patient(
            first_name="SYNTHETIC-LAB", last_name=f"SYNTHETIC-WORKLIST-{suffix}"
        )
        db.add(patient)
        db.flush()
    visit = Visit(patient_id=patient.id, visit_date=day, status=status)
    db.add(visit)
    db.flush()
    line = VisitService(visit_id=visit.id, service_id=service.id, name=service.name)
    db.add(line)
    db.flush()
    return patient, visit, line


def _catalog(db):
    lab = Service(name="SYNTHETIC-LAB-TEST", service_code="L998", queue_tag="lab")
    non_lab = Service(name="SYNTHETIC-NONLAB", service_code="L999", queue_tag="cardio")
    db.add_all([lab, non_lab])
    db.flush()
    return lab, non_lab


def _search(db, **options):
    return search_lab_worklist(db, LabWorklistSearch(**options), CLINIC_TZ, now=NOW)


def test_worklist_searches_before_cursor_and_counts_the_entire_scope(db_session):
    lab, non_lab = _catalog(db_session)
    _, earliest, _ = _new_visit(db_session, "000", lab)
    for index in range(51):
        _new_visit(db_session, f"{index + 1:03}", lab)
    last_patient, last, _ = _new_visit(db_session, "TARGET", lab, day=TODAY)
    _, _, _ = _new_visit(db_session, "COMPETING-ROUTE", non_lab)
    _, _, _ = _new_visit(db_session, "CANCELED", lab, status="cancelled")
    _, same_patient_visit, _ = _new_visit(
        db_session, "TARGET", lab, patient=last_patient
    )
    # A visit that predates the worklist's first page still counts and is searchable.
    first = _search(db_session, limit=50)
    assert first.date == TODAY
    assert first.total == first.counts.actionable == 54
    assert count_lab_worklist(db_session, CLINIC_TZ, now=NOW) == first.counts
    assert first.counts.today == 1
    assert first.entries[0].id == f"visit:{earliest.id}"
    assert first.entries[0].service_details[0].can_cancel
    assert all(row.visit_id != last.id for row in first.entries)
    assert first.next_cursor is not None
    next_page = _search(db_session, limit=50, cursor=first.next_cursor)
    assert [
        row.id for row in next_page.entries if row.patient_id == last_patient.id
    ] == [
        f"visit:{same_patient_visit.id}",
        f"visit:{last.id}",
    ]
    assert next_page.next_cursor is None
    assert not {row.id for row in first.entries}.intersection(
        row.id for row in next_page.entries
    )
    outside_first_page = _search(db_session, q=f"visit:{last.id}")
    assert outside_first_page.total == outside_first_page.counts.actionable == 1
    assert outside_first_page.entries[0].visit_id == last.id
    assert _search(db_session, q="synthetic-worklist-target").total == 2
    assert _search(db_session, q="%_").total == 0
    assert _search(db_session, view="today").total == 1
    with pytest.raises(InvalidWorklistCursor):
        _search(db_session, limit=50, cursor=first.next_cursor, view="today")
    anchor = _search(db_session, limit=1)
    earliest.status = "canceled"
    db_session.flush()
    with pytest.raises(InvalidWorklistCursor):
        _search(db_session, cursor=anchor.next_cursor)


def test_worklist_preserves_release_across_correction_and_scans_exact_specimen(
    db_session,
):
    lab, _ = _catalog(db_session)
    patient, visit, line = _new_visit(db_session, "CORRECTION", lab)
    _, unassigned_visit, _ = _new_visit(
        db_session, "CORRECTION", lab, patient=patient, day=TODAY
    )
    order = LabOrder(
        patient_id=patient.id,
        visit_id=visit.id,
        due_at=datetime(2012, 1, 4, 19, 0, tzinfo=UTC),
        priority="urgent",
    )
    other_order = LabOrder(patient_id=patient.id, visit_id=visit.id)
    template = LabReportTemplate(
        code="SYNTHETIC-QUEUE", name="SYNTHETIC-QUEUE", family="SYNTHETIC"
    )
    db_session.add_all([order, other_order, template])
    db_session.flush()
    version = LabReportTemplateVersion(
        template_id=template.id, version_no=1, layout_preset="default"
    )
    db_session.add(version)
    db_session.flush()
    released = LabReportInstance(
        order_id=order.id,
        visit_id=visit.id,
        patient_id=patient.id,
        template_id=template.id,
        template_version_id=version.id,
        status="FINALIZED",
        finalized_at=NOW,
    )
    db_session.add(released)
    db_session.flush()
    allocation = LabOrderTest(
        order_id=order.id, visit_service_id=line.id, report_instance_id=released.id
    )
    specimen = LabSpecimen(
        order_id=order.id,
        barcode="SYNTHETIC-AB123",
        material_code="SYNTHETIC",
        container_code="SYNTHETIC",
        status="accepted",
        revision=1,
        created_at=NOW,
        create_request_id="synthetic-scan",
    )
    db_session.add_all([allocation, specimen])
    db_session.flush()

    assert _search(db_session, view="ready").total == 1
    scanned = _search(db_session, barcode=specimen.barcode.lower())
    assert scanned.total == 1 and scanned.counts.ready == 1
    assert scanned.entries[0].id == f"order:{order.id}"
    assert scanned.entries[0].work_date == YESTERDAY
    assert scanned.entries[0].specimen_ids == [specimen.id]
    assert scanned.entries[0].progress.released_tests == 1
    assert _search(db_session, barcode="SYNTHETIC-AB12").total == 0

    # A correction is new work against the same order, and the original
    # remains released until the correction is successfully published.
    correction = LabReportInstance(
        order_id=order.id,
        visit_id=visit.id,
        patient_id=patient.id,
        template_id=template.id,
        template_version_id=version.id,
        status="READY",
        supersedes_instance_id=released.id,
    )
    db_session.add(correction)
    db_session.flush()
    result = _search(db_session, view="overdue")
    assert result.total == result.counts.in_review == 1
    row = result.entries[0]
    assert row.report_instance_id == correction.id
    assert row.status == "in_review"
    assert row.progress.total_reports == row.progress.released_reports == 1
    assert row.priority == "urgent"
    assert row.service_details[0].visit_service_id == line.id
    assert not row.service_details[0].can_cancel
    assert _search(db_session, q=lab.name).total == 2
    assert {row.id for row in _search(db_session).entries} == {
        f"order:{order.id}",
        f"order:{other_order.id}",
        f"visit:{unassigned_visit.id}",
    }


def test_first_specimen_moves_exact_requisition_to_its_order(
    client, db_session, auth_headers
):
    lab, _ = _catalog(db_session)
    patient, visit, line = _new_visit(db_session, "BEFORE-REPORT", lab)
    assert [row.id for row in _search(db_session).entries] == [f"visit:{visit.id}"]

    response = client.post(
        f"/api/v1/lab/visits/{visit.id}/specimens",
        headers=auth_headers,
        json={
            "material_code": "synthetic",
            "container_code": "synthetic",
            "request_id": str(uuid4()),
            "visit_service_ids": [line.id],
        },
    )
    assert response.is_success, response.text
    specimen = response.json()
    order_id = specimen["order_id"]
    other = LabOrder(patient_id=patient.id, visit_id=visit.id)
    db_session.add(other)
    db_session.flush()

    page = _search(db_session, q=f"visit:{visit.id}")
    assert {row.id for row in page.entries} == {
        f"order:{order_id}",
        f"order:{other.id}",
    }
    assert page.total == 2
    scoped = _search(db_session, barcode=specimen["barcode"])
    row = scoped.entries[0]
    assert scoped.total == 1 and row.order_id == order_id
    assert row.status == "awaiting_specimen"
    assert row.progress.ordered_tests == 1 and row.progress.released_tests == 0
    assert row.service_details[0].visit_service_id == line.id
    assert row.service_details[0].can_cancel
    assert _search(db_session, q=lab.name).total == 1

    conflicting_collection = client.post(
        f"/api/v1/lab/orders/{other.id}/specimens",
        headers=auth_headers,
        json={
            "material_code": "synthetic",
            "container_code": "synthetic",
            "request_id": str(uuid4()),
            "visit_service_ids": [line.id],
        },
    )
    assert conflicting_collection.status_code == 409
    other_report = SimpleNamespace(
        order=other, order_id=other.id, patient_id=patient.id, visit_id=visit.id
    )
    with pytest.raises(LabReportingDomainError, match="specimen custody in another"):
        LabReportingService(db_session)._claim_ordered_services(
            other_report, [line.id], "unused"
        )
    wrong_order = client.post(
        f"/api/v1/lab/visits/{visit.id}/tests/{line.id}/cancel",
        headers=auth_headers,
        json={"order_id": other.id, "reason": "SYNTHETIC-CROSS-ORDER"},
    )
    assert wrong_order.status_code == 409

    # Old inconsistent custody data remains visible without proposing either order.
    competing_specimen = LabSpecimen(
        order_id=other.id,
        barcode="SYNTHETIC-COMPETITION",
        material_code="synthetic",
        container_code="synthetic",
        status="expected",
        revision=1,
        created_at=NOW,
        create_request_id=str(uuid4()),
    )
    db_session.add(competing_specimen)
    db_session.flush()
    db_session.add(
        LabSpecimenAssignment(
            specimen_id=competing_specimen.id, visit_service_id=line.id
        )
    )
    db_session.flush()
    disputed = next(
        row for row in _search(db_session).entries if row.id == f"visit:{visit.id}"
    )
    assert disputed.status == "held"
    assert disputed.hold_reason == "specimen_order_ambiguous"
    assert disputed.service_details[0].visit_service_id is None

    reconciled = client.post(
        f"/api/v1/lab/specimens/{competing_specimen.id}/assignments",
        headers=auth_headers,
        json={
            "operation": "remove",
            "reason": "SYNTHETIC-CUSTODY-RECONCILED",
            "expected_revision": 1,
            "request_id": str(uuid4()),
            "visit_service_ids": [line.id],
        },
    )
    assert reconciled.is_success, reconciled.text
    assert (
        _search(db_session, barcode=specimen["barcode"])
        .entries[0]
        .service_details[0]
        .visit_service_id
        == line.id
    )


def test_legacy_release_marks_unknown_lines_and_preserves_new_requisitions(db_session):
    lab, _ = _catalog(db_session)
    patient, visit, old_line = _new_visit(db_session, "LEGACY-COVERAGE", lab)
    old_line.created_at = NOW - timedelta(hours=2)
    order = LabOrder(patient_id=patient.id, visit_id=visit.id)
    template = LabReportTemplate(
        code="SYNTHETIC-LEGACY", name="SYNTHETIC-LEGACY", family="SYNTHETIC"
    )
    db_session.add_all([order, template])
    db_session.flush()
    version = LabReportTemplateVersion(
        template_id=template.id, version_no=1, layout_preset="standard"
    )
    db_session.add(version)
    db_session.flush()
    db_session.add(
        LabReportInstance(
            order_id=order.id,
            visit_id=visit.id,
            patient_id=patient.id,
            template_id=template.id,
            template_version_id=version.id,
            status="FINALIZED",
            finalized_at=NOW - timedelta(hours=1),
        )
    )
    db_session.flush()

    released = _search(db_session, view="ready").entries[0]
    assert released.order_id == order.id and released.progress.ordered_tests is None
    historical = _search(db_session).entries[0]
    assert historical.id == f"visit:{visit.id}" and historical.status == "held"
    assert historical.hold_reason == "historical_allocation_unknown"
    assert historical.service_details[0].visit_service_id is None
    assert not historical.service_details[0].can_cancel
    proposed = SimpleNamespace(
        order=order, order_id=order.id, patient_id=patient.id, visit_id=visit.id
    )
    with pytest.raises(LabReportingDomainError, match="unconfirmed historical"):
        LabReportingService(db_session)._claim_ordered_services(
            proposed, [old_line.id], template.code
        )

    new_line = VisitService(
        visit_id=visit.id,
        service_id=lab.id,
        name="SYNTHETIC-NEW-REQUEST",
        created_at=NOW,
    )
    db_session.add(new_line)
    db_session.flush()
    pending = _search(db_session, q="SYNTHETIC-NEW-REQUEST").entries[0]
    assert pending.id == historical.id and pending.status == "pending"
    assert [item.visit_service_id for item in pending.service_details] == [
        None,
        new_line.id,
    ]
    assert pending.service_details[1].can_cancel


def test_worklist_api_audits_each_returned_patient_without_search_text(
    client, db_session, auth_headers, caplog
):
    lab, _ = _catalog(db_session)
    patient, visit, _ = _new_visit(db_session, "AUDIT", lab)
    endpoint = "/api/v1/lab/worklist/search"
    assert client.post(endpoint, json={}).status_code in (401, 403)
    response = client.post(
        endpoint, json={"q": "synthetic-worklist-audit"}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert [row["visit_id"] for row in response.json()["entries"]] == [visit.id]
    audit = (
        db_session.execute(
            select(PatientAccessAuditLog).where(
                PatientAccessAuditLog.subject_patient_id == patient.id,
                PatientAccessAuditLog.resource_type == "lab_worklist",
            )
        )
        .scalars()
        .one()
    )
    assert audit.resource_id == f"visit:{visit.id}"
    assert audit.action == "read"
    assert audit.extra_data is None
    malformed_query = "SYNTHETIC-UNLOGGED-SEARCH" * 10
    rejected = client.post(endpoint, json={"q": malformed_query}, headers=auth_headers)
    assert rejected.status_code == 422
    assert "SYNTHETIC-UNLOGGED-SEARCH" not in rejected.text
    assert "SYNTHETIC-UNLOGGED-SEARCH" not in caplog.text


def test_cancel_unreported_line_is_idempotent_and_remains_out_of_active_list(
    client, db_session, auth_headers
):
    lab, non_lab = _catalog(db_session)
    _, visit, line = _new_visit(db_session, "LINE-CANCEL", lab)
    _, _, unrelated = _new_visit(db_session, "NONLAB-LINE", non_lab)
    endpoint = f"/api/v1/lab/visits/{visit.id}/tests/{line.id}/cancel"

    assert (
        client.post(endpoint, json={"reason": ""}, headers=auth_headers).status_code
        == 422
    )
    mismatch = client.post(
        f"/api/v1/lab/visits/{visit.id}/tests/{unrelated.id}/cancel",
        json={"reason": "Synthetic cross-visit refusal"},
        headers=auth_headers,
    )
    assert mismatch.status_code == 404
    response = client.post(
        endpoint, json={"reason": "Synthetic collection canceled"}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    replay = client.post(
        endpoint, json={"reason": "Synthetic collection canceled"}, headers=auth_headers
    )
    assert replay.json() == response.json()
    assert (
        client.post(
            endpoint, json={"reason": "Synthetic second reason"}, headers=auth_headers
        ).status_code
        == 409
    )
    assert _search(db_session).total == 0
    canceled_order = response.json()["order_id"]
    canceled_collection = client.post(
        f"/api/v1/lab/orders/{canceled_order}/specimens",
        headers=auth_headers,
        json={
            "material_code": "synthetic",
            "container_code": "synthetic",
            "request_id": str(uuid4()),
            "visit_service_ids": [line.id],
        },
    )
    assert canceled_collection.status_code == 409


def test_order_schedule_is_explicit_and_rejects_missing_timezone(
    client, db_session, auth_headers
):
    route = "/api/v1/lab/orders"
    template_list = client.get("/api/v1/lab/templates", headers=auth_headers).json()
    template = next(row for row in template_list if row["code"] == "cbc_oak")
    patient = Patient(first_name="SYNTHETIC-LAB", last_name="SYNTHETIC-SCHEDULE")
    db_session.add(patient)
    db_session.flush()
    data = {
        "template_id": template["id"],
        "patient_id": patient.id,
        "priority": "urgent",
    }
    assert (
        client.post(
            route, json={**data, "due_at": "2012-01-05T00:00:00"}, headers=auth_headers
        ).status_code
        == 422
    )
    response = client.post(
        route,
        json={**data, "due_at": "2012-01-05T00:00:00+05:00"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    report_id = response.json()["instance_id"]
    row = _search(db_session, q=f"report:{report_id}", view="overdue").entries[0]
    assert row.priority == "urgent"
    assert row.due_at.replace(tzinfo=UTC) == datetime(2012, 1, 4, 19, tzinfo=UTC)
