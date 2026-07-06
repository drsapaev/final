from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.emr import EMR
from app.models.lab import LabOrder, LabResult
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.models.visit import VisitService


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = _suffix()
    user = User(
        username=f"lab_report_{label}_{suffix}",
        email=f"lab-report-{label}-{suffix}@test.local",
        full_name=f"Lab Report {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="therapy",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_patient(db_session) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name="Lab",
        last_name=f"Report{suffix}",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_visit(db_session, *, patient_id: int, doctor_id: int) -> Visit:
    visit = Visit(
        patient_id=patient_id,
        doctor_id=doctor_id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _create_lab_report_instance(
    client,
    *,
    auth_headers: dict[str, str],
    patient_id: int,
    visit_id: int,
) -> dict:
    templates_response = client.get("/api/v1/lab/templates", headers=auth_headers)
    assert templates_response.status_code == 200
    cbc_template = next(
        template for template in templates_response.json() if template["code"] == "cbc_oak"
    )
    response = client.post(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "visit_id": visit_id,
            "template_id": cbc_template["id"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_legacy_lab_result(
    db_session,
    *,
    patient_id: int,
    visit_id: int,
    test_code: str,
    value: str,
) -> LabResult:
    order = LabOrder(
        patient_id=patient_id,
        visit_id=visit_id,
        status="done",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    result = LabResult(
        order_id=order.id,
        test_code=test_code,
        test_name=test_code.title(),
        value=value,
        unit="g/L",
        ref_range="120-160",
        abnormal=False,
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    return result


def _create_appointment(
    db_session,
    *,
    patient_id: int,
    doctor_id: int,
) -> Appointment:
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        appointment_date=date.today(),
        appointment_time="09:00",
        status="scheduled",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


def _create_emr(
    db_session,
    *,
    appointment_id: int,
) -> EMR:
    emr = EMR(
        appointment_id=appointment_id,
        lab_results={},
    )
    db_session.add(emr)
    db_session.commit()
    db_session.refresh(emr)
    return emr


@pytest.mark.integration
def test_lab_template_version_actions_are_backend_owned(client, auth_headers):
    templates_response = client.get("/api/v1/lab/templates", headers=auth_headers)
    assert templates_response.status_code == 200
    cbc_template = next(
        template for template in templates_response.json() if template["code"] == "cbc_oak"
    )

    detail_response = client.get(
        f"/api/v1/lab/templates/{cbc_template['id']}", headers=auth_headers
    )
    assert detail_response.status_code == 200
    template_detail = detail_response.json()
    source_version_id = (
        template_detail["draft_version_id"]
        or template_detail["published_version_id"]
        or template_detail["latest_version_id"]
    )
    source = next(
        version
        for version in template_detail["versions"]
        if version["id"] == source_version_id
    )

    if source["status"] == "DRAFT":
        assert set(source["available_actions"]) == {"update", "publish"}
        assert source["can_update"] is True
        assert source["can_publish"] is True
        assert source["can_create_draft"] is False

        publish_response = client.post(
            f"/api/v1/lab/template-versions/{source['id']}/publish",
            headers=auth_headers,
        )
        assert publish_response.status_code == 200
        published = publish_response.json()
    else:
        published = source

    assert published["status"] == "PUBLISHED"
    assert published["available_actions"] == ["create_draft"]
    assert published["can_update"] is False
    assert published["can_publish"] is False
    assert published["can_create_draft"] is True

    new_draft_response = client.post(
        f"/api/v1/lab/templates/{cbc_template['id']}/versions",
        headers=auth_headers,
        json={"source_version_id": published["id"]},
    )
    assert new_draft_response.status_code == 200
    new_draft = new_draft_response.json()
    assert new_draft["status"] == "DRAFT"
    assert set(new_draft["available_actions"]) == {"update", "publish"}
    assert new_draft["can_update"] is True
    assert new_draft["can_publish"] is True
    assert new_draft["can_create_draft"] is False


@pytest.mark.integration
def test_lab_reporting_api_flow(client, auth_headers, db_session, test_patient, test_visit):
    test_patient.sex = "M"
    test_patient.birth_date = date(1990, 1, 1)
    db_session.commit()

    templates_response = client.get("/api/v1/lab/templates", headers=auth_headers)
    assert templates_response.status_code == 200
    templates = templates_response.json()
    cbc_template = next(template for template in templates if template["code"] == "cbc_oak")
    assert any(template["code"] == "urinalysis_oam" for template in templates)
    ige_template = next(template for template in templates if template["code"] == "ige_total")
    assert any(template["code"] == "vitamin_d_panel" for template in templates)
    assert any(template["code"] == "hba1c_panel" for template in templates)
    assert any(template["code"] == "testosterone_panel" for template in templates)

    instance_response = client.post(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        json={
            "patient_id": test_patient.id,
            "visit_id": test_visit.id,
            "template_id": cbc_template["id"],
        },
    )
    assert instance_response.status_code == 200
    instance = instance_response.json()
    assert instance["status"] == "DRAFT"
    assert set(instance["available_actions"]) == {
        "edit",
        "save_draft",
        "mark_ready",
        "finalize",
    }
    assert instance["can_edit"] is True
    assert instance["can_save_draft"] is True
    assert instance["can_mark_ready"] is True
    assert instance["can_finalize"] is True
    assert instance["can_revise"] is False
    assert instance["can_print"] is False
    assert instance["signer_snapshot"]["lab_technician_name"] == "Test Admin"
    assert instance["signer_snapshot"]["approver_name"] == "Test Admin"

    bulk_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/bulk-values",
        headers=auth_headers,
        json=[
            {"field_key": "wbc", "value_text": "6.1"},
            {"field_key": "hgb", "value_text": "100"},
        ],
    )
    assert bulk_response.status_code == 200
    payload = bulk_response.json()
    assert payload["instance"]["status"] == "IN_PROGRESS"
    assert set(payload["updated_field_keys"]) == {"wbc", "hgb"}
    hgb_field = next(
        field
        for section in payload["instance"]["sections"]
        for field in section["fields"]
        if field["field_key"] == "hgb"
    )
    assert hgb_field["resolved_flag"] is None
    assert hgb_field["reference_mode"] == "static_text"
    assert hgb_field["resolved_flag_source"] is None
    assert hgb_field["resolved_flag_severity"] is None
    assert hgb_field["resolved_flag_meta"] is None
    assert payload["instance"]["critical_findings"] == []

    history_response = client.get(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        params={"patient_id": test_patient.id},
    )
    assert history_response.status_code == 200
    history = history_response.json()
    summary = next(item for item in history if item["id"] == instance["id"])
    assert summary["visit_id"] == test_visit.id
    assert summary["flagged_findings_count"] == 0
    assert summary["critical_findings_count"] == 0
    assert summary["max_flag_severity"] is None
    assert summary["can_edit"] is True
    assert summary["can_finalize"] is True
    assert summary["can_revise"] is False
    assert summary["can_print"] is False

    visit_history_response = client.get(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        params=[("visit_ids", str(test_visit.id))],
    )
    assert visit_history_response.status_code == 200
    visit_history = visit_history_response.json()
    assert any(item["id"] == instance["id"] for item in visit_history)
    assert all(item["visit_id"] == test_visit.id for item in visit_history)

    analytes_response = client.get("/api/v1/lab/catalog/analytes", headers=auth_headers)
    assert analytes_response.status_code == 200
    analytes = analytes_response.json()
    assert any(item["code"] == "hgb" for item in analytes)

    ranges_response = client.get(
        "/api/v1/lab/catalog/reference-ranges",
        headers=auth_headers,
        params={"analyte_code": "hgb"},
    )
    assert ranges_response.status_code == 200
    ranges = ranges_response.json()
    assert any(item["sex"] == "M" and item["low"] == "130.0000" for item in ranges)

    ige_instance_response = client.post(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        json={
            "patient_id": test_patient.id,
            "template_id": ige_template["id"],
        },
    )
    assert ige_instance_response.status_code == 200
    ige_instance = ige_instance_response.json()

    ige_bulk_response = client.post(
        f"/api/v1/lab/report-instances/{ige_instance['id']}/bulk-values",
        headers=auth_headers,
        json=[{"field_key": "total_ige", "value_text": "150"}],
    )
    assert ige_bulk_response.status_code == 200
    ige_payload = ige_bulk_response.json()
    ige_field = next(
        field
        for section in ige_payload["instance"]["sections"]
        for field in section["fields"]
        if field["field_key"] == "total_ige"
    )
    assert ige_field["reference_mode"] == "catalog"
    assert ige_field["reference_text"] == "< 130 МЕ/мл"
    assert ige_field["resolved_flag"] == "high"
    assert ige_field["resolved_flag_source"] == "catalog_reference"

    # /mark-ready endpoint was removed (L-2 fix: it was functionally empty —
    # backend allows the same actions for DRAFT/IN_PROGRESS/READY statuses).
    # Skip directly to /finalize, which is permitted from any non-FINALIZED status.

    finalize_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/finalize",
        headers=auth_headers,
    )
    assert finalize_response.status_code == 200
    finalized = finalize_response.json()
    assert finalized["status"] == "FINALIZED"
    assert set(finalized["available_actions"]) == {"revise", "print"}
    assert finalized["can_edit"] is False
    assert finalized["can_save_draft"] is False
    assert finalized["can_mark_ready"] is False
    assert finalized["can_finalize"] is False
    assert finalized["can_revise"] is True
    assert finalized["can_print"] is True

    print_once_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/mark-printed",
        headers=auth_headers,
    )
    assert print_once_response.status_code == 200
    printed = print_once_response.json()
    assert printed["status"] == "PRINTED"
    assert set(printed["available_actions"]) == {"revise", "print"}
    assert printed["can_edit"] is False
    assert printed["can_revise"] is True
    assert printed["can_print"] is True

    print_twice_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/mark-printed",
        headers=auth_headers,
    )
    assert print_twice_response.status_code == 200
    assert print_twice_response.json()["status"] == "PRINTED"


@pytest.mark.integration
def test_doctor_lab_report_reads_are_limited_to_own_visits(
    client,
    auth_headers,
    db_session,
) -> None:
    own_user, own_doctor = _create_doctor_user(db_session, label="own")
    _other_user, other_doctor = _create_doctor_user(db_session, label="other")
    own_patient = _create_patient(db_session)
    other_patient = _create_patient(db_session)
    own_visit = _create_visit(
        db_session,
        patient_id=own_patient.id,
        doctor_id=own_doctor.id,
    )
    other_visit = _create_visit(
        db_session,
        patient_id=other_patient.id,
        doctor_id=other_doctor.id,
    )
    own_instance = _create_lab_report_instance(
        client,
        auth_headers=auth_headers,
        patient_id=own_patient.id,
        visit_id=own_visit.id,
    )
    other_instance = _create_lab_report_instance(
        client,
        auth_headers=auth_headers,
        patient_id=other_patient.id,
        visit_id=other_visit.id,
    )
    doctor_headers = _doctor_headers(client, own_user)

    own_detail = client.get(
        f"/api/v1/lab/report-instances/{own_instance['id']}",
        headers=doctor_headers,
    )
    assert own_detail.status_code == 200, own_detail.text

    other_detail = client.get(
        f"/api/v1/lab/report-instances/{other_instance['id']}",
        headers=doctor_headers,
    )
    assert other_detail.status_code == 403

    list_response = client.get(
        "/api/v1/lab/report-instances",
        headers=doctor_headers,
    )
    assert list_response.status_code == 200, list_response.text
    listed_ids = {item["id"] for item in list_response.json()}
    assert own_instance["id"] in listed_ids
    assert other_instance["id"] not in listed_ids

    other_visit_list = client.get(
        "/api/v1/lab/report-instances",
        params=[("visit_ids", str(other_visit.id))],
        headers=doctor_headers,
    )
    assert other_visit_list.status_code == 403

    other_pdf = client.get(
        f"/api/v1/lab/report-instances/{other_instance['id']}/pdf",
        headers=doctor_headers,
    )
    assert other_pdf.status_code == 403


@pytest.mark.integration
def test_doctor_emr_lab_reads_are_limited_to_own_patients(
    client,
    db_session,
) -> None:
    own_user, own_doctor = _create_doctor_user(db_session, label="emr_own")
    _other_user, other_doctor = _create_doctor_user(db_session, label="emr_other")
    own_patient = _create_patient(db_session)
    other_patient = _create_patient(db_session)
    own_visit = _create_visit(
        db_session,
        patient_id=own_patient.id,
        doctor_id=own_doctor.id,
    )
    other_visit = _create_visit(
        db_session,
        patient_id=other_patient.id,
        doctor_id=other_doctor.id,
    )
    own_result = _create_legacy_lab_result(
        db_session,
        patient_id=own_patient.id,
        visit_id=own_visit.id,
        test_code="hemoglobin",
        value="130",
    )
    _create_legacy_lab_result(
        db_session,
        patient_id=other_patient.id,
        visit_id=other_visit.id,
        test_code="hemoglobin",
        value="80",
    )
    doctor_headers = _doctor_headers(client, own_user)

    own_results = client.get(
        f"/api/v1/emr/lab/patients/{own_patient.id}/lab-results",
        headers=doctor_headers,
    )
    assert own_results.status_code == 200, own_results.text
    own_payload = own_results.json()
    assert own_payload["patient_id"] == own_patient.id
    assert {item["id"] for item in own_payload["results"]} == {own_result.id}

    other_results = client.get(
        f"/api/v1/emr/lab/patients/{other_patient.id}/lab-results",
        headers=doctor_headers,
    )
    assert other_results.status_code == 403

    other_abnormal_results = client.get(
        f"/api/v1/emr/lab/patients/{other_patient.id}/abnormal-lab-results",
        headers=doctor_headers,
    )
    assert other_abnormal_results.status_code == 403

    other_trends = client.get(
        "/api/v1/emr/lab/lab-results/trends",
        params={"patient_id": other_patient.id, "test_type": "hemoglobin"},
        headers=doctor_headers,
    )
    assert other_trends.status_code == 403

    other_summary = client.get(
        "/api/v1/emr/lab/emr/123/lab-summary",
        params={"patient_id": other_patient.id},
        headers=doctor_headers,
    )
    assert other_summary.status_code == 403


@pytest.mark.integration
def test_doctor_emr_lab_integrate_is_limited_to_owned_emr_and_patient_results(
    client,
    db_session,
) -> None:
    own_user, own_doctor = _create_doctor_user(db_session, label="integrate_own")
    _other_user, other_doctor = _create_doctor_user(
        db_session,
        label="integrate_other",
    )
    own_patient = _create_patient(db_session)
    other_patient = _create_patient(db_session)
    own_visit = _create_visit(
        db_session,
        patient_id=own_patient.id,
        doctor_id=own_doctor.id,
    )
    other_visit = _create_visit(
        db_session,
        patient_id=other_patient.id,
        doctor_id=other_doctor.id,
    )
    own_emr = _create_emr(
        db_session,
        appointment_id=_create_appointment(
            db_session,
            patient_id=own_patient.id,
            doctor_id=own_doctor.id,
        ).id,
    )
    other_emr = _create_emr(
        db_session,
        appointment_id=_create_appointment(
            db_session,
            patient_id=other_patient.id,
            doctor_id=other_doctor.id,
        ).id,
    )
    own_result = _create_legacy_lab_result(
        db_session,
        patient_id=own_patient.id,
        visit_id=own_visit.id,
        test_code="hemoglobin",
        value="130",
    )
    other_result = _create_legacy_lab_result(
        db_session,
        patient_id=other_patient.id,
        visit_id=other_visit.id,
        test_code="glucose",
        value="7",
    )
    doctor_headers = _doctor_headers(client, own_user)

    own_response = client.post(
        f"/api/v1/emr/lab/emr/{own_emr.id}/integrate-lab-results",
        json=[own_result.id],
        headers=doctor_headers,
    )
    assert own_response.status_code == 200, own_response.text
    db_session.refresh(own_emr)
    assert own_emr.lab_results["hemoglobin"][0]["id"] == own_result.id

    foreign_emr_response = client.post(
        f"/api/v1/emr/lab/emr/{other_emr.id}/integrate-lab-results",
        json=[own_result.id],
        headers=doctor_headers,
    )
    assert foreign_emr_response.status_code == 403
    db_session.refresh(other_emr)
    assert other_emr.lab_results == {}

    foreign_result_response = client.post(
        f"/api/v1/emr/lab/emr/{own_emr.id}/integrate-lab-results",
        json=[other_result.id],
        headers=doctor_headers,
    )
    assert foreign_result_response.status_code == 403
    db_session.refresh(own_emr)
    assert "glucose" not in own_emr.lab_results


@pytest.mark.integration
def test_admin_emr_lab_integrate_rejects_cross_patient_result(
    client,
    auth_headers,
    db_session,
    test_doctor,
) -> None:
    own_patient = _create_patient(db_session)
    other_patient = _create_patient(db_session)
    own_visit = _create_visit(
        db_session,
        patient_id=own_patient.id,
        doctor_id=test_doctor.id,
    )
    other_visit = _create_visit(
        db_session,
        patient_id=other_patient.id,
        doctor_id=test_doctor.id,
    )
    own_emr = _create_emr(
        db_session,
        appointment_id=_create_appointment(
            db_session,
            patient_id=own_patient.id,
            doctor_id=test_doctor.id,
        ).id,
    )
    other_result = _create_legacy_lab_result(
        db_session,
        patient_id=other_patient.id,
        visit_id=other_visit.id,
        test_code="glucose",
        value="7",
    )
    own_result = _create_legacy_lab_result(
        db_session,
        patient_id=own_patient.id,
        visit_id=own_visit.id,
        test_code="hemoglobin",
        value="130",
    )

    foreign_result_response = client.post(
        f"/api/v1/emr/lab/emr/{own_emr.id}/integrate-lab-results",
        json=[other_result.id],
        headers=auth_headers,
    )
    assert foreign_result_response.status_code == 404
    db_session.refresh(own_emr)
    assert own_emr.lab_results == {}

    own_result_response = client.post(
        f"/api/v1/emr/lab/emr/{own_emr.id}/integrate-lab-results",
        json=[own_result.id],
        headers=auth_headers,
    )
    assert own_result_response.status_code == 200, own_result_response.text
    db_session.refresh(own_emr)
    assert own_emr.lab_results["hemoglobin"][0]["id"] == own_result.id
    assert "glucose" not in own_emr.lab_results


@pytest.mark.integration
def test_emr_lab_notify_doctor_rejects_cross_patient_result(
    client,
    auth_headers,
    db_session,
    test_doctor,
) -> None:
    own_patient = _create_patient(db_session)
    other_patient = _create_patient(db_session)
    other_visit = _create_visit(
        db_session,
        patient_id=other_patient.id,
        doctor_id=test_doctor.id,
    )
    other_result = _create_legacy_lab_result(
        db_session,
        patient_id=other_patient.id,
        visit_id=other_visit.id,
        test_code="glucose",
        value="7",
    )

    response = client.post(
        f"/api/v1/emr/lab/lab-results/{other_result.id}/notify-doctor",
        params={"patient_id": own_patient.id, "doctor_id": test_doctor.id},
        headers=auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.integration
def test_doctor_emr_lab_notify_doctor_is_limited_to_owned_patient(
    client,
    db_session,
) -> None:
    own_user, own_doctor = _create_doctor_user(db_session, label="notify_own")
    _other_user, other_doctor = _create_doctor_user(
        db_session,
        label="notify_other",
    )
    own_patient = _create_patient(db_session)
    other_patient = _create_patient(db_session)
    own_visit = _create_visit(
        db_session,
        patient_id=own_patient.id,
        doctor_id=own_doctor.id,
    )
    other_visit = _create_visit(
        db_session,
        patient_id=other_patient.id,
        doctor_id=other_doctor.id,
    )
    own_result = _create_legacy_lab_result(
        db_session,
        patient_id=own_patient.id,
        visit_id=own_visit.id,
        test_code="hemoglobin",
        value="130",
    )
    other_result = _create_legacy_lab_result(
        db_session,
        patient_id=other_patient.id,
        visit_id=other_visit.id,
        test_code="glucose",
        value="7",
    )
    doctor_headers = _doctor_headers(client, own_user)

    own_response = client.post(
        f"/api/v1/emr/lab/lab-results/{own_result.id}/notify-doctor",
        params={"patient_id": own_patient.id, "doctor_id": own_doctor.id},
        headers=doctor_headers,
    )
    assert own_response.status_code == 200, own_response.text
    assert own_response.json()["notification"]["result_id"] == own_result.id

    foreign_result_response = client.post(
        f"/api/v1/emr/lab/lab-results/{other_result.id}/notify-doctor",
        params={"patient_id": other_patient.id, "doctor_id": own_doctor.id},
        headers=doctor_headers,
    )
    assert foreign_result_response.status_code == 403

    wrong_doctor_response = client.post(
        f"/api/v1/emr/lab/lab-results/{own_result.id}/notify-doctor",
        params={"patient_id": own_patient.id, "doctor_id": other_doctor.id},
        headers=doctor_headers,
    )
    assert wrong_doctor_response.status_code == 403


@pytest.mark.integration
def test_lab_template_resolution_api_restricts_template_choices(
    client, auth_headers, db_session, test_patient, test_visit
):
    lab_service = Service(
        code="lab_oam",
        service_code="L25",
        name="Общий анализ мочи",
        active=True,
        requires_doctor=False,
        queue_tag="laboratory",
        is_consultation=False,
    )
    db_session.add(lab_service)
    db_session.flush()
    db_session.add(
        VisitService(
            visit_id=test_visit.id,
            service_id=lab_service.id,
            code="L25",
            name=lab_service.name,
            qty=1,
        )
    )
    db_session.commit()

    resolution_response = client.post(
        "/api/v1/lab/template-resolutions/resolve",
        headers=auth_headers,
        json={"patient_id": test_patient.id, "visit_id": test_visit.id},
    )
    assert resolution_response.status_code == 200
    resolution = resolution_response.json()
    assert resolution["resolution_mode"] == "mapped"
    assert resolution["service_codes"] == ["L25"]
    assert resolution["matched_service_codes"] == ["L25"]
    assert resolution["unmapped_service_codes"] == []
    assert [item["code"] for item in resolution["allowed_templates"]] == [
        "urinalysis_oam"
    ]
    assert resolution["default_template"]["code"] == "urinalysis_oam"

    templates_response = client.get("/api/v1/lab/templates", headers=auth_headers)
    assert templates_response.status_code == 200
    templates = templates_response.json()
    cbc_template = next(template for template in templates if template["code"] == "cbc_oak")
    oam_template = next(
        template for template in templates if template["code"] == "urinalysis_oam"
    )

    rejected_response = client.post(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        json={
            "patient_id": test_patient.id,
            "visit_id": test_visit.id,
            "template_id": cbc_template["id"],
        },
    )
    assert rejected_response.status_code == 409
    assert "not allowed" in rejected_response.json()["detail"]

    allowed_response = client.post(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        json={
            "patient_id": test_patient.id,
            "visit_id": test_visit.id,
            "template_id": oam_template["id"],
        },
    )
    assert allowed_response.status_code == 200
    assert allowed_response.json()["template"]["code"] == "urinalysis_oam"


@pytest.mark.integration
def test_lab_template_resolution_api_maps_real_catalog_code_l01_to_cbc(
    client, auth_headers, test_patient
):
    resolution_response = client.post(
        "/api/v1/lab/template-resolutions/resolve",
        headers=auth_headers,
        json={"patient_id": test_patient.id, "service_codes": ["L01"]},
    )
    assert resolution_response.status_code == 200
    resolution = resolution_response.json()
    assert resolution["resolution_mode"] == "mapped"
    assert resolution["service_codes"] == ["L01"]
    assert resolution["matched_service_codes"] == ["L01"]
    assert resolution["unmapped_service_codes"] == []
    assert [item["code"] for item in resolution["allowed_templates"]] == ["cbc_oak"]
    assert resolution["default_template"]["code"] == "cbc_oak"


@pytest.mark.integration
def test_lab_template_resolution_api_maps_live_glucose_code_l11_to_glucose_panel(
    client, auth_headers, test_patient
):
    resolution_response = client.post(
        "/api/v1/lab/template-resolutions/resolve",
        headers=auth_headers,
        json={"patient_id": test_patient.id, "service_codes": ["L11"]},
    )
    assert resolution_response.status_code == 200
    resolution = resolution_response.json()
    assert resolution["resolution_mode"] == "mapped"
    assert resolution["service_codes"] == ["L11"]
    assert resolution["matched_service_codes"] == ["L11"]
    assert resolution["unmapped_service_codes"] == []
    assert [item["code"] for item in resolution["allowed_templates"]] == [
        "glucose_panel"
    ]
    assert resolution["default_template"]["code"] == "glucose_panel"


@pytest.mark.integration
def test_lab_template_resolution_api_maps_vitamin_d_hba1c_and_testosterone(
    client, auth_headers, test_patient
):
    expectations = {
        "L23": "vitamin_d_panel",
        "L24": "hba1c_panel",
        "L54": "testosterone_panel",
    }

    for service_code, template_code in expectations.items():
        resolution_response = client.post(
            "/api/v1/lab/template-resolutions/resolve",
            headers=auth_headers,
            json={"patient_id": test_patient.id, "service_codes": [service_code]},
        )
        assert resolution_response.status_code == 200
        resolution = resolution_response.json()
        assert resolution["resolution_mode"] == "mapped"
        assert resolution["service_codes"] == [service_code]
        assert resolution["matched_service_codes"] == [service_code]
        assert resolution["unmapped_service_codes"] == []
        assert [item["code"] for item in resolution["allowed_templates"]] == [
            template_code
        ]
        assert resolution["default_template"]["code"] == template_code


@pytest.mark.integration
def test_lab_report_instance_api_resolves_visit_from_appointment_context(
    client, auth_headers, db_session, test_patient, test_doctor
):
    appointment = Appointment(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        appointment_date=date.today(),
        appointment_time="11:30",
        status="scheduled",
        services=["L24"],
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    templates_response = client.get("/api/v1/lab/templates", headers=auth_headers)
    assert templates_response.status_code == 200
    templates = templates_response.json()
    hba1c_template = next(
        template for template in templates if template["code"] == "hba1c_panel"
    )

    instance_response = client.post(
        "/api/v1/lab/report-instances",
        headers=auth_headers,
        json={
            "patient_id": test_patient.id,
            "appointment_id": appointment.id,
            "template_id": hba1c_template["id"],
            "service_codes": ["L24"],
        },
    )
    assert instance_response.status_code == 200
    instance = instance_response.json()
    assert instance["visit_id"] is not None
    assert instance["template"]["code"] == "hba1c_panel"


@pytest.mark.integration
def test_legacy_lab_contract_is_not_published(client, auth_headers):
    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]

    legacy_paths = {
        "/api/v1/lab",
        "/api/v1/lab/{req_id}",
        "/api/v1/lab/requests",
        "/api/v1/lab/requests/{req_id}",
        "/api/v1/lab/tests",
        "/api/v1/lab/results",
        "/api/v1/lab/reports",
        "/api/v1/lab/reference-ranges",
        "/api/v1/lab/equipment",
    }
    assert legacy_paths.isdisjoint(paths.keys())

    for route in (
        "/api/v1/lab",
        "/api/v1/lab/requests",
        "/api/v1/lab/tests",
        "/api/v1/lab/results",
        "/api/v1/lab/reports",
        "/api/v1/lab/reference-ranges",
        "/api/v1/lab/equipment",
    ):
        response = client.get(route, headers=auth_headers)
        assert response.status_code == 404
