"""EMR medical suggestion routes enforce the nested clinician-review contract.

Services are synthetic mocks: no external AI provider or real patient is used.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import deps
from app.api.v1.endpoints import emr_ai, emr_ai_enhanced
from app.db.session import get_db
from app.schemas.medical_ai_safety import MedicalAIResultResponse
from app.services import ai_feature_gating


@pytest.fixture
def emr_app(monkeypatch):
    app = FastAPI()
    app.include_router(emr_ai.router, prefix="/api/v1/emr/ai")
    app.include_router(emr_ai_enhanced.router, prefix="/api/v1/emr/ai-enhanced")
    user = SimpleNamespace(id=1, role="Admin", is_superuser=True, is_active=True)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[deps.get_db] = lambda: None
    app.dependency_overrides[deps.get_current_user] = lambda: user
    app.dependency_overrides[emr_ai.EMR_AI_ACCESS] = lambda: user
    monkeypatch.setattr(ai_feature_gating, "is_ai_feature_enabled", lambda *_: True)
    return app


@pytest.fixture
def fake_services(monkeypatch):
    basic = SimpleNamespace(
        get_diagnosis_suggestions=AsyncMock(return_value=["SYNTHETIC suggestion"]),
        get_treatment_suggestions=AsyncMock(return_value=["SYNTHETIC suggestion"]),
        get_icd10_suggestions=AsyncMock(return_value=["SYNTHETIC suggestion"]),
        auto_fill_emr_fields=AsyncMock(return_value={"field": "SYNTHETIC"}),
        validate_emr_data=AsyncMock(return_value={"valid": True, "ai_safety_meta": {"requires_doctor_confirmation": False}}),
        get_ai_suggestions=AsyncMock(return_value=["SYNTHETIC suggestion"]),
    )
    monkeypatch.setattr(emr_ai, "get_emr_ai_service", AsyncMock(return_value=basic))
    enhanced = SimpleNamespace(
        auto_fill_emr_fields=AsyncMock(return_value={"field": "SYNTHETIC"}),
        validate_emr_data=AsyncMock(return_value={"valid": True, "ai_safety_meta": {"requires_doctor_confirmation": False}}),
        generate_icd10_suggestions=AsyncMock(return_value=["SYNTHETIC suggestion"]),
        _analyze_patient_data=AsyncMock(return_value={"risk_factors": [], "age_group": "adult"}),
        _generate_improvement_suggestions=AsyncMock(return_value=["SYNTHETIC suggestion"]),
    )
    monkeypatch.setattr(emr_ai_enhanced, "emr_ai_enhanced", enhanced)
    record = SimpleNamespace(complaints="", anamnesis="", examination="", diagnosis="", icd10="", recommendations="", specialty="general")
    monkeypatch.setattr(emr_ai_enhanced.emr, "get", lambda *_args, **_kwargs: record, raising=False)
    return basic, enhanced


def assert_safety(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ai_safety_meta"]["requires_doctor_confirmation"] is True
    assert payload["requires_doctor_confirmation"] is True
    assert payload["decision_boundary"] == "suggestion_only"
    return payload


@pytest.mark.parametrize("url,body", [
    ("/suggestions/diagnosis", ["SYNTHETIC symptom"]),
    ("/suggestions/treatment?diagnosis=SYNTHETIC", None),
    ("/suggestions/icd10?diagnosis_text=SYNTHETIC", None),
    ("/auto-fill", {"template_structure": {}, "patient_data": {}}),
    ("/validate", {"emr_data": {}, "template_structure": {}}),
    ("/suggestions/ai", {}),
])
def test_basic_medical_routes_serialize_server_safety(emr_app, fake_services, url, body):
    with TestClient(emr_app) as client:
        response = client.post("/api/v1/emr/ai" + url, json=body)
    assert_safety(response)


@pytest.mark.parametrize("url,body", [
    ("/auto-fill", {"template_structure": {}, "patient_data": {}}),
    ("/validate", {}),
    ("/icd10-suggestions?diagnosis_text=SYNTHETIC", None),
    ("/analyze-patient", {}),
    ("/emr/1/ai-enhance?enhancement_type=validation", None),
])
def test_enhanced_medical_routes_serialize_server_safety(emr_app, fake_services, url, body):
    with TestClient(emr_app) as client:
        response = client.post("/api/v1/emr/ai-enhanced" + url, json=body)
    assert_safety(response)


def test_emr_suggest_response_model_keeps_marker_and_existing_fields(emr_app, monkeypatch):
    suggestion = emr_ai.AISuggestionV2(
        id="SYNTHETIC", targetField="diagnosis", content="SYNTHETIC suggestion", confidence=0.5
    )
    monkeypatch.setattr(emr_ai, "generate_v2_suggestions", lambda *_args: [suggestion])
    with TestClient(emr_app) as client:
        response = client.post("/api/v1/emr/ai/suggest", json={"emr_snapshot": {}, "specialty": "general"})
    result = assert_safety(response)
    assert result["suggestions"][0]["content"] == "SYNTHETIC suggestion"
    assert result["suggestions"][0]["requiresDoctorConfirmation"] is True
    assert result["model"] == "mock"
    assert result["specialty"] == "general"


def test_bad_provider_does_not_expose_raw_failure(emr_app, fake_services):
    fake_services[0].get_diagnosis_suggestions.side_effect = ValueError("SYNTHETIC private provider response")
    with TestClient(emr_app) as client:
        response = client.post("/api/v1/emr/ai/suggestions/diagnosis", json=["SYNTHETIC"])
    assert response.status_code == 500
    assert "private provider response" not in response.text


@pytest.mark.parametrize("bad", [False, 1, "true", None, [], {}])
def test_emr_response_models_reject_invalid_safety_markers(bad):
    meta = bad if isinstance(bad, (dict, list)) or bad is None else {"requires_doctor_confirmation": bad}
    with pytest.raises(ValidationError):
        MedicalAIResultResponse.model_validate({"ai_safety_meta": meta})
    with pytest.raises(ValidationError):
        emr_ai.SuggestResponseV2.model_validate({"suggestions": [], "specialty": "general", "ai_safety_meta": meta})


@pytest.mark.parametrize("bad", [False, 1, "true", None])
def test_emr_suggestion_rejects_conflicting_item_confirmation(bad):
    with pytest.raises(ValidationError):
        emr_ai.AISuggestionV2.model_validate({
            "id": "SYNTHETIC", "targetField": "diagnosis",
            "content": "SYNTHETIC", "confidence": 0.5,
            "requiresDoctorConfirmation": bad,
        })


def test_bad_constructed_suggestion_is_not_served(emr_app, monkeypatch):
    invalid = emr_ai.AISuggestionV2.model_construct(
        id="SYNTHETIC", targetField="diagnosis", content="SYNTHETIC_PRIVATE",
        confidence=0.5, requiresDoctorConfirmation=False,
    )
    monkeypatch.setattr(emr_ai, "generate_v2_suggestions", lambda *_args: [invalid])
    with TestClient(emr_app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/emr/ai/suggest", json={"emr_snapshot": {}})
    assert response.status_code == 500
    assert "SYNTHETIC_PRIVATE" not in response.text


def test_openapi_requires_nested_marker_for_emr_response_models(emr_app):
    schemas = emr_app.openapi()["components"]["schemas"]
    for name in ("MedicalAIResultResponse", "SuggestResponseV2"):
        assert "ai_safety_meta" in schemas[name]["required"]
        assert schemas[name]["properties"]["ai_safety_meta"]["$ref"] == "#/components/schemas/MedicalAISafetyMeta"
    safety = schemas["MedicalAISafetyMeta"]
    assert "requires_doctor_confirmation" in safety["required"]
    assert safety["properties"]["requires_doctor_confirmation"]["const"] is True
    item = schemas["AISuggestionV2"]["properties"]["requiresDoctorConfirmation"]
    assert item["const"] is True
