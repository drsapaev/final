from __future__ import annotations

from types import SimpleNamespace

from app.services.services_api_service import ServicesApiService


def test_service_categories_endpoint_delegates_to_service(client, monkeypatch) -> None:
    captured = {}

    def fake_list_service_categories(self, *, active):
        captured["active"] = active
        return [
            {
                "id": 1,
                "code": "CARDIO",
                "name_ru": "Кардиология",
                "name_uz": None,
                "name_en": None,
                "specialty": "cardiology",
                "active": True,
            }
        ]

    monkeypatch.setattr(
        ServicesApiService,
        "list_service_categories",
        fake_list_service_categories,
    )

    response = client.get("/api/v1/services/categories", params={"active": "true"})

    assert response.status_code == 200
    assert response.json()[0]["code"] == "CARDIO"
    assert captured["active"] is True


def test_get_service_endpoint_delegates_to_service(client, monkeypatch) -> None:
    captured = {}

    def fake_get_service(self, *, service_id: int):
        captured["service_id"] = service_id
        return SimpleNamespace(
            id=service_id,
            code="K01",
            name="Consultation",
            department="cardiology",
            unit="service",
            price=125000,
            currency="UZS",
            active=True,
            category_id=5,
            duration_minutes=30,
            doctor_id=None,
            category_code="K",
            service_code="K01",
            requires_doctor=False,
            queue_tag="cardio",
            is_consultation=True,
            allow_doctor_price_override=False,
            department_key="cardio",
        )

    monkeypatch.setattr(ServicesApiService, "get_service", fake_get_service)

    response = client.get("/api/v1/services/42")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 42
    assert payload["code"] == "K01"
    assert payload["name"] == "Consultation"
    assert captured["service_id"] == 42

