from types import SimpleNamespace

from app.api.v1.endpoints import appointments


def test_appointments_stats_route_dispatches_before_appointment_id(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(
        appointments,
        "load_stats",
        lambda db, *, department, date_str: SimpleNamespace(
            is_open=True,
            start_number=10,
            last_ticket=12,
            waiting=2,
            serving=1,
            done=9,
        ),
    )

    response = client.get(
        "/api/v1/appointments/stats",
        params={"department": "cardiology", "date": "2026-06-01"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "department": "cardiology",
        "date_str": "2026-06-01",
        "is_open": True,
        "start_number": 10,
        "last_ticket": 12,
        "waiting": 2,
        "serving": 1,
        "done": 9,
    }


def test_appointments_qrcode_route_dispatches_before_appointment_id(
    client, auth_headers
):
    response = client.get(
        "/api/v1/appointments/qrcode",
        params={"department": "cardiology", "date": "2026-06-01"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "format": "text",
        "data": "cardiology::2026-06-01",
    }


def test_numeric_appointment_id_route_remains_available(client, auth_headers):
    response = client.get("/api/v1/appointments/999999", headers=auth_headers)

    assert response.status_code == 404
