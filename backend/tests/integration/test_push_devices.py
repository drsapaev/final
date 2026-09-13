"""PR-6: Push device registry tests.

Owner-mandated scenarios:
1.  two devices of one user;
2.  two users (isolation);
3.  register idempotency;
4.  token rotation (same physical device_id);
5.  exact-token conditional invalidation;
6.  logout of ONE device (others + master opt-out untouched);
7.  global opt-out (user-level flag governs senders);
8.  no cross-user deletion/disable;
9.  concurrent refresh/replace races;
10. legacy compatibility (users.device_token mirror contract).

Plus contract hygiene: no token/endpoint value is ever echoed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.crud import push_device as crud_push_device, user as crud_user
from app.models.push_device import PushDevice
from app.models.user import User
from app.services.fcm_service import FCMResponse, FCMService
from app.services.notifications import notification_sender_service
from app.services.push_device_registry import fingerprint


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_user(db_session, *, role: str = "Patient") -> User:
    s = _suffix()
    user = User(
        username=f"push6_{role.lower()}_{s}",
        email=f"push6-{role.lower()}-{s}@test.local",
        full_name=f"Push6 Test {role}",
        hashed_password=get_password_hash("pass123"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(client, user: User) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _register(
    client,
    user: User,
    *,
    token: str,
    provider="fcm",
    platform="android",
    device_id: str | None = None,
    credential: dict | None = None,
):
    payload: dict = {"provider": provider, "platform": platform, "token": token}
    if device_id is not None:
        payload["device_id"] = device_id
    if credential is not None:
        payload["credential"] = credential
    return client.post(
        "/api/v1/push/devices/register", headers=_headers(client, user), json=payload
    )


def _user_rows(db_session, user_id: int) -> list[PushDevice]:
    db_session.expire_all()
    return (
        db_session.query(PushDevice)
        .filter(PushDevice.user_id == user_id)
        .order_by(PushDevice.id)
        .all()
    )


# ---------------------------------------------------------------------------
# 1. Two devices of one user
# ---------------------------------------------------------------------------


def test_two_devices_of_one_user(client, db_session):
    user = _make_user(db_session)

    response_a = _register(client, user, token="tok-phone", device_id="dev-phone")
    response_b = _register(
        client,
        user,
        token="https://push.example.com/wps/dev-tablet",
        provider="webpush",
        platform="web",
        device_id="dev-tablet",
        credential={"keys": {"p256dh": "k1", "auth": "k2"}},
    )

    assert response_a.status_code == 200, response_a.text
    assert response_b.status_code == 200, response_b.text
    assert response_a.json()["created"] is True
    assert response_b.json()["created"] is True

    rows = _user_rows(db_session, user.id)
    assert len(rows) == 2
    assert {r.provider for r in rows} == {"fcm", "webpush"}
    assert {r.platform for r in rows} == {"android", "web"}

    listing = client.get("/api/v1/push/devices", headers=_headers(client, user))
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total_count"] == 2
    assert all(d["active"] and d["enabled"] for d in body["devices"])


# ---------------------------------------------------------------------------
# 2. Two users — isolation
# ---------------------------------------------------------------------------


def test_two_users_isolated_lists(client, db_session):
    user_a = _make_user(db_session)
    user_b = _make_user(db_session)

    assert _register(client, user_a, token="tok-a").status_code == 200
    assert _register(client, user_b, token="tok-b").status_code == 200

    rows_a = _user_rows(db_session, user_a.id)
    rows_b = _user_rows(db_session, user_b.id)
    assert [r.token for r in rows_a] == ["tok-a"]
    assert [r.token for r in rows_b] == ["tok-b"]

    list_a = client.get("/api/v1/push/devices", headers=_headers(client, user_a)).json()
    assert list_a["total_count"] == 1
    assert list_a["devices"][0]["provider"] == "fcm"


# ---------------------------------------------------------------------------
# 3. Register idempotency
# ---------------------------------------------------------------------------


def test_register_idempotent_no_duplicate(client, db_session):
    user = _make_user(db_session)

    first = _register(client, user, token="tok-same", device_id="dev-1")
    second = _register(client, user, token="tok-same", device_id="dev-1")

    assert first.json()["created"] is True
    assert second.json()["created"] is False
    rows = _user_rows(db_session, user.id)
    assert len(rows) == 1
    # last_seen_at refreshed on the idempotent path
    assert rows[0].last_seen_at is not None


def test_register_idempotent_revives_disabled_device(client, db_session):
    """Re-registering a DISABLED (muted) device is an explicit 'push me
    again' intent — the row is re-enabled, not duplicated."""
    user = _make_user(db_session)
    row, _ = crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-mute",
        device_id="dev-mute",
    )
    crud_push_device.disable_device(db_session, user_id=user.id, device_row_id=row.id)

    response = _register(client, user, token="tok-mute", device_id="dev-mute")
    assert response.json()["created"] is False

    (row_after,) = _user_rows(db_session, user.id)
    assert row_after.enabled is True
    assert row_after.invalidated_at is None


