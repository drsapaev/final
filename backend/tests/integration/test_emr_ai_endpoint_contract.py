from __future__ import annotations

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


class _FakeEMRAIService:
    def __init__(self) -> None:
        self.diagnosis_calls: list[tuple[list[str], str]] = []
        self.auto_fill_calls: list[tuple[dict[str, object], dict[str, object], str]] = []

    async def get_diagnosis_suggestions(
        self,
        symptoms: list[str],
        specialty: str = "general",
    ) -> list[dict[str, object]]:
        self.diagnosis_calls.append((symptoms, specialty))
        return [
            {"diagnosis": "Цефалгия", "icd10": "G44.2", "confidence": 0.78},
            {"diagnosis": "Гипертензия", "icd10": "I10", "confidence": 0.72},
        ]

    async def auto_fill_emr_fields(
        self,
        template_structure: dict[str, object],
        patient_data: dict[str, object],
        specialty: str = "general",
    ) -> dict[str, object]:
        self.auto_fill_calls.append((template_structure, patient_data, specialty))
        return {
            "summary": {"complaints": patient_data.get("complaints", "")},
            "meta": {"specialty": specialty},
        }


def test_emr_ai_diagnosis_endpoint_preserves_body_and_query_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_ai as emr_ai_endpoints

    fake_service = _FakeEMRAIService()

    async def fake_get_emr_ai_service():
        return fake_service

    monkeypatch.setattr(
        emr_ai_endpoints,
        "get_emr_ai_service",
        fake_get_emr_ai_service,
    )

    response = client.post(
        "/api/v1/emr/ai/suggestions/diagnosis",
        params={"specialty": "cardio"},
        json=["головная боль", "давление 150/90"],
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["specialty"] == "cardio"
    assert payload["suggestions"][0]["icd10"] == "G44.2"
    assert fake_service.diagnosis_calls == [
        (["головная боль", "давление 150/90"], "cardio")
    ]


def test_emr_ai_auto_fill_endpoint_preserves_embedded_body_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_ai as emr_ai_endpoints

    fake_service = _FakeEMRAIService()

    async def fake_get_emr_ai_service():
        return fake_service

    monkeypatch.setattr(
        emr_ai_endpoints,
        "get_emr_ai_service",
        fake_get_emr_ai_service,
    )

    template_structure = {
        "sections": [
            {
                "section_name": "summary",
                "fields": [{"field_name": "complaints", "field_type": "textarea"}],
            }
        ]
    }
    patient_data = {"complaints": "Слабость и головокружение", "age": 52}

    response = client.post(
        "/api/v1/emr/ai/auto-fill",
        params={"specialty": "therapist"},
        json={
            "template_structure": template_structure,
            "patient_data": patient_data,
        },
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filled_data"] == {
        "summary": {"complaints": "Слабость и головокружение"},
        "meta": {"specialty": "therapist"},
    }
    assert payload["template_structure"] == template_structure
    assert payload["specialty"] == "therapist"
    assert fake_service.auto_fill_calls == [
        (template_structure, patient_data, "therapist")
    ]


def test_emr_ai_v2_suggest_endpoint_preserves_doctor_context_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_ai as emr_ai_endpoints

    captured_calls: list[tuple[dict[str, object], str, object]] = []

    def fake_generate_v2_suggestions(emr_data, specialty, doctor_context=None):
        captured_calls.append((emr_data, specialty, doctor_context))
        return [
            emr_ai_endpoints.AISuggestionV2(
                id="ctx-1234",
                targetField="diagnosis",
                content="Артериальная гипертензия",
                confidence=0.66,
                explanation="На основе вашей истории",
            )
        ]

    monkeypatch.setattr(
        emr_ai_endpoints,
        "generate_v2_suggestions",
        fake_generate_v2_suggestions,
    )

    response = client.post(
        "/api/v1/emr/ai/suggest",
        json={
            "emr_snapshot": {"complaints": "головная боль, шум в ушах"},
            "specialty": "cardio",
            "language": "ru",
            "doctor_context": {
                "doctor_id": 17,
                "specialty": "cardio",
                "field_name": "diagnosis",
                "unique_phrases": ["Артериальная гипертензия, II стадия"],
                "previous_entries": [
                    {
                        "content": "Контроль АД",
                        "diagnosis": "I10",
                        "created_at": "2026-03-14T09:30:00",
                    }
                ],
            },
        },
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "mock"
    assert payload["specialty"] == "cardio"
    assert payload["used_doctor_context"] is True
    assert payload["suggestions"] == [
        {
            "id": "ctx-1234",
            "targetField": "diagnosis",
            "content": "Артериальная гипертензия",
            "confidence": 0.66,
            "source": "AI",
            "explanation": "На основе вашей истории",
            "model": "mock",
        }
    ]
    assert len(captured_calls) == 1
    emr_data, specialty, doctor_context = captured_calls[0]
    assert emr_data == {"complaints": "головная боль, шум в ушах"}
    assert specialty == "cardio"
    assert doctor_context.doctor_id == 17
    assert doctor_context.unique_phrases == ["Артериальная гипертензия, II стадия"]
