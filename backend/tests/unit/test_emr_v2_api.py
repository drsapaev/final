from __future__ import annotations

import pytest

from app.api.v1.endpoints import emr_v2


@pytest.mark.unit
def test_doctor_history_route_is_not_shadowed_by_visit_id(
    client,
    admin_user,
    auth_headers,
    monkeypatch,
):
    def fake_get_history_entries(self, **kwargs):
        return [
            {
                "content": "Chest pain",
                "diagnosis": "I20.0",
                "created_at": "2026-01-01T10:00:00",
            }
        ]

    monkeypatch.setattr(
        emr_v2.EMRDoctorHistoryService,
        "get_history_entries",
        fake_get_history_entries,
    )

    response = client.get(
        f"/api/v1/v2/emr/doctor-history?doctor_id={admin_user.id}&field_name=complaints&specialty=cardiology",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["field_name"] == "complaints"
    assert payload["entries"][0]["content"] == "Chest pain"