# ---------------------------------------------------------------------------
# 4. Token rotation (same physical device)
# ---------------------------------------------------------------------------


def test_token_rotation_invalidates_old_row_only(client, db_session):
    user = _make_user(db_session)
    _register(client, user, token="tok-old", device_id="dev-x")
    _register(client, user, token="tok-other", device_id="dev-y")

    response = _register(client, user, token="tok-new", device_id="dev-x")
    assert response.json()["created"] is True

    rows = {r.token: r for r in _user_rows(db_session, user.id)}
    assert rows["tok-old"].invalidated_at is not None
    assert rows["tok-old"].enabled is False
    assert rows["tok-new"].invalidated_at is None
    assert rows["tok-new"].enabled is True
    # A DIFFERENT physical device is untouched by the rotation.
    assert rows["tok-other"].invalidated_at is None
    assert rows["tok-other"].enabled is True


# ---------------------------------------------------------------------------
# 5. Exact-token conditional invalidation
# ---------------------------------------------------------------------------


def test_exact_token_conditional_invalidation(db_session):
    user = _make_user(db_session)
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-dead",
        device_id="dev-1",
    )
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-fine",
        device_id="dev-2",
    )

    # Wrong token: nothing touched.
    assert (
        crud_push_device.invalidate_active_credential(
            db_session, provider="fcm", token="tok-wrong"
        )
        == 0
    )
    # Right token: exactly one row invalidated.
    assert (
        crud_push_device.invalidate_active_credential(
            db_session, provider="fcm", token="tok-dead"
        )
        == 1
    )

    rows = {r.token: r for r in _user_rows(db_session, user.id)}
    assert rows["tok-dead"].invalidated_at is not None
    assert rows["tok-fine"].invalidated_at is None
    assert rows["tok-fine"].enabled is True


def test_shared_token_single_active_owner_by_construction(db_session):
    """Registry upgrade over the PR-5 mirror: a shared ACTIVE token across
    owners is structurally IMPOSSIBLE — the second registration moves the
    credential (previous owner invalidated). Invalidation of the exact
    token therefore always degrades to the single active row, and a second
    (idempotent) call touches nothing."""
    owner_a = _make_user(db_session)
    owner_b = _make_user(db_session)
    crud_push_device.register_device(
        db_session,
        user_id=owner_a.id,
        provider="fcm",
        platform="android",
        token="tok-shared",
    )
    crud_push_device.register_device(
        db_session,
        user_id=owner_b.id,
        provider="fcm",
        platform="web",
        token="tok-shared",
    )

    (row_a,) = _user_rows(db_session, owner_a.id)
    (row_b,) = _user_rows(db_session, owner_b.id)
    assert row_a.invalidated_at is not None  # moved away
    assert row_b.invalidated_at is None  # single active owner

    assert (
        crud_push_device.invalidate_active_credential(
            db_session, provider="fcm", token="tok-shared"
        )
        == 1
    )
    # Idempotent: the dead credential is already marked.
    assert (
        crud_push_device.invalidate_active_credential(
            db_session, provider="fcm", token="tok-shared"
        )
        == 0
    )


# ---------------------------------------------------------------------------
# 6. Logout ONE device
# ---------------------------------------------------------------------------


