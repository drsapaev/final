from __future__ import annotations

from datetime import datetime
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


class _FakeDoctorSectionTemplatesService:
    def __init__(self) -> None:
        self.get_calls: list[tuple[int, str, str | None, int]] = []
        self.update_calls: list[tuple[int, str, str, str]] = []

    async def get_templates(
        self,
        doctor_id: int,
        section_type: str,
        icd10_code: str | None,
        limit: int,
    ) -> dict[str, object]:
        self.get_calls.append((doctor_id, section_type, icd10_code, limit))
        return {
            "section_type": section_type,
            "icd10_code": icd10_code,
            "templates": [
                {
                    "id": "template-1",
                    "section_type": section_type,
                    "icd10_code": icd10_code,
                    "template_text": "Take medication after meals",
                    "usage_count": 4,
                    "is_pinned": True,
                    "last_used_at": datetime(2026, 3, 10, 10, 30, 0),
                    "created_at": datetime(2026, 3, 1, 9, 0, 0),
                }
            ],
            "total": 1,
        }

    async def update_template(
        self,
        doctor_id: int,
        template_id: str,
        new_text: str,
        mode: str,
    ) -> tuple[SimpleNamespace, str]:
        self.update_calls.append((doctor_id, template_id, new_text, mode))
        return (
            SimpleNamespace(
                id="template-1-copy",
                section_type="treatment",
                icd10_code="I10",
                template_text=new_text,
                usage_count=5,
                is_pinned=False,
                last_used_at=datetime(2026, 3, 11, 8, 45, 0),
                created_at=datetime(2026, 3, 11, 8, 45, 0),
            ),
            "saved as new",
        )


def test_section_templates_rejects_invalid_section_type(
    client,
    test_doctor_user,
):
    response = client.get(
        "/api/v1/section-templates/not-a-section",
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 400
    assert "Invalid section_type" in response.json()["detail"]


def test_section_templates_list_endpoint_preserves_doctor_query_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import section_templates as section_templates_endpoints

    fake_service = _FakeDoctorSectionTemplatesService()
    monkeypatch.setattr(
        section_templates_endpoints,
        "DoctorSectionTemplatesService",
        lambda _db: fake_service,
    )

    response = client.get(
        "/api/v1/section-templates/treatment",
        params={"icd10_code": "I10", "limit": 5},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["section_type"] == "treatment"
    assert payload["icd10_code"] == "I10"
    assert payload["total"] == 1
    assert payload["templates"][0]["id"] == "template-1"
    assert payload["templates"][0]["is_pinned"] is True
    assert fake_service.get_calls == [
        (test_doctor_user.id, "treatment", "I10", 5)
    ]


def test_section_templates_update_endpoint_preserves_write_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import section_templates as section_templates_endpoints

    fake_service = _FakeDoctorSectionTemplatesService()
    monkeypatch.setattr(
        section_templates_endpoints,
        "DoctorSectionTemplatesService",
        lambda _db: fake_service,
    )

    response = client.put(
        "/api/v1/section-templates/treatment/template-1",
        json={"new_text": "Updated treatment template", "mode": "save_as_new"},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "template-1-copy"
    assert payload["section_type"] == "treatment"
    assert payload["icd10_code"] == "I10"
    assert payload["template_text"] == "Updated treatment template"
    assert payload["usage_count"] == 5
    assert fake_service.update_calls == [
        (
            test_doctor_user.id,
            "template-1",
            "Updated treatment template",
            "save_as_new",
        )
    ]
