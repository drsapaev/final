from __future__ import annotations

from datetime import datetime

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


class _FakeEMRLabIntegrationService:
    def __init__(self) -> None:
        self.lab_results_calls: list[
            tuple[int, datetime | None, datetime | None, list[str] | None]
        ] = []
        self.integrate_calls: list[tuple[int, list[int]]] = []
        self.notify_calls: list[tuple[int, int, int]] = []

    async def get_patient_lab_results(
        self,
        *,
        db,
        patient_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        test_types: list[str] | None = None,
    ) -> list[dict[str, object]]:
        self.lab_results_calls.append((patient_id, date_from, date_to, test_types))
        return [
            {"id": 1, "is_abnormal": True},
            {"id": 2, "is_abnormal": False},
        ]

    async def integrate_lab_results_with_emr(
        self,
        *,
        db,
        emr_id: int,
        lab_result_ids: list[int],
    ) -> dict[str, object]:
        self.integrate_calls.append((emr_id, lab_result_ids))
        return {"emr_id": emr_id, "integrated_count": len(lab_result_ids)}

    async def notify_doctor_about_lab_results(
        self,
        *,
        db,
        patient_id: int,
        doctor_id: int,
        result_id: int,
    ) -> dict[str, object]:
        self.notify_calls.append((patient_id, doctor_id, result_id))
        return {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "result_id": result_id,
            "status": "queued",
        }


def test_emr_lab_results_endpoint_preserves_query_parsing_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_lab_integration as lab_endpoints

    fake_service = _FakeEMRLabIntegrationService()
    monkeypatch.setattr(lab_endpoints, "emr_lab_integration", fake_service)

    response = client.get(
        "/api/v1/emr/lab/patients/77/lab-results",
        params={
            "date_from": "2026-03-01T00:00:00",
            "date_to": "2026-03-14T00:00:00",
            "test_types": "glucose, cholesterol",
        },
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["patient_id"] == 77
    assert payload["total_count"] == 2
    assert payload["abnormal_count"] == 1
    assert fake_service.lab_results_calls == [
        (
            77,
            datetime.fromisoformat("2026-03-01T00:00:00"),
            datetime.fromisoformat("2026-03-14T00:00:00"),
            ["glucose", "cholesterol"],
        )
    ]


def test_emr_lab_integration_endpoint_preserves_list_body_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_lab_integration as lab_endpoints

    fake_service = _FakeEMRLabIntegrationService()
    monkeypatch.setattr(lab_endpoints, "emr_lab_integration", fake_service)

    response = client.post(
        "/api/v1/emr/lab/emr/42/integrate-lab-results",
        json=[11, 12, 13],
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Лабораторные результаты успешно интегрированы с EMR"
    assert payload["result"] == {"emr_id": 42, "integrated_count": 3}
    assert fake_service.integrate_calls == [(42, [11, 12, 13])]


def test_emr_lab_notify_endpoint_preserves_parameter_contract(
    client,
    auth_headers,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_lab_integration as lab_endpoints

    fake_service = _FakeEMRLabIntegrationService()
    monkeypatch.setattr(lab_endpoints, "emr_lab_integration", fake_service)

    response = client.post(
        "/api/v1/emr/lab/lab-results/9/notify-doctor",
        params={"patient_id": 77, "doctor_id": 15},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Уведомление врача отправлено"
    assert payload["notification"]["status"] == "queued"
    assert fake_service.notify_calls == [(77, 15, 9)]
