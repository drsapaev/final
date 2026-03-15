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


class _FakeEMRExportService:
    def __init__(self) -> None:
        self.csv_calls: list[tuple[dict[str, object], list[str] | None]] = []
        self.validate_calls: list[tuple[dict[str, object], str]] = []

    async def get_export_formats(self) -> list[str]:
        return ["json", "xml", "csv", "zip"]

    async def export_emr_to_csv(
        self,
        emr_data: dict[str, object],
        fields: list[str] | None = None,
    ) -> str:
        self.csv_calls.append((emr_data, fields))
        return "patient_id,diagnosis\n1,I20.9\n"

    async def validate_import_data(
        self,
        data: dict[str, object],
        format_type: str,
    ) -> dict[str, object]:
        self.validate_calls.append((data, format_type))
        return {"valid": True, "errors": [], "warnings": []}


def test_emr_export_formats_endpoint_preserves_authenticated_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_export as emr_export_endpoints

    fake_service = _FakeEMRExportService()
    monkeypatch.setattr(
        emr_export_endpoints,
        "EMRExportService",
        lambda: fake_service,
    )

    response = client.get(
        "/api/v1/emr/export/formats",
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["formats"] == ["json", "xml", "csv", "zip"]
    assert payload["message"] == "Список форматов экспорта получен"


def test_emr_export_csv_endpoint_preserves_download_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_export as emr_export_endpoints

    fake_service = _FakeEMRExportService()
    monkeypatch.setattr(
        emr_export_endpoints,
        "EMRExportService",
        lambda: fake_service,
    )

    response = client.post(
        "/api/v1/emr/export/export/csv",
        params=[("fields", "patient_id"), ("fields", "diagnosis")],
        json={"patient_id": 1, "diagnosis": "I20.9"},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    assert response.text == "patient_id,diagnosis\n1,I20.9\n"
    assert response.headers["content-disposition"] == (
        "attachment; filename=emr_export.csv"
    )
    assert response.headers["content-type"].startswith("text/csv")
    assert fake_service.csv_calls == [
        ({"patient_id": 1, "diagnosis": "I20.9"}, ["patient_id", "diagnosis"])
    ]


def test_emr_export_validate_endpoint_preserves_query_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_export as emr_export_endpoints

    fake_service = _FakeEMRExportService()
    monkeypatch.setattr(
        emr_export_endpoints,
        "EMRExportService",
        lambda: fake_service,
    )

    response = client.post(
        "/api/v1/emr/export/validate",
        params={"format_type": "xml"},
        json={"patient_id": 1, "diagnosis": "I20.9"},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["validation"]["valid"] is True
    assert payload["validation"]["errors"] == []
    assert fake_service.validate_calls == [
        ({"patient_id": 1, "diagnosis": "I20.9"}, "xml")
    ]
