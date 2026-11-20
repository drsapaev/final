from types import SimpleNamespace

import pytest

from app.services.auth_api_service import AuthApiDomainError, AuthApiService


class Repo:
    def __init__(self, user, *, factor=False, live=None, revoke=False):
        self.user, self.live, self.factor, self.revoke = (
            user,
            live or user,
            factor,
            revoke,
        )
        self.committed = False

    async def get_user_by_username(self, username):
        return self.user

    async def get_user_by_username_or_email(self, username):
        return self.user

    async def get_user_for_update(self, user_id):
        return self.live

    async def has_configured_second_factor(self, user_id):
        return self.factor

    async def apply_login_policy(self, user):
        if self.revoke:
            user.auth_epoch += 1

    async def commit(self):
        self.committed = True


def user(**kw):
    values = {
        "id": 7,
        "username": "john",
        "email": "j@x.io",
        "full_name": "John",
        "role": "Doctor",
        "is_active": True,
        "is_superuser": False,
        "hashed_password": "hash",
        "auth_epoch": 4,
    }
    values.update(kw)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def sign(monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_api_service.verify_password",
        lambda p, h: p == "ok" and h == "hash",
    )
    monkeypatch.setattr(
        "app.services.auth_api_service.create_access_token", lambda data: data
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["oauth", "json"])
@pytest.mark.parametrize("revoke", [False, True])
async def test_fallback_signs_live_identity_and_policy(kind, revoke):
    repo = Repo(user(), revoke=revoke)
    service = AuthApiService(None, repo)
    if kind == "oauth":
        result = await service.login_oauth_payload(username="john", password="ok")
    else:
        result = await service.json_login_payload(
            username="john", password="ok", remember_me=False
        )
    assert result["access_token"] == {"sub": "7", "auth_epoch": 4 + revoke}
    assert repo.committed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes,factor",
    [
        ({"is_active": False}, False),
        ({"is_superuser": True}, False),
        ({"role": "Admin"}, False),
        ({"role": "Cashier"}, False),
        ({"auth_epoch": 5}, False),
        ({"hashed_password": "changed"}, False),
        ({"username": "renamed"}, False),
        ({}, True),
    ],
)
async def test_fallback_rejects_revoked_changed_and_2fa_users(changes, factor):
    repo = Repo(user(), factor=factor, live=user(**changes))
    with pytest.raises(AuthApiDomainError) as exc:
        await AuthApiService(None, repo).login_oauth_payload(
            username="john", password="ok"
        )
    assert exc.value.status_code == 401
    assert not repo.committed
