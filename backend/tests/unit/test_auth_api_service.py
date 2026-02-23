from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.auth_api_service import AuthApiDomainError, AuthApiService


@pytest.mark.unit
class TestAuthApiService:
    @pytest.mark.asyncio
    async def test_login_oauth_payload_raises_for_invalid_credentials(self, monkeypatch):
        async def get_user_by_username(username):
            return None

        repository = SimpleNamespace(
            get_user_by_username=get_user_by_username,
            get_user_by_username_or_email=get_user_by_username,
        )
        service = AuthApiService(db=None, repository=repository)

        with pytest.raises(AuthApiDomainError) as exc_info:
            await service.login_oauth_payload(username="u", password="p")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_oauth_payload_returns_token(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.auth_api_service.verify_password",
            lambda password, hashed: password == "ok" and hashed == "hash",
        )
        monkeypatch.setattr(
            "app.services.auth_api_service.create_access_token",
            lambda payload: f"token-{payload['sub']}",
        )

        async def get_user_by_username(username):
            return SimpleNamespace(username=username, hashed_password="hash")

        repository = SimpleNamespace(
            get_user_by_username=get_user_by_username,
            get_user_by_username_or_email=get_user_by_username,
        )
        service = AuthApiService(db=None, repository=repository)

        payload = await service.login_oauth_payload(username="john", password="ok")

        assert payload["access_token"] == "token-john"
        assert payload["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_json_login_payload_rejects_inactive_user(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.auth_api_service.verify_password",
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
                hashed_password="hash",
            )

        repository = SimpleNamespace(
            get_user_by_username=lambda username: None,
            get_user_by_username_or_email=get_user_by_username_or_email,
        )
        service = AuthApiService(db=None, repository=repository)

        with pytest.raises(AuthApiDomainError) as exc_info:
            await service.json_login_payload(
                username="john",
                password="ok",
                remember_me=False,
            )

        assert exc_info.value.status_code == 401
        assert "деактивирован" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_json_login_payload_returns_user_payload(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.auth_api_service.verify_password",
            lambda password, hashed: password == "ok",
        )
        monkeypatch.setattr(
            "app.services.auth_api_service.create_access_token",
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
                hashed_password="hash",
            )

        repository = SimpleNamespace(
            get_user_by_username=lambda username: None,
            get_user_by_username_or_email=get_user_by_username_or_email,
        )
        service = AuthApiService(db=None, repository=repository)

        payload = await service.json_login_payload(
            username="john",
            password="ok",
            remember_me=True,
        )

        assert payload["access_token"] == "token-7"
        assert payload["user"]["username"] == "john"
