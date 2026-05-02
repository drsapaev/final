from __future__ import annotations

from datetime import date

import pytest

from app.models.appointment import Appointment
from app.models.service import Service
from app.models.visit import VisitService


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

    ready_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/mark-ready",
        headers=auth_headers,
    )
    assert ready_response.status_code == 200

    finalize_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/finalize",
        headers=auth_headers,
    )
    assert finalize_response.status_code == 200
    assert finalize_response.json()["status"] == "FINALIZED"

    print_once_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/mark-printed",
        headers=auth_headers,
    )
    assert print_once_response.status_code == 200
    assert print_once_response.json()["status"] == "PRINTED"

    print_twice_response = client.post(
        f"/api/v1/lab/report-instances/{instance['id']}/mark-printed",
        headers=auth_headers,
    )
    assert print_twice_response.status_code == 200
    assert print_twice_response.json()["status"] == "PRINTED"


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