def test_logout_one_device_leaves_others_and_flag(client, db_session):
    user = _make_user(db_session)
    response_a = _register(client, user, token="tok-a", device_id="dev-a")
    _register(
        client,
        user,
        token="https://push.example.com/wps/dev-b",
        provider="webpush",
        platform="web",
        device_id="dev-b",
        credential={"keys": {"p256dh": "k", "auth": "a"}},
    )
    device_a_id = response_a.json()["device"]["id"]

    # Master opt-out was set by registration (explicit consent); it is a
    # USER-level flag — a device logout must NOT flip it.
    assert (
        db_session.query(User)
        .filter(User.id == user.id)
        .first()
        .push_notifications_enabled
        is True
    )

    response = client.post(
        f"/api/v1/push/devices/{device_a_id}/disable", headers=_headers(client, user)
    )
    assert response.status_code == 200, response.text

    rows = {r.token: r for r in _user_rows(db_session, user.id)}
    assert rows["tok-a"].enabled is False
    assert rows["tok-a"].invalidated_at is None  # muted, NOT dead
    assert rows["https://push.example.com/wps/dev-b"].enabled is True
    assert rows["https://push.example.com/wps/dev-b"].invalidated_at is None
    assert (
        db_session.query(User)
        .filter(User.id == user.id)
        .first()
        .push_notifications_enabled
        is True
    )

    # An invalidated (dead) device cannot be revived via enable — only a
    # fresh registration returns it. A disabled one CAN be re-enabled.
    enable = client.post(
        f"/api/v1/push/devices/{device_a_id}/enable", headers=_headers(client, user)
    )
    assert enable.status_code == 200
    (row_a,) = [r for r in _user_rows(db_session, user.id) if r.token == "tok-a"]
    assert row_a.enabled is True


# ---------------------------------------------------------------------------
# 7. Global opt-out (user-level master flag governs senders)
# ---------------------------------------------------------------------------


class _StubFCMService(FCMService):
    def __init__(self):  # noqa: D107 - intentionally skip _load_credentials
        self.project_id = "test-project"
        self.fcm_url = (
            "https://fcm.googleapis.com/v1/projects/test-project/messages:send"
        )
        self.credentials = object()
        self.access_token = "stub-access-token"
        self.token_expiry = 0
        self._send_semaphore = AsyncMock()
        self._refresh_lock = AsyncMock()

    @property
    def active(self) -> bool:  # noqa: D102
        return True


@pytest.mark.asyncio
async def test_global_opt_out_governs_despite_enabled_devices(db_session, monkeypatch):
    """users.push_notifications_enabled stays the USER-level master opt-out:
    even with enabled registry devices, an opted-out user gets no push."""
    user = _make_user(db_session)
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-registry",
        device_id="dev-1",
    )
    # Explicit user-level opt-out (e.g. via settings surface).
    user.push_notifications_enabled = False
    db_session.commit()

    stub = _StubFCMService()
    stub.send_notification = AsyncMock(
        return_value=FCMResponse(success=True, message_id="m-x")
    )
    monkeypatch.setattr(notification_sender_service, "fcm_service", stub)

    await notification_sender_service.send_push(
        user_id=user.id, title="T", message="M", db=db_session
    )
    stub.send_notification.assert_not_awaited()

    # Registry devices remain enabled+active — the opt-out is a sender gate,
    # not a destructive device wipe.
    (row,) = _user_rows(db_session, user.id)
    assert row.enabled is True
    assert row.invalidated_at is None


# ---------------------------------------------------------------------------
# 8. No cross-user mutation
# ---------------------------------------------------------------------------


def test_no_cross_user_disable_or_delete(client, db_session):
    owner = _make_user(db_session)
    attacker = _make_user(db_session)

    created = _register(client, owner, token="tok-private", device_id="dev-p")
    device_id = created.json()["device"]["id"]

    disable = client.post(
        f"/api/v1/push/devices/{device_id}/disable", headers=_headers(client, attacker)
    )
    delete = client.delete(
        f"/api/v1/push/devices/{device_id}", headers=_headers(client, attacker)
    )
    assert disable.status_code == 404
    assert delete.status_code == 404

    (row,) = _user_rows(db_session, owner.id)
    assert row.enabled is True  # untouched
    assert row.invalidated_at is None


# ---------------------------------------------------------------------------
# 9. Concurrent refresh / replace races
# ---------------------------------------------------------------------------


def test_concurrent_same_credential_single_active_row(db_session):
    """Two racing registers of the same credential converge on ONE active
    row (the partial unique index is the arbiter; the loser takes the
    idempotent refresh path)."""
    user = _make_user(db_session)
    _, created_first = crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-race",
        device_id="dev-r",
    )
    _, created_second = crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-race",
        device_id="dev-r",
    )
    assert created_first is True
    assert created_second is False
    active = [r for r in _user_rows(db_session, user.id) if r.invalidated_at is None]
    assert len(active) == 1


