"""Email verification delivery never claims success or leaks its link."""
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from app.api.deps import create_access_token
from app.core.config import settings
from app.models.authentication import EmailVerificationToken
from app.models.user import User
from app.services.email_verification_delivery import (
    VerificationConfigurationError,
    verification_url,
)


@pytest.fixture
def account(db_session):
    user = User(username="SYNTHETIC_" + uuid4().hex, email=uuid4().hex + "@example.com", role="Registrar", is_active=True, is_superuser=False, hashed_password="synthetic")
    db_session.add(user)
    db_session.commit()
    token = create_access_token({"sub": str(user.id), "auth_epoch": user.auth_epoch})
    return user, {"Authorization": f"Bearer {token}"}


class FakeMail:
    def __init__(self, ok=True):
        self.ok = ok
        self.deliveries = []
    async def send_email_enhanced(self, **message):
        self.deliveries.append(message)
        return self.ok, "synthetic provider detail"


def test_delivery_link_can_be_confirmed_once(client, db_session, account, monkeypatch, caplog):
    import app.api.v1.endpoints.authentication as endpoint
    user, headers = account
    mail = FakeMail()
    monkeypatch.setattr(endpoint, "get_email_sms_enhanced_service", lambda: mail)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example")
    response = client.post("/api/v1/authentication/email-verification", headers=headers)
    assert response.status_code == 200, response.text
    assert len(mail.deliveries) == 1 and mail.deliveries[0]["to_email"] == user.email
    url = mail.deliveries[0]["text_content"].splitlines()[1]
    parsed = urlsplit(url)
    assert parsed.scheme == "https" and parsed.netloc == "frontend.example" and parsed.path == "/verify-email" and not parsed.query
    token = parse_qs(parsed.fragment)["token"][0]
    assert token not in response.text and token not in caplog.text
    result = client.post("/api/v1/authentication/email-verification/confirm", json={"token": token})
    assert result.status_code == 200, result.text
    assert client.post("/api/v1/authentication/email-verification/confirm", json={"token": token}).status_code == 400
    db_session.expire_all()
    assert user.profile.email_verified
    assert token not in caplog.text


def test_failed_delivery_preserves_existing_link(client, db_session, account, monkeypatch):
    import app.api.v1.endpoints.authentication as endpoint
    from app.services.authentication_service import AuthenticationService
    user, headers = account
    old = AuthenticationService().create_email_verification_token(db_session, user.id)["token"]
    mail = FakeMail(ok=False)
    monkeypatch.setattr(endpoint, "get_email_sms_enhanced_service", lambda: mail)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example")
    response = client.post("/api/v1/authentication/email-verification", headers=headers)
    assert response.status_code == 502
    assert "synthetic provider detail" not in response.text
    assert client.post("/api/v1/authentication/email-verification/confirm", json={"token": old}).status_code == 200
    sent_token = parse_qs(urlsplit(mail.deliveries[0]["text_content"].splitlines()[1]).fragment)["token"][0]
    assert client.post("/api/v1/authentication/email-verification/confirm", json={"token": sent_token}).status_code == 400


def test_account_limit_counts_failed_delivery_attempts(client, account, monkeypatch):
    import app.api.v1.endpoints.authentication as endpoint
    _, headers = account
    mail = FakeMail(ok=False)
    monkeypatch.setattr(endpoint, "get_email_sms_enhanced_service", lambda: mail)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example")
    assert [client.post("/api/v1/authentication/email-verification", headers=headers).status_code for _ in range(4)] == [502, 502, 502, 429]
    assert len(mail.deliveries) == 3


@pytest.mark.parametrize("origin", ["https://evil.example@frontend.example", "https://frontend.example/path", "https://frontend.example/?x=1", "https://frontend.example/#frag", "http://remote.example", "https://frontend.example\\@evil.example", "javascript:alert(1)"])
def test_bad_frontend_origins_are_rejected(monkeypatch, origin):
    monkeypatch.setattr(settings, "FRONTEND_URL", origin)
    with pytest.raises(VerificationConfigurationError):
        verification_url("synthetic")


def test_expired_history_is_removed_before_new_reservation(db_session, account, monkeypatch):
    from app.services.email_verification_delivery import reserve_verification
    from app.services.profile_contact_security import ProfileBearerContext
    user, _ = account
    now = datetime.now(UTC)
    db_session.add(EmailVerificationToken(user_id=user.id, token="synthetic-expired-token", verified=True, created_at=now-timedelta(days=3), expires_at=now-timedelta(days=2)))
    db_session.commit()
    reserve_verification(db_session, ProfileBearerContext(user.id, user.auth_epoch, None, None, None), None, None)
    assert db_session.query(EmailVerificationToken).filter_by(token="synthetic-expired-token").first() is None


def test_unexpected_provider_exception_does_not_leak_link(client, account, monkeypatch, caplog):
    import app.api.v1.endpoints.authentication as endpoint
    _, headers = account
    class BrokenMail:
        async def send_email_enhanced(self, **message):
            raise RuntimeError(message["text_content"])
    monkeypatch.setattr(endpoint, "get_email_sms_enhanced_service", lambda: BrokenMail())
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example")
    response = client.post("/api/v1/authentication/email-verification", headers=headers)
    assert response.status_code == 502
    assert "#token=" not in response.text and "#token=" not in caplog.text


@pytest.mark.parametrize("missing", ["jti", "exp"])
def test_delivery_requires_expiring_individually_revocable_bearer(client, account, monkeypatch, missing):
    import jwt

    import app.api.v1.endpoints.authentication as endpoint
    user, _ = account
    claims = {"sub": str(user.id), "auth_epoch": user.auth_epoch, "jti": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)}
    claims.pop(missing)
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    mail = FakeMail()
    monkeypatch.setattr(endpoint, "get_email_sms_enhanced_service", lambda: mail)
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example")
    response = client.post("/api/v1/authentication/email-verification", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401 and not mail.deliveries
