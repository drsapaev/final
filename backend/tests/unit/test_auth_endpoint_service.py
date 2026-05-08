from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.auth_endpoint_service import AuthDomainError, AuthEndpointService
from tests.auth_test_credentials import DUMMY_PASSWORD_HASH, GENERIC_TEST_PASSWORD


@pytest.mark.unit
class TestAuthEndpointService:
    @pytest.mark.asyncio
    async def test_login_oauth_payload_raises_for_invalid_credentials(self, monkeypatch):
        async def get_user_by_username(username):
            return None

        repository = SimpleNamespace(
            get_user_by_username=get_user_by_username,
            get_user_by_username_or_email=get_user_by_username,
        )
        service = AuthEndpointService(db=None, repository=repository)

        with pytest.raises(AuthDomainError) as exc_info:
            await service.login_oauth_payload(username="u", password=GENERIC_TEST_PASSWORD)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_oauth_payload_returns_token(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.auth_endpoint_service.verify_password",
            lambda password, hashed: password == GENERIC_TEST_PASSWORD
            and hashed == DUMMY_PASSWORD_HASH,
        )
        monkeypatch.setattr(
            "app.services.auth_endpoint_service.create_access_token",
            lambda payload: f"token-{payload['sub']}",
        )

        async def get_user_by_username(username):
            return SimpleNamespace(username=username, hashed_password=DUMMY_PASSWORD_HASH)

        repository = SimpleNamespace(
            get_user_by_username=get_user_by_username,
            get_user_by_username_or_email=get_user_by_username,
        )
        service = AuthEndpointService(db=None, repository=repository)

        payload = await service.login_oauth_payload(
            username="john",
            password=GENERIC_TEST_PASSWORD,
        )

        assert payload["access_token"] == "token-john"
        assert payload["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_json_login_payload_rejects_inactive_user(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.auth_endpoint_service.verify_password",
            lambda password, hashed: True,
        )

        async def get_user_by_username_or_email(username):
            return SimpleNamespace(
                id=1,
                username="john",
                email="j@x.io",
                full_name="John",
                role="Doctor",
                is_active=False,
                is_superuser=False,
                hashed_password=DUMMY_PASSWORD_HASH,
            )

        repository = SimpleNamespace(
            get_user_by_username=lambda username: None,
            get_user_by_username_or_email=get_user_by_username_or_email,
        )
        service = AuthEndpointService(db=None, repository=repository)

        with pytest.raises(AuthDomainError) as exc_info:
            await service.json_login_payload(
                username="john",
                password=GENERIC_TEST_PASSWORD,
                remember_me=False,
            )

        assert exc_info.value.status_code == 401
        assert "деактивирован" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_json_login_payload_returns_user_payload(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.auth_endpoint_service.verify_password",
            lambda password, hashed: password == GENERIC_TEST_PASSWORD,
        )
        monkeypatch.setattr(
            "app.services.auth_endpoint_service.create_access_token",
            lambda data: f"token-{data['sub']}",
        )

        async def get_user_by_username_or_email(username):
            return SimpleNamespace(
                id=7,
                username="john",
                email="j@x.io",
                full_name="John",
                role="Doctor",
                is_active=True,
                is_superuser=False,
                hashed_password=DUMMY_PASSWORD_HASH,
            )

        repository = SimpleNamespace(
            get_user_by_username=lambda username: None,
            get_user_by_username_or_email=get_user_by_username_or_email,
        )
        service = AuthEndpointService(db=None, repository=repository)

        payload = await service.json_login_payload(
            username="john",
            password=GENERIC_TEST_PASSWORD,
            remember_me=True,
        )

        assert payload["access_token"] == "token-7"
        assert payload["user"]["username"] == "john"
