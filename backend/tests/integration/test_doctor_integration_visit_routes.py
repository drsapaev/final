from app.api.v1.endpoints import doctor_integration


def test_doctor_visit_statistics_route_dispatches_before_visit_id(
    client,
    auth_headers,
    monkeypatch,
):
    def _fake_visit_statistics(*, db, doctor_id, date_from, date_to):
        return {
            "total": 3,
            "completed": 2,
            "doctor_id": doctor_id,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
        }

    monkeypatch.setattr(
        doctor_integration.crud_visit,
        "get_visit_statistics",
        _fake_visit_statistics,
    )

    response = client.get(
        "/api/v1/doctor/visits/statistics",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["statistics"]["total"] == 3
