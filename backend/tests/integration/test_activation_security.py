"""Public activation disclosure and shared admission regression tests."""
from __future__ import annotations

import secrets
import threading

import pytest
from fastapi import HTTPException, Request

from app.core import activation_rate_limit as budget
from app.core.security import get_password_hash
from app.models.activation import Activation, ActivationStatus
from app.models.clinic import Branch, ClinicSettings
from app.models.user import User
from app.services.setup_service import SetupService
from tests.integration.test_setup_api import build_payload

pytestmark = pytest.mark.integration


class FakeSharedBudget:
    def __init__(self):
        self.values = {}
        self.lock = threading.Lock()

    def consume(self, db, client_key):
        with self.lock:
            if (self.values.get("global", 0) >= budget._GLOBAL_LIMIT or
                self.values.get(client_key, 0) >= budget._CLIENT_LIMIT):
                return False
            self.values["global"] = self.values.get("global", 0) + 1
            self.values[client_key] = self.values.get(client_key, 0) + 1
            return True


@pytest.fixture
def active_budget(monkeypatch):
    store = FakeSharedBudget()
    monkeypatch.setattr(budget, "_testing_bypass", lambda: False)
    monkeypatch.setattr(budget, "_consume_budget", store.consume)
    return store


def test_shared_budget_covers_both_paths_and_survives_setup_rollback(client, db_session, active_budget):
    invalid_key = "SYNTHETIC-" + secrets.token_hex(12)
    setup = build_payload(activation_key=invalid_key)
    for index in range(5):
        if index % 2:
            response = client.post("/api/v1/setup/initialize", json=setup)
            assert response.status_code == 400
        else:
            response = client.post("/api/v1/activation/activate", json={"key": invalid_key})
            assert response.status_code == 200 and not response.json()["ok"]
    response = client.post("/api/v1/activation/activate", json={"key": invalid_key})
    assert response.status_code == 429
    assert client.post("/api/v1/setup/initialize", json=setup).status_code == 429
    assert db_session.query(ClinicSettings).count() == 0
    assert db_session.query(Branch).count() == 0
    assert db_session.query(User).count() == 0
    assert client.post("/api/v1/setup/initialize", json=build_payload()).status_code == 200
    assert invalid_key not in repr(active_budget.values)


def test_proxy_headers_do_not_bypass_budget(client, active_budget):
    invalid_key = "SYNTHETIC-" + secrets.token_hex(12)
    for n in range(5):
        response = client.post("/api/v1/activation/activate", json={"key": invalid_key},
                               headers={"X-Forwarded-For": f"192.0.2.{n + 1}"})
        assert response.status_code == 200
    assert client.post("/api/v1/activation/activate", json={"key": invalid_key},
                       headers={"X-Forwarded-For": "192.0.2.99"}).status_code == 429


def test_distributed_clients_share_global_limit_and_address_is_not_stored(monkeypatch, active_budget):
    monkeypatch.setattr(budget, "_GLOBAL_LIMIT", 3)
    for n in range(1, 5):
        address = f"192.0.2.{n}"
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": [],
                           "client": (address, 123), "server": ("testserver", 80), "scheme": "http"})
        if n <= 3:
            budget.enforce_activation_budget(request, None)
        else:
            with pytest.raises(HTTPException) as exc:
                budget.enforce_activation_budget(request, None)
            assert exc.value.status_code == 429
        assert address not in repr(active_budget.values)


def test_throttled_client_cannot_exhaust_global_budget(monkeypatch, active_budget):
    monkeypatch.setattr(budget, "_GLOBAL_LIMIT", 6)
    def request_for(address):
        return Request({"type": "http", "method": "POST", "path": "/", "headers": [],
                        "client": (address, 123), "server": ("testserver", 80), "scheme": "http"})
    for _ in range(5):
        budget.enforce_activation_budget(request_for("192.0.2.1"), None)
    for _ in range(10):
        with pytest.raises(HTTPException) as exc:
            budget.enforce_activation_budget(request_for("192.0.2.1"), None)
        assert exc.value.status_code == 429
    budget.enforce_activation_budget(request_for("192.0.2.2"), None)


def test_unavailable_budget_fails_closed_but_no_key_setup_works(client, monkeypatch):
    monkeypatch.setattr(budget, "_testing_bypass", lambda: False)
    def fail(*args):
        raise RuntimeError("private-storage-detail")
    monkeypatch.setattr(budget, "_consume_budget", fail)
    key = "SYNTHETIC-" + secrets.token_hex(12)
    for url, payload in [
        ("/api/v1/activation/activate", {"key": key}),
        ("/api/v1/setup/initialize", build_payload(activation_key=key)),
    ]:
        response = client.post(url, json=payload)
        assert response.status_code == 503
        assert "private-storage-detail" not in response.text
    assert client.post("/api/v1/setup/initialize", json=build_payload()).status_code == 200


def test_status_masks_key_and_machine_and_conflict_hides_other_machine(client, db_session, monkeypatch, caplog):
    from app.core import activation as activation_core
    from tests.conftest import mint_access_token

    local_hash = "LOCAL-" + secrets.token_hex(20)
    other_hash = "OTHER-" + secrets.token_hex(20)
    monkeypatch.setattr(activation_core, "server_machine_hash", lambda: local_hash)
    # The admin issue operation may disclose the new key to its authenticated
    # caller, but neither logs nor the public status response may do so.
    admin = User(username="SYNTHETIC_" + secrets.token_hex(8), role="Admin",
                 hashed_password=get_password_hash(secrets.token_urlsafe(24)),
                 is_active=True, is_superuser=True)
    db_session.add(admin)
    db_session.commit()
    with caplog.at_level("INFO"):
        issued = client.post("/api/v1/activation/issue", json={"days": 5},
                             headers={"Authorization": f"Bearer {mint_access_token(admin)}"})
    assert issued.status_code == 200
    key = issued.json()["key"]
    assert key not in caplog.text
    assert client.post("/api/v1/activation/activate", json={"key": key}).json()["ok"]
    status = client.get("/api/v1/activation/status").json()
    assert status["ok"] and status["key"] == "****" + key[-4:]
    assert status["machine_hash"] == "****" + local_hash[-4:]
    assert key not in repr(status) and local_hash not in repr(status)

    other_key = "SYNTHETIC-" + secrets.token_hex(12)
    db_session.add(Activation(key=other_key, machine_hash=other_hash, status=ActivationStatus.ACTIVE))
    db_session.commit()
    conflict = client.post("/api/v1/activation/activate", json={"key": other_key}).json()
    assert not conflict["ok"] and conflict["reason"] == "KEY_IN_USE"
    assert conflict["machine_hash"] is None and other_hash not in repr(conflict)


def test_setup_unexpected_error_is_generic(client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SETUP_CANARY")
    monkeypatch.setattr(SetupService, "_create_branch", fail)
    response = client.post("/api/v1/setup/initialize", json=build_payload())
    assert response.status_code == 500
    assert "PRIVATE_SETUP_CANARY" not in response.text