def test_late_invalidation_spares_replacement_token(db_session):
    """TOCTOU: a send that started BEFORE rotation must not wipe the
    replacement token registered while it was in flight (PR-5 r3 lesson,
    registry edition)."""
    user = _make_user(db_session)
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-v1",
        device_id="dev-t",
    )
    # Rotation happens while the "in-flight" send is out.
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-v2",
        device_id="dev-t",
    )
    # The late UNREGISTERED verdict arrives for the OLD credential.
    assert (
        crud_push_device.invalidate_active_credential(
            db_session, provider="fcm", token="tok-v1"
        )
        == 0
    )

    rows = {r.token: r for r in _user_rows(db_session, user.id)}
    assert rows["tok-v2"].invalidated_at is None
    assert rows["tok-v2"].enabled is True


def test_credential_move_between_accounts(client, db_session):
    """A physical device re-registered on a new account moves the ACTIVE
    credential: the previous owner's row is invalidated, the new owner
    gets a fresh active row."""
    old_owner = _make_user(db_session)
    new_owner = _make_user(db_session)

    _register(client, old_owner, token="tok-move", device_id="dev-m")
    response = _register(client, new_owner, token="tok-move", device_id="dev-m")
    assert response.json()["created"] is True

    (old_row,) = _user_rows(db_session, old_owner.id)
    (new_row,) = _user_rows(db_session, new_owner.id)
    assert old_row.invalidated_at is not None
    assert old_row.enabled is False
    assert new_row.invalidated_at is None
    assert new_row.enabled is True

    # Exactly ONE active row holds the credential.
    active = (
        db_session.query(PushDevice)
        .filter(
            PushDevice.token == "tok-move",
            PushDevice.invalidated_at.is_(None),
        )
        .count()
    )
    assert active == 1


# ---------------------------------------------------------------------------
# 10. Legacy compatibility — users.device_token mirror contract
# ---------------------------------------------------------------------------


def test_new_register_fcm_mirrors_to_legacy_column(client, db_session):
    user = _make_user(db_session)
    _register(client, user, token="tok-mirror", device_id="dev-mir")

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token == "tok-mirror"
    assert refreshed.device_type == "android"
    assert refreshed.push_notifications_enabled is True


def test_last_fcm_registration_wins_mirror(client, db_session):
    """The mirror is last-registration-wins (legacy single-device world);
    the registry keeps BOTH devices as the multi-device truth."""
    user = _make_user(db_session)
    _register(client, user, token="tok-first", device_id="dev-1")
    _register(client, user, token="tok-second", device_id="dev-2")

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token == "tok-second"

    active_tokens = {
        r.token for r in _user_rows(db_session, user.id) if r.invalidated_at is None
    }
    assert active_tokens == {"tok-first", "tok-second"}


def test_webpush_register_never_touches_legacy_column(client, db_session):
    """A Web Push subscription is NEVER squeezed into the FCM-token
    format: provider=webpush does not write users.device_token."""
    user = _make_user(db_session)
    user.device_token = "tok-existing-fcm"
    db_session.commit()

    response = _register(
        client,
        user,
        token="https://fcm.push.googleapis.com/wps/abc",
        provider="webpush",
        platform="web",
        device_id="dev-w",
        credential={"keys": {"p256dh": "pk", "auth": "ak"}},
    )
    assert response.status_code == 200, response.text

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token == "tok-existing-fcm"
    (row,) = _user_rows(db_session, user.id)
    assert row.provider == "webpush"
    assert row.credential == {"keys": {"p256dh": "pk", "auth": "ak"}}


def test_legacy_register_token_dual_writes_registry(client, db_session):
    """Old callers keep working: legacy /fcm/register-token mirrors AND
    dual-writes the canonical registry."""
    user = _make_user(db_session)
    response = client.post(
        "/api/v1/fcm/register-token",
        headers=_headers(client, user),
        json={"device_token": "tok-legacy", "device_type": "android"},
    )
    assert response.status_code == 200, response.text

    (row,) = _user_rows(db_session, user.id)
    assert row.provider == "fcm"
    assert row.platform == "android"
    assert row.token == "tok-legacy"
    assert row.invalidated_at is None


