"""Public reset verification has a shared IP budget and opaque failures."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.endpoints import password_reset
from app.db.session import get_db
from app.services.password_reset_service import PasswordResetService
from app.services.phone_verification_store import PhoneStoreUnavailable


@pytest.mark.parametrize("phone", ["+٩٩٨٩٠١٠٢٣٤٥٦", "+998９０１０２３４５６"])
def test_phone_schemas_reject_non_ascii_digits(phone):
    with pytest.raises(ValidationError):
        password_reset.PasswordResetInitiateRequest(phone=phone)
    with pytest.raises(ValidationError):
        password_reset.PhoneVerificationRequest(phone=phone, verification_code="123456")


@pytest.mark.parametrize("code", ["１２３４５６", "١٢٣٤٥٦", "123456\n"])
def test_verification_schema_rejects_unicode_or_trailing_newline(code):
    with pytest.raises(ValidationError):
        password_reset.PhoneVerificationRequest(phone="+998901023456", verification_code=code)


@pytest.fixture
def client(monkeypatch):
    class Verification:
        allowed = True
        unavailable = False
        failure = "CODE_NOT_FOUND"
        seen_ips = []

        def consume_ip_verify_budget(self, ip):
            self.seen_ips.append(ip)
            if self.unavailable:
                raise PhoneStoreUnavailable("SYNTHETIC_PRIVATE_VALUE")
            return self.allowed

        def verify_code(self, **kwargs):
            # Different internal errors are indistinguishable publicly.
            return {"success": False, "error": "internal detail", "error_code": self.failure, "attempts_left": 2}

    verification = Verification()
    service = PasswordResetService()
    service.phone_verification = verification
    monkeypatch.setattr(password_reset, "get_password_reset_service", lambda: service)
    app = FastAPI()
    app.include_router(password_reset.router)
    app.dependency_overrides[get_db] = lambda: None
    with TestClient(app) as api:
        yield api, verification


def post_verification(client, phone="+998901023456"):
    return client.post("/verify-phone", json={"phone": phone, "verification_code": "123456"})


@pytest.mark.parametrize("failure", ["INVALID_CODE", "CODE_EXPIRED", "MAX_ATTEMPTS_EXCEEDED"])
def test_proof_failure_does_not_reveal_issued_code(client, failure):
    api, verification = client
    missing = post_verification(api, "+998901023457")
    verification.failure = failure
    failed = post_verification(api)
    assert missing.status_code == failed.status_code == 404
    assert missing.json() == failed.json()
    assert failed.headers["cache-control"] == "no-store"
    assert "attempts_left" not in str(failed.json())


def test_budget_is_applied_before_phone_lookup_and_fails_closed(client):
    api, verification = client
    verification.allowed = False
    known = post_verification(api)
    unknown = post_verification(api, "+998901023457")
    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json()
    assert known.headers["cache-control"] == "no-store"
    assert len(verification.seen_ips) == 2
    verification.unavailable = True
    known = post_verification(api)
    unknown = post_verification(api, "+998901023457")
    assert known.status_code == unknown.status_code == 503
    assert known.json() == unknown.json()
    assert known.headers["cache-control"] == "no-store"
    assert "SYNTHETIC_PRIVATE_VALUE" not in str(known.json())


def test_successful_bearer_response_is_not_cacheable(client):
    api, _ = client
    service = password_reset.get_password_reset_service()

    async def successful_verification(**kwargs):
        return {"success": True, "message": "ok", "reset_token": "synthetic", "expires_in_hours": 1}

    service.verify_phone_and_get_token = successful_verification
    response = post_verification(api)
    assert response.status_code == 200
    assert response.json()["reset_token"] == "synthetic"
    assert response.headers["cache-control"] == "no-store"
