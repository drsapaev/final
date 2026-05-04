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
