from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import app.api.v1.endpoints.online_queue_new as online_queue_new_module
import pytest

from app.services.queue_service import QueueValidationError


@pytest.mark.unit
def test_online_queue_join_uses_queue_domain_service_boundary(client, monkeypatch):
    domain_service = Mock()
    domain_service.allocate_ticket.return_value = {
        "entry": SimpleNamespace(number=7),
        "duplicate": False,
        "specialist_name": "Test Specialist",
        "cabinet": "12A",
    }
    monkeypatch.setattr(
        online_queue_new_module,
        "_queue_domain_service",
        lambda db: domain_service,
    )

    response = client.post(
        "/api/v1/online-queue/join",
        json={
            "token": "boundary-token",
            "patient_name": "Boundary Patient",
            "phone": "+998901010101",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["number"] == 7
    assert payload["duplicate"] is False
    domain_service.allocate_ticket.assert_called_once_with(
        allocation_mode="join_with_token",
        token_str="boundary-token",
        patient_name="Boundary Patient",
        phone="+998901010101",
        telegram_id=None,
        source="online",
    )


@pytest.mark.unit
def test_online_queue_join_duplicate_response_is_preserved(client, monkeypatch):
    domain_service = Mock()
    domain_service.allocate_ticket.return_value = {
        "entry": SimpleNamespace(number=5),
        "duplicate": True,
        "duplicate_reason": "телефону +998902020202",
        "specialist_name": "Test Specialist",
        "cabinet": "12A",
    }
    monkeypatch.setattr(
        online_queue_new_module,
        "_queue_domain_service",
        lambda db: domain_service,
    )

    response = client.post(
        "/api/v1/online-queue/join",
        json={
            "token": "duplicate-token",
            "patient_name": "Duplicate Patient",
            "phone": "+998902020202",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["number"] == 5
    assert payload["duplicate"] is True
    assert "телефону +998902020202" in payload["message"]


@pytest.mark.unit
def test_online_queue_join_validation_error_mapping_is_preserved(client, monkeypatch):
    domain_service = Mock()
    domain_service.allocate_ticket.side_effect = QueueValidationError("bad token")
    monkeypatch.setattr(
        online_queue_new_module,
        "_queue_domain_service",
        lambda db: domain_service,
    )

    response = client.post(
        "/api/v1/online-queue/join",
        json={
            "token": "bad-token",
            "patient_name": "Invalid Patient",
            "phone": "+998903030303",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert payload["message"] == "bad token"
