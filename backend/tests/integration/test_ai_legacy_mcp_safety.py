"""End-to-end safety envelope tests with synthetic provider outputs only."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import ai, ai_integration, mcp


@pytest.fixture
def fake_medical_providers(monkeypatch):
    provider_result = {
        "status": "success",
        "success": True,
        "data": {"suggestions": ["SYNTHETIC-SUGGESTION"]},
        # Provider claims are never authoritative for the top-level boundary.
        "ai_safety_meta": {"requires_doctor_confirmation": False},
    }
    manager = SimpleNamespace(
        execute_request=AsyncMock(return_value=provider_result),
        batch_execute=AsyncMock(return_value=[{"data": "SYNTHETIC-SUGGESTION"}]),
    )

    async def get_manager():
        return manager

    monkeypatch.setattr(mcp, "get_mcp_manager", get_manager)
    monkeypatch.setattr(ai, "get_mcp_manager", get_manager)
    for name in ("analyze_complaint", "interpret_lab_results", "analyze_skin", "interpret_ecg"):
        monkeypatch.setattr(ai.ai_manager, name, AsyncMock(return_value=dict(provider_result)))
    monkeypatch.setattr(
        ai.ai_manager, "suggest_icd10",
        AsyncMock(return_value=[{"code": "SYNTHETIC-CODE"}]),
    )

    class FakeAIService:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def analyze_complaints(self, **kwargs):
            return dict(provider_result)

        async def suggest_icd10(self, **kwargs):
            return dict(provider_result)

        async def analyze_document(self, **kwargs):
            return dict(provider_result)

    async def get_service(_db):
        return FakeAIService()

    monkeypatch.setattr(ai_integration, "get_ai_service", get_service)
    return manager


def assert_safe(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    assert payload["ai_safety_meta"] == {"requires_doctor_confirmation": True}
    return payload


@pytest.mark.parametrize("path,body", [
    ("complaint-to-plan", {"complaint": "SYNTHETIC-COMPLAINT", "use_mcp": False}),
    ("lab-interpret", {"results": [{"name": "SYNTHETIC", "value": "1"}]}),
    ("ecg-interpret", {"parameters": {"synthetic": 1}}),
    ("analyze-complaints", {"complaints": "SYNTHETIC-COMPLAINT"}),
    ("suggest-icd10", {"diagnosis": "SYNTHETIC-DIAGNOSIS"}),
    ("analyze-document", {"document_text": "SYNTHETIC-DOCUMENT"}),
    ("interpret-lab-results", {"lab_results": "SYNTHETIC-RESULT"}),
    ("symptom-checker", {"symptoms": ["SYNTHETIC-SYMPTOM"]}),
    ("quick/diagnosis-help", {"symptoms": "SYNTHETIC-SYMPTOM"}),
])
def test_legacy_and_integration_medical_responses_have_server_marker(
    client, auth_headers, fake_medical_providers, path, body
):
    response = client.post(f"/api/v1/ai/{path}", headers=auth_headers, json=body)
    payload = assert_safe(response)
    if path != "quick/diagnosis-help":
        assert payload["status"] == "success"


def test_legacy_complaint_mcp_success_and_fallback_are_marked(
    client, auth_headers, fake_medical_providers
):
    body = {"complaint": "SYNTHETIC", "use_mcp": True}
    first = assert_safe(client.post("/api/v1/ai/complaint-to-plan", headers=auth_headers, json=body))
    assert first["suggestions"] == ["SYNTHETIC-SUGGESTION"]
    fake_medical_providers.execute_request.return_value = {"fallback": True}
    assert_safe(client.post("/api/v1/ai/complaint-to-plan", headers=auth_headers, json=body))


def test_legacy_icd_empty_and_nonempty_lists_have_envelopes(
    client, auth_headers, fake_medical_providers
):
    for expected in ([{"code": "SYNTHETIC-CODE"}], []):
        ai.ai_manager.suggest_icd10.return_value = expected
        result = assert_safe(client.post(
            "/api/v1/ai/icd-suggest", headers=auth_headers,
            json={"symptoms": ["SYNTHETIC"]},
        ))
        assert result["data"] == expected


@pytest.mark.parametrize("path,kwargs", [
    ("complaint/analyze", {"json": {"complaint": "SYNTHETIC"}}),
    ("complaint/validate", {"params": {"complaint": "SYNTHETIC"}}),
    ("icd10/suggest", {"json": {"symptoms": ["SYNTHETIC"]}}),
    ("icd10/validate", {"params": {"code": "SYNTHETIC"}}),
    ("lab/interpret", {"json": {"results": [{"name": "SYNTHETIC", "value": "1"}]}}),
    ("lab/check-critical", {"json": [{"name": "SYNTHETIC", "value": "1"}]}),
])
def test_mcp_medical_responses_have_server_marker(
    client, auth_headers, fake_medical_providers, path, kwargs
):
    payload = assert_safe(client.post(f"/api/v1/mcp/{path}", headers=auth_headers, **kwargs))
    assert payload["status"] == "success"


@pytest.mark.parametrize("path,fields", [
    ("/api/v1/ai/skin-analyze", {}),
    ("/api/v1/mcp/imaging/analyze", {"image_type": "xray"}),
    ("/api/v1/mcp/imaging/skin-lesion", {}),
])
def test_image_medical_responses_have_server_marker(
    client, auth_headers, fake_medical_providers, path, fields
):
    assert_safe(client.post(
        path, headers=auth_headers, data=fields,
        files={"image": ("SYNTHETIC.png", b"synthetic", "image/png")},
    ))


def test_mcp_icd_empty_and_service_failure_have_marker(client, auth_headers, fake_medical_providers):
    empty = assert_safe(client.post(
        "/api/v1/mcp/icd10/suggest", headers=auth_headers, json={"symptoms": []}
    ))
    assert empty["success"] is False
    fake_medical_providers.execute_request.side_effect = RuntimeError("SYNTHETIC")
    failure = assert_safe(client.post(
        "/api/v1/mcp/icd10/suggest", headers=auth_headers, json={"symptoms": ["SYNTHETIC"]}
    ))
    assert failure["success"] is False


def test_mcp_batch_empty_and_mixed_results_have_envelope(client, auth_headers, fake_medical_providers):
    for expected in ([{"data": "SYNTHETIC-SUGGESTION"}], []):
        fake_medical_providers.batch_execute.return_value = expected
        result = assert_safe(client.post(
            "/api/v1/mcp/batch", headers=auth_headers, json={"requests": []}
        ))
        assert result["data"] == expected


def test_openapi_requires_medical_metadata_for_legacy_and_mcp(client):
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    for schema_name in ("MedicalAIResultResponse", "MedicalAIListResponse"):
        assert "ai_safety_meta" in schemas[schema_name]["required"]
    medical = schemas["MedicalAISafetyMeta"]
    assert "requires_doctor_confirmation" in medical["required"]
    assert medical["properties"]["requires_doctor_confirmation"]["const"] is True
    for path in (
        "/api/v1/ai/icd-suggest", "/api/v1/ai/analyze-document", "/api/v1/mcp/batch",
    ):
        schema = spec["paths"][path]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith(("MedicalAIListResponse", "MedicalAIResultResponse"))


@pytest.mark.parametrize("provider_http_error", [False, True])
@pytest.mark.parametrize("path,method,kwargs", [
    ("complaint-to-plan", "analyze_complaint", {"json": {"complaint": "SYNTHETIC", "use_mcp": False}}),
    ("icd-suggest", "suggest_icd10", {"json": {"symptoms": ["SYNTHETIC"]}}),
    ("lab-interpret", "interpret_lab_results", {"json": {"results": [{"name": "SYNTHETIC", "value": "1"}]}}),
    ("ecg-interpret", "interpret_ecg", {"json": {"parameters": {"synthetic": 1}}}),
    ("skin-analyze", "analyze_skin", {"files": {"image": ("SYNTHETIC.png", b"synthetic", "image/png")}}),
])
def test_legacy_provider_exceptions_never_log_or_return_clinical_text(
    client, auth_headers, fake_medical_providers, monkeypatch, caplog,
    path, method, kwargs, provider_http_error,
):
    canary = "SYNTHETIC-CLINICAL-CANARY"
    exc = HTTPException(status_code=422, detail=canary) if provider_http_error else RuntimeError(canary)
    monkeypatch.setattr(ai.ai_manager, method, AsyncMock(side_effect=exc))

    with caplog.at_level("ERROR", logger=ai.__name__):
        response = client.post(f"/api/v1/ai/{path}", headers=auth_headers, **kwargs)

    assert response.status_code == 500
    assert canary not in response.text
    assert canary not in caplog.text
    records = [record for record in caplog.records if record.name == ai.__name__]
    assert records and all(record.exc_info is None for record in records)
    assert any("RuntimeError" in record.getMessage() for record in records)


def test_legacy_complaint_mcp_exception_is_sanitized_before_fallback(
    client, auth_headers, fake_medical_providers, caplog
):
    canary = "SYNTHETIC-CLINICAL-CANARY"
    fake_medical_providers.execute_request.side_effect = RuntimeError(canary)

    with caplog.at_level("ERROR", logger=ai.__name__):
        response = client.post(
            "/api/v1/ai/complaint-to-plan", headers=auth_headers,
            json={"complaint": "SYNTHETIC", "use_mcp": True},
        )

    assert_safe(response)
    assert canary not in response.text
    assert canary not in caplog.text
    records = [record for record in caplog.records if record.name == ai.__name__]
    assert records and all(record.exc_info is None for record in records)
    assert any("RuntimeError" in record.getMessage() for record in records)


def test_legacy_endpoint_owned_permission_and_upload_errors_remain_intact(
    client, auth_headers, fake_medical_providers, monkeypatch
):
    from app.services.authorization.staff import staff_authorization_service

    monkeypatch.setattr(staff_authorization_service, "can_access_ai", lambda _user: False)
    denied = client.post(
        "/api/v1/ai/complaint-to-plan", headers=auth_headers,
        json={"complaint": "SYNTHETIC", "use_mcp": False},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Недостаточно прав"

    monkeypatch.setattr(staff_authorization_service, "can_access_ai", lambda _user: True)
    invalid_image = client.post(
        "/api/v1/ai/skin-analyze", headers=auth_headers,
        files={"image": ("synthetic.txt", b"synthetic", "text/plain")},
    )
    assert invalid_image.status_code == 400
    assert invalid_image.json()["detail"] == "Файл должен быть изображением"


@pytest.mark.parametrize("batch", [False, True])
def test_mcp_transport_error_never_exposes_exception_text_over_http_or_logs(
    client, auth_headers, monkeypatch, caplog, batch
):
    from app.services.mcp.mcp_manager import MCPManager

    marker = "SYNTHETIC-CLINICAL-CANARY"
    manager = MCPManager()
    manager.config["enabled"] = True
    manager.client = SimpleNamespace(_call_server=AsyncMock(side_effect=RuntimeError(marker)))

    async def get_manager():
        return manager

    monkeypatch.setattr(mcp, "get_mcp_manager", get_manager)
    if batch:
        path = "/api/v1/mcp/batch"
        body = {"requests": [{"server": "lab", "method": "tool/interpret_lab_results", "params": {}}]}
    else:
        path = "/api/v1/mcp/lab/interpret"
        body = {"results": [{"name": "SYNTHETIC", "value": "1"}]}
    with caplog.at_level("ERROR", logger="app.services.mcp.mcp_manager"):
        response = client.post(path, headers=auth_headers, json=body)

    payload = assert_safe(response)
    result = payload["data"][0] if batch else payload
    assert result["status"] == "error"
    assert result["layer"] == "mcp_manager"
    assert marker not in response.text
    assert marker not in caplog.text


def test_legacy_complaint_falls_back_on_actual_mcp_transport_failure(
    client, auth_headers, fake_medical_providers, monkeypatch, caplog
):
    from app.services.mcp.mcp_manager import MCPManager

    marker = "SYNTHETIC-CLINICAL-CANARY"
    manager = MCPManager()
    manager.config["enabled"] = True
    manager.client = SimpleNamespace(_call_server=AsyncMock(side_effect=RuntimeError(marker)))

    async def get_manager():
        return manager

    monkeypatch.setattr(ai, "get_mcp_manager", get_manager)
    with caplog.at_level("ERROR"):
        response = client.post(
            "/api/v1/ai/complaint-to-plan", headers=auth_headers,
            json={"complaint": "SYNTHETIC", "use_mcp": True},
        )

    assert_safe(response)
    ai.ai_manager.analyze_complaint.assert_awaited_once()
    assert marker not in response.text
    assert marker not in caplog.text


@pytest.mark.parametrize("nested", [False, True])
def test_mcp_wrapped_server_error_never_exposes_clinical_text(
    client, auth_headers, monkeypatch, caplog, nested
):
    from app.services.mcp.base_server import MCPResponse
    from app.services.mcp.mcp_client import MedicalMCPClient
    from app.services.mcp.mcp_manager import MCPManager

    marker = "SYNTHETIC-CLINICAL-CANARY"
    wrapped = MCPResponse(result={"status": "error", "error": marker}) if nested else MCPResponse(
        error={"code": -32603, "message": marker}
    )
    server = SimpleNamespace(handle_request=AsyncMock(return_value=wrapped))
    transport = MedicalMCPClient.__new__(MedicalMCPClient)
    transport.servers = {"lab": server}
    transport._request_counter = 0
    manager = MCPManager()
    manager.config["enabled"] = True
    manager.client = transport

    async def get_manager():
        return manager

    monkeypatch.setattr(mcp, "get_mcp_manager", get_manager)
    with caplog.at_level("INFO"):
        response = client.post(
            "/api/v1/mcp/lab/interpret", headers=auth_headers,
            json={"results": [{"name": "SYNTHETIC", "value": "1"}]},
        )

    payload = assert_safe(response)
    assert payload["status"] == ("success" if nested else "error")
    error = payload["data"]["error"] if nested else payload["error"]
    assert error
    assert marker not in response.text
    assert marker not in caplog.text


def test_mcp_batch_does_not_log_caller_supplied_server_or_method(
    client, auth_headers, monkeypatch, caplog
):
    from app.services.mcp.mcp_client import MedicalMCPClient
    from app.services.mcp.mcp_manager import MCPManager

    marker = "SYNTHETIC-CLINICAL-CANARY"
    transport = MedicalMCPClient.__new__(MedicalMCPClient)
    transport.servers = {}
    transport._request_counter = 0
    manager = MCPManager()
    manager.config["enabled"] = True
    manager.client = transport

    async def get_manager():
        return manager

    monkeypatch.setattr(mcp, "get_mcp_manager", get_manager)
    with caplog.at_level("DEBUG"):
        response = client.post(
            "/api/v1/mcp/batch", headers=auth_headers,
            json={"requests": [{"server": marker, "method": marker, "params": {}}]},
        )

    assert_safe(response)
    assert marker not in caplog.text
