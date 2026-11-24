"""Published medical AI route schemas require the server safety marker."""

import pytest


MEDICAL_ROUTE_MODELS = {
    **{f"/api/v1/ai/v2/{path}": "AIResponse" for path in (
        "analyze-complaints", "suggest-icd10", "differential-diagnosis", "interpret-lab",
        "analyze-skin", "analyze-skin-file", "analyze-ecg", "symptom-check",
        "analyze-document", "drug-interaction",
    )},
    **{f"/api/v1/ai/{path}": "MedicalAIResultResponse" for path in (
        "analyze-complaints", "suggest-icd10", "analyze-document", "interpret-lab-results",
        "symptom-checker", "quick/diagnosis-help", "complaint-to-plan", "lab-interpret",
        "skin-analyze", "ecg-interpret",
    )},
    **{f"/api/v1/mcp/{path}": "MedicalAIResultResponse" for path in (
        "complaint/analyze", "complaint/validate", "icd10/suggest", "icd10/validate",
        "lab/interpret", "lab/check-critical", "imaging/analyze", "imaging/skin-lesion",
    )},
    **{f"/api/v1/emr/ai/{path}": "MedicalAIResultResponse" for path in (
        "suggestions/diagnosis", "suggestions/treatment", "suggestions/icd10", "auto-fill",
        "validate", "suggestions/ai",
    )},
    **{f"/api/v1/emr/ai-enhanced/{path}": "MedicalAIResultResponse" for path in (
        "auto-fill", "validate", "icd10-suggestions", "analyze-patient", "emr/{emr_id}/ai-enhance",
    )},
    "/api/v1/emr/ai/suggest": "SuggestResponseV2",
    "/api/v1/ai/icd-suggest": "MedicalAIListResponse",
    "/api/v1/mcp/batch": "MedicalAIListResponse",
}


@pytest.mark.parametrize("path,model", MEDICAL_ROUTE_MODELS.items())
def test_published_medical_success_schema_requires_nested_safety(client, path, model):
    schema = client.get("/openapi.json").json()
    response = schema["paths"][path]["post"]["responses"]["200"]
    response_schema = response["content"]["application/json"]["schema"]
    assert response_schema["$ref"] == f"#/components/schemas/{model}"
    published_model = schema["components"]["schemas"][model]
    assert "ai_safety_meta" in published_model["required"]
    assert published_model["properties"]["ai_safety_meta"]["$ref"] == (
        "#/components/schemas/MedicalAISafetyMeta"
    )


def test_published_marker_is_required_boolean_true_and_collections_use_envelopes(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    marker = schemas["MedicalAISafetyMeta"]
    assert "requires_doctor_confirmation" in marker["required"]
    assert marker["properties"]["requires_doctor_confirmation"]["type"] == "boolean"
    assert marker["properties"]["requires_doctor_confirmation"]["const"] is True
    collection = schemas["MedicalAIListResponse"]
    assert set(collection["required"]) == {"data", "ai_safety_meta"}
    assert collection["properties"]["data"]["type"] == "array"


@pytest.mark.parametrize("path", ["generate-smart-template?specialty=general", "smart-suggestions?field_name=diagnosis"])
def test_unavailable_enhanced_stub_returns_no_medical_result(monkeypatch, path):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import deps
    from app.api.v1.endpoints import emr_ai_enhanced
    from app.db.session import get_db
    from app.services import ai_feature_gating

    app = FastAPI()
    app.include_router(emr_ai_enhanced.router, prefix="/api/v1/emr/ai-enhanced")
    user = SimpleNamespace(id=1, role="Admin", is_superuser=True, is_active=True)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[deps.get_db] = lambda: None
    app.dependency_overrides[deps.get_current_user] = lambda: user
    monkeypatch.setattr(ai_feature_gating, "is_ai_feature_enabled", lambda *_: True)
    with TestClient(app) as test_client:
        response = test_client.post(f"/api/v1/emr/ai-enhanced/{path}", json={})
    assert response.status_code == 503
    assert response.json() == {"detail": {"error": "ai_feature_unavailable"}}