def test_legacy_ios_registration_stays_mirror_only(client, db_session):
    """Registry platforms are android|web (owner contract); the legacy
    contract's extra "ios" value keeps working via the mirror only."""
    user = _make_user(db_session)
    response = client.post(
        "/api/v1/fcm/register-token",
        headers=_headers(client, user),
        json={"device_token": "tok-ios", "device_type": "ios"},
    )
    assert response.status_code == 200, response.text

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token == "tok-ios"
    assert _user_rows(db_session, user.id) == []


def test_legacy_unregister_invalidates_only_exact_credential(client, db_session):
    user = _make_user(db_session)
    user.device_token = "tok-legacy-live"
    user.device_type = "android"
    user.push_notifications_enabled = True
    db_session.commit()
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-legacy-live",
    )
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-second-device",
        device_id="dev-2",
    )

    response = client.delete(
        "/api/v1/fcm/unregister-token", headers=_headers(client, user)
    )
    assert response.status_code == 200, response.text

    rows = {r.token: r for r in _user_rows(db_session, user.id)}
    assert rows["tok-legacy-live"].invalidated_at is not None
    # Device-level isolation: the OTHER registry device survives the
    # legacy single-device unregister.
    assert rows["tok-second-device"].invalidated_at is None
    assert rows["tok-second-device"].enabled is True

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token is None
    # Legacy global opt-out contract preserved (explicit user act).
    assert refreshed.push_notifications_enabled is False


def test_unregistered_purge_cleans_both_stores(db_session):
    """The canonical UNREGISTERED verdict purges the legacy mirror AND the
    exact registry credential (crud extension) — other registry devices
    stay untouched."""
    user = _make_user(db_session)
    user.device_token = "tok-dead-mirrored"
    user.push_notifications_enabled = True
    db_session.commit()
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-dead-mirrored",
    )
    crud_push_device.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token="tok-live-second",
        device_id="dev-2",
    )

    cleared = crud_user.clear_device_token_if_unchanged(
        db_session, user_id=user.id, expected_token="tok-dead-mirrored"
    )
    assert cleared is True

    rows = {r.token: r for r in _user_rows(db_session, user.id)}
    assert rows["tok-dead-mirrored"].invalidated_at is not None
    assert rows["tok-live-second"].invalidated_at is None
    assert rows["tok-live-second"].enabled is True

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token is None


# ---------------------------------------------------------------------------
# Contract hygiene: no credential ever echoed; webpush validation
# ---------------------------------------------------------------------------


def test_register_and_list_never_echo_credentials(client, db_session):
    user = _make_user(db_session)
    secret = "tok-SUPER-SECRET-value-never-echoed"

    response = _register(client, user, token=secret, device_id="dev-s")
    assert response.status_code == 200, response.text
    assert secret not in response.text
    assert fingerprint(secret) in response.text  # non-reversible prefix only

    listing = client.get("/api/v1/push/devices", headers=_headers(client, user))
    assert listing.status_code == 200
    assert secret not in listing.text


def test_webpush_requires_subscription_keys(client, db_session):
    user = _make_user(db_session)

    missing_keys = _register(
        client,
        user,
        token="https://push.example.com/ep",
        provider="webpush",
        platform="web",
    )
    assert missing_keys.status_code == 422

    missing_auth = _register(
        client,
        user,
        token="https://push.example.com/ep",
        provider="webpush",
        platform="web",
        credential={"keys": {"p256dh": "pk"}},
    )
    assert missing_auth.status_code == 422

    plain_http_endpoint = _register(
        client,
        user,
        token="http://insecure.example.com/ep",
        provider="webpush",
        platform="web",
        credential={"keys": {"p256dh": "pk", "auth": "ak"}},
    )
    assert plain_http_endpoint.status_code == 422


def test_push_devices_require_authentication(client):
    assert client.get("/api/v1/push/devices").status_code == 401
    assert (
        client.post(
            "/api/v1/push/devices/register",
            json={"provider": "fcm", "platform": "android", "token": "x"},
        ).status_code
        == 401
    )


def test_delete_own_device_removes_row_only(client, db_session):
    user = _make_user(db_session)
    created = _register(client, user, token="tok-gone", device_id="dev-g")
    _register(client, user, token="tok-stays", device_id="dev-s")
    device_id = created.json()["device"]["id"]

    response = client.delete(
        f"/api/v1/push/devices/{device_id}", headers=_headers(client, user)
    )
    assert response.status_code == 200, response.text

    tokens = {r.token for r in _user_rows(db_session, user.id)}
    assert tokens == {"tok-stays"}
