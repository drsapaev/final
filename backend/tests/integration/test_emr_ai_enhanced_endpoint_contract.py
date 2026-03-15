from __future__ import annotations

from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.integration


def _doctor_auth_headers(client, test_doctor_user) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _FakeEMRAIEnhancedService:
    def __init__(self) -> None:
        self.template_calls: list[
            tuple[str, dict[str, object], dict[str, object] | None]
        ] = []
        self.suggestion_calls: list[tuple[dict[str, object], str, str]] = []
        self.specialty_templates = {
            "general": {"complaints": {"type": "textarea"}},
            "cardiology": {"diagnosis": {"type": "textarea"}},
        }

    async def generate_smart_template(
        self,
        *,
        specialty: str,
        patient_data: dict[str, object],
        doctor_preferences: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.template_calls.append((specialty, patient_data, doctor_preferences))
        return {
            "specialty": specialty,
            "sections": ["complaints", "diagnosis"],
            "doctor_preferences": doctor_preferences or {},
        }

    async def get_smart_suggestions(
        self,
        *,
        current_data: dict[str, object],
        field_name: str,
        specialty: str = "general",
    ) -> list[dict[str, object]]:
        self.suggestion_calls.append((current_data, field_name, specialty))
        return [
            {
                "field": field_name,
                "text": f"smart-{field_name}",
                "specialty": specialty,
            }
        ]


def test_emr_ai_enhanced_generate_template_preserves_embedded_body_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_ai_enhanced as enhanced_endpoints

    fake_service = _FakeEMRAIEnhancedService()
    monkeypatch.setattr(enhanced_endpoints, "emr_ai_enhanced", fake_service)

    response = client.post(
        "/api/v1/emr/ai-enhanced/generate-smart-template",
        params={"specialty": "cardiology"},
        json={
            "patient_data": {"age": 67, "hypertension": True},
            "doctor_preferences": {"style": "concise"},
        },
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["specialty"] == "cardiology"
    assert payload["template"] == {
        "specialty": "cardiology",
        "sections": ["complaints", "diagnosis"],
        "doctor_preferences": {"style": "concise"},
    }
    assert fake_service.template_calls == [
        (
            "cardiology",
            {"age": 67, "hypertension": True},
            {"style": "concise"},
        )
    ]


def test_emr_ai_enhanced_smart_suggestions_preserves_raw_dict_body_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_ai_enhanced as enhanced_endpoints

    fake_service = _FakeEMRAIEnhancedService()
    monkeypatch.setattr(enhanced_endpoints, "emr_ai_enhanced", fake_service)

    response = client.post(
        "/api/v1/emr/ai-enhanced/smart-suggestions",
        params={"field_name": "diagnosis", "specialty": "cardiology"},
        json={"complaints": "Боль в груди", "blood_pressure": "150/90"},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["field_name"] == "diagnosis"
    assert payload["count"] == 1
    assert payload["suggestions"] == [
        {
            "field": "diagnosis",
            "text": "smart-diagnosis",
            "specialty": "cardiology",
        }
    ]
    assert fake_service.suggestion_calls == [
        (
            {"complaints": "Боль в груди", "blood_pressure": "150/90"},
            "diagnosis",
            "cardiology",
        )
    ]


def test_emr_ai_enhanced_emr_enhance_preserves_path_query_and_crud_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_ai_enhanced as enhanced_endpoints

    fake_service = _FakeEMRAIEnhancedService()
    monkeypatch.setattr(enhanced_endpoints, "emr_ai_enhanced", fake_service)
    monkeypatch.setattr(
        enhanced_endpoints.emr_crud,
        "get",
        lambda db, id: SimpleNamespace(
            complaints="Боль в груди",
            anamnesis="2 дня",
            examination="АД 150/90",
            diagnosis="",
            icd10="",
            recommendations="",
            specialty="cardiology",
        ),
    )

    response = client.post(
        "/api/v1/emr/ai-enhanced/emr/42/ai-enhance",
        params={"enhancement_type": "suggestions"},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["emr_id"] == 42
    assert payload["enhancement_type"] == "suggestions"
    assert set(payload["result"]) == {"complaints", "diagnosis", "treatment"}
    assert fake_service.suggestion_calls == [
        (
            {
                "complaints": "Боль в груди",
                "anamnesis": "2 дня",
                "examination": "АД 150/90",
                "diagnosis": "",
                "icd10": "",
                "recommendations": "",
            },
            "complaints",
            "cardiology",
        ),
        (
            {
                "complaints": "Боль в груди",
                "anamnesis": "2 дня",
                "examination": "АД 150/90",
                "diagnosis": "",
                "icd10": "",
                "recommendations": "",
            },
            "diagnosis",
            "cardiology",
        ),
        (
            {
                "complaints": "Боль в груди",
                "anamnesis": "2 дня",
                "examination": "АД 150/90",
                "diagnosis": "",
                "icd10": "",
                "recommendations": "",
            },
            "treatment",
            "cardiology",
        ),
    ]
