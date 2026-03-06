from __future__ import annotations

from datetime import date

from app.services.visits_api_service import VisitsApiService


def test_list_visits_endpoint_delegates_to_service(client, monkeypatch) -> None:
    captured = {}

    def fake_list_visits(
        self,
        *,
        patient_id,
        doctor_id,
        status_q,
        planned,
        limit,
        offset,
    ):
        captured.update(
            {
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "status_q": status_q,
                "planned": planned,
                "limit": limit,
                "offset": offset,
            }
        )
        return [
            {
                "id": 17,
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "status": status_q or "open",
                "created_at": None,
                "started_at": None,
                "finished_at": None,
                "notes": "router wiring",
                "planned_date": planned,
                "source": "desk",
            }
        ]

    monkeypatch.setattr(VisitsApiService, "list_visits", fake_list_visits)

    response = client.get(
        "/api/v1/visits/visits",
        params={
            "patient_id": 4,
            "doctor_id": 9,
            "status_q": "open",
            "planned_date": "2026-03-06",
            "limit": 5,
            "offset": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == 17
    assert payload[0]["notes"] == "router wiring"
    assert captured == {
        "patient_id": 4,
        "doctor_id": 9,
        "status_q": "open",
        "planned": date(2026, 3, 6),
        "limit": 5,
        "offset": 2,
    }


def test_get_visit_endpoint_delegates_to_service(client, monkeypatch) -> None:
    captured = {}

    def fake_get_visit(self, *, visit_id: int):
        captured["visit_id"] = visit_id
        return {
            "visit": {
                "id": visit_id,
                "patient_id": 5,
                "doctor_id": 8,
                "status": "open",
                "created_at": None,
                "started_at": None,
                "finished_at": None,
                "notes": "visit card",
                "planned_date": None,
                "source": "desk",
            },
            "services": [
                {
                    "code": "CONSULT",
                    "name": "Consultation",
                    "price": 125000.0,
                    "qty": 1,
                }
            ],
        }

    monkeypatch.setattr(VisitsApiService, "get_visit", fake_get_visit)

    response = client.get("/api/v1/visits/visits/42")

    assert response.status_code == 200
    payload = response.json()
    assert payload["visit"]["id"] == 42
    assert payload["visit"]["notes"] == "visit card"
    assert payload["services"][0]["name"] == "Consultation"
    assert captured["visit_id"] == 42


def test_create_visit_endpoint_delegates_to_service(
    client,
    monkeypatch,
    auth_headers,
) -> None:
    captured = {}

    def fake_create_visit(self, *, request, payload, current_user):
        captured.update(
            {
                "payload": payload,
                "current_user_role": current_user.role,
                "has_request": request is not None,
            }
        )
        return {
            "id": 81,
            "patient_id": payload.patient_id,
            "doctor_id": payload.doctor_id,
            "status": "open",
            "created_at": None,
            "started_at": None,
            "finished_at": None,
            "notes": payload.notes,
            "planned_date": payload.planned_date,
            "source": payload.source or "desk",
        }

    monkeypatch.setattr(VisitsApiService, "create_visit", fake_create_visit)

    response = client.post(
        "/api/v1/visits/visits",
        json={
            "patient_id": 2,
            "doctor_id": 3,
            "notes": "created via service",
            "planned_date": "2026-03-07",
            "source": "desk",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == 81
    assert payload["notes"] == "created via service"
    assert payload["planned_date"] == "2026-03-07"
    assert payload["source"] == "desk"
    assert captured["payload"].patient_id == 2
    assert captured["payload"].doctor_id == 3
    assert captured["payload"].planned_date == date(2026, 3, 7)
    assert captured["current_user_role"] == "Admin"
    assert captured["has_request"] is True


def test_add_service_endpoint_delegates_to_service(
    client,
    monkeypatch,
    auth_headers,
    test_visit,
) -> None:
    captured = {}

    def fake_add_service(self, *, visit_id: int, item):
        captured["visit_id"] = visit_id
        captured["item"] = item
        return {
            "ok": True,
            "service": {
                "id": 501,
                "visit_id": visit_id,
                "code": item.code,
                "name": item.name,
                "price": item.price,
                "qty": item.qty,
            },
        }

    monkeypatch.setattr(VisitsApiService, "add_service", fake_add_service)

    response = client.post(
        f"/api/v1/visits/visits/{test_visit.id}/services",
        json={
            "code": "CONSULT",
            "name": "Consultation",
            "price": 125000,
            "qty": 1,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"]["visit_id"] == test_visit.id
    assert payload["service"]["name"] == "Consultation"
    assert captured["visit_id"] == test_visit.id
    assert captured["item"].code == "CONSULT"
    assert captured["item"].price == 125000
