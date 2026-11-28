from __future__ import annotations

import ast
from pathlib import Path

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "api"
    / "v1"
    / "endpoints"
    / "appointment_flow.py"
)

WRITE_HANDLERS = {
    "create_or_update_emr",
    "save_emr",
    "create_or_update_prescription",
    "save_prescription",
    "complete_visit",
}

READ_HANDLERS = {
    "get_emr",
    "get_prescription",
    "get_appointment_status",
    "resolve_canonical_visit",
}


def _functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _resolve_calls(fn: ast.FunctionDef) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_resolve_appointment_and_visit"
        ):
            calls.append(node)
    return calls


def _allow_visit_fallback_kw(call: ast.Call) -> bool | None:
    for keyword in call.keywords:
        if keyword.arg == "allow_visit_fallback":
            return keyword.value.value if isinstance(keyword.value, ast.Constant) else None
    return None


def test_clinical_write_handlers_disable_legacy_visit_id_fallback() -> None:
    functions = _functions()

    for handler_name in WRITE_HANDLERS:
        calls = _resolve_calls(functions[handler_name])
        assert calls, f"{handler_name} must resolve appointment/visit before writing"
        assert any(_allow_visit_fallback_kw(call) is False for call in calls), (
            f"{handler_name} must not silently treat a missing appointment_id as visit_id"
        )


def test_read_handlers_keep_legacy_visit_id_fallback() -> None:
    functions = _functions()

    for handler_name in READ_HANDLERS:
        calls = _resolve_calls(functions[handler_name])
        assert calls, f"{handler_name} must resolve appointment/visit before reading"
        assert all(_allow_visit_fallback_kw(call) is not False for call in calls), (
            f"{handler_name} should remain read-compatible with legacy visit_id fallback"
        )


def test_manual_prescription_update_clears_emr_revision_provenance(
    client, db_session, auth_headers, test_visit, monkeypatch
):
    monkeypatch.setattr(settings, "EMR_LEGACY_WRITE_FREEZE", False)
    appointment = Appointment(
        patient_id=test_visit.patient_id,
        doctor_id=test_visit.doctor_id,
        appointment_date=test_visit.visit_date,
        appointment_time=test_visit.visit_time,
        status=AppointmentStatus.IN_VISIT,
    )
    db_session.add(appointment)
    db_session.commit()

    root = f"/api/v1/v2/emr/{test_visit.id}"
    drug = {
        "name": "SYNTHETIC Medication",
        "dosage": "SYNTHETIC Dose",
        "frequency": "SYNTHETIC Frequency",
        "duration": "SYNTHETIC Duration",
        "quantity": 2,
    }
    saved_response = client.post(
        root,
        headers=auth_headers,
        json={
            "is_draft": False,
            "data": {"specialty": "cardiology", "medications": {"list": [drug]}},
        },
    )
    assert saved_response.status_code == 200, saved_response.text
    saved = saved_response.json()
    prescription = f"{root}/workspace/prescription"
    issued_response = client.post(
        prescription,
        headers=auth_headers,
        json={
            "patient_id": test_visit.patient_id,
            "expected_row_version": saved["row_version"],
        },
    )
    assert issued_response.status_code == 200, issued_response.text
    assert issued_response.json()["emr_version"] == saved["version"]

    manual_response = client.post(
        f"/api/v1/appointments/{appointment.id}/prescription",
        headers=auth_headers,
        json={
            "appointment_id": appointment.id,
            "medications": [{**drug, "quantity": 3}],
            "is_draft": False,
        },
    )
    assert manual_response.status_code == 200, manual_response.text
    manual = manual_response.json()
    assert manual["id"] == issued_response.json()["id"]
    assert manual["visit_id"] == test_visit.id
    assert manual["emr_record_id"] == saved["id"]
    assert manual["medications"][0]["quantity"] == 3
    current = client.get(
        prescription, headers=auth_headers, params={"patient_id": test_visit.patient_id}
    )
    assert current.status_code == 200, current.text
    assert current.json()["emr_version"] is None
