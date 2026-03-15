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


def test_emr_versioning_timeline_endpoint_preserves_doctor_query_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_versioning_enhanced as versioning_endpoints

    calls: list[tuple[int, int]] = []

    async def fake_get_version_timeline(*, db, emr_id: int, limit: int):
        calls.append((emr_id, limit))
        return [
            {"version_id": 7, "version_number": 3},
            {"version_id": 6, "version_number": 2},
        ]

    monkeypatch.setattr(
        versioning_endpoints.emr_versioning_enhanced,
        "get_version_timeline",
        fake_get_version_timeline,
    )

    response = client.get(
        "/api/v1/emr/versions/42/versions/timeline",
        params={"limit": 2},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["emr_id"] == 42
    assert payload["total_versions"] == 2
    assert payload["timeline"][0]["version_id"] == 7
    assert calls == [(42, 2)]


def test_emr_versioning_create_endpoint_preserves_body_and_query_contract(
    client,
    test_doctor_user,
    monkeypatch,
):
    from app.api.v1.endpoints import emr_versioning_enhanced as versioning_endpoints
    from app.crud import emr_template as emr_template_crud

    previous_version = SimpleNamespace(version_data={"diagnosis": "stable"})
    crud_calls: list[tuple[int, int]] = []
    service_calls: list[tuple[int, dict[str, object], str, str | None, int, dict[str, object] | None]] = []

    def fake_get_by_emr(db, *, emr_id: int, limit: int):
        crud_calls.append((emr_id, limit))
        return [previous_version]

    async def fake_create_version_with_analysis(
        *,
        db,
        emr_id: int,
        version_data: dict[str, object],
        change_type: str,
        change_description: str | None,
        changed_by: int,
        previous_version: dict[str, object] | None,
    ):
        service_calls.append(
            (
                emr_id,
                version_data,
                change_type,
                change_description,
                changed_by,
                previous_version,
            )
        )
        return SimpleNamespace(
            id=55,
            version_number=4,
            created_at=datetime(2026, 3, 14, 9, 30, 0),
        )

    monkeypatch.setattr(emr_template_crud.emr_version, "get_by_emr", fake_get_by_emr)
    monkeypatch.setattr(
        versioning_endpoints.emr_versioning_enhanced,
        "create_version_with_analysis",
        fake_create_version_with_analysis,
    )

    response = client.post(
        "/api/v1/emr/versions/42/versions/create",
        params={
            "change_type": "manual_update",
            "change_description": "Added follow-up notes",
        },
        json={"diagnosis": "improved", "plan": "continue treatment"},
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Версия успешно создана"
    assert payload["version_id"] == 55
    assert payload["version_number"] == 4
    assert crud_calls == [(42, 1)]
    assert service_calls == [
        (
            42,
            {"diagnosis": "improved", "plan": "continue treatment"},
            "manual_update",
            "Added follow-up notes",
            test_doctor_user.id,
            {"diagnosis": "stable"},
        )
    ]


def test_emr_versioning_delete_endpoint_preserves_admin_only_contract(
    client,
    auth_headers,
    monkeypatch,
):
    from app.crud import emr_template as emr_template_crud

    remove_calls: list[int] = []

    fake_crud = SimpleNamespace(
        get=lambda db, id: SimpleNamespace(id=id, emr_id=42),
        remove=lambda db, id: remove_calls.append(id),
    )
    monkeypatch.setattr(emr_template_crud, "emr_version", fake_crud)

    response = client.delete(
        "/api/v1/emr/versions/42/versions/7",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Версия успешно удалена",
        "version_id": 7,
    }
    assert remove_calls == [7]


def test_emr_versioning_delete_endpoint_blocks_doctor_role(
    client,
    test_doctor_user,
):
    response = client.delete(
        "/api/v1/emr/versions/42/versions/7",
        headers=_doctor_auth_headers(client, test_doctor_user),
    )

    assert response.status_code == 403
