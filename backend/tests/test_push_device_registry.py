"""PR-6: push device registry — specification tests.

Covers the ten specification invariants plus credential hygiene:

1.  two devices, one user (multi-device core);
2.  two users — isolated registries;
3.  register idempotency (client statement is authoritative);
4.  token rotation (explicit previous_token retires the exact old row);
5.  exact-token conditional invalidation (provider feedback path);
6.  single-device logout leaves other devices and users untouched;
7.  global opt-out: user-level master beats device-level switch;
8.  no cross-user deletion/toggle;
9.  concurrent refresh/replace — unique-slot recovery + DB-level guard;
10. legacy compatibility (users.device_token untouched by this surface;
    legacy /fcm endpoints keep working unchanged);
11. credential never appears in responses or logs (fingerprint only).

Activation status: no sender consumes the registry in this PR —
``list_sendable_tokens`` is exercised as the documented future
integration point only.
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.push_device import PushDevice
from app.models.user import User
from app.services import push_device_registry as registry
from tests.conftest import mint_access_token

ANDROID_TOKEN = "pr6-test-android-credential-01"
WEB_TOKEN = "pr6-test-webpush-subscription-json-02"
OTHER_TOKEN = "pr6-test-second-user-credential-03"


def _get_or_create_user(db_session: Session, username: str) -> User:
    user = db_session.query(User).filter(User.username == username).first()
    if user is None:
        user = User(
            username=username,
            email=f"{username}@test.invalid",
            hashed_password=get_password_hash("push-test-123"),
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _register(
    client: TestClient,
    user: User,
    token: str,
    *,
    provider: str = "fcm",
    platform: str = "android",
    device_id: str | None = None,
    previous_token: str | None = None,
):
    payload: dict = {"provider": provider, "platform": platform, "token": token}
    if device_id is not None:
        payload["device_id"] = device_id
    if previous_token is not None:
        payload["previous_token"] = previous_token
    return client.post(
        "/api/v1/push/devices/register", json=payload, headers=_headers(user)
    )


def _row_by_token(db_session: Session, user_id: int, token: str) -> PushDevice | None:
    return (
        db_session.query(PushDevice)
        .filter(PushDevice.user_id == user_id, PushDevice.token == token)
        .one_or_none()
    )


# ---------------------------------------------------------------------------
# 1. two devices, one user
# ---------------------------------------------------------------------------


def test_two_devices_one_user(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_a")

    r_android = _register(client, user, ANDROID_TOKEN, device_id="dev-1")
    r_web = _register(
        client,
        user,
        WEB_TOKEN,
        provider="webpush",
        platform="web",
        device_id="dev-2",
    )
    assert r_android.status_code == 200
    assert r_web.status_code == 200

    listed = client.get("/api/v1/push/devices", headers=_headers(user))
    assert listed.status_code == 200
    body = listed.json()
    assert body["total_count"] == 2
    assert {d["provider"] for d in body["devices"]} == {"fcm", "webpush"}
    assert {d["platform"] for d in body["devices"]} == {"android", "web"}
    # credentials never leave the server; the fingerprint does
    for device in body["devices"]:
        assert "token" not in device
        assert device["token_fingerprint"]


# ---------------------------------------------------------------------------
# 2. two users — isolated registries
# ---------------------------------------------------------------------------


def test_two_users_isolated_registries(client: TestClient, db_session: Session):
    user_a = _get_or_create_user(db_session, "push_a")
    user_b = _get_or_create_user(db_session, "push_b")

    assert _register(client, user_a, ANDROID_TOKEN).status_code == 200
    assert _register(client, user_b, OTHER_TOKEN).status_code == 200

    list_a = client.get("/api/v1/push/devices", headers=_headers(user_a)).json()
    list_b = client.get("/api/v1/push/devices", headers=_headers(user_b)).json()

    assert list_a["total_count"] == 1
    assert list_b["total_count"] == 1
    assert (
        list_a["devices"][0]["token_fingerprint"]
        == registry.token_fingerprint(ANDROID_TOKEN)
    )
    assert (
        list_b["devices"][0]["token_fingerprint"]
        == registry.token_fingerprint(OTHER_TOKEN)
    )
    assert list_a["devices"][0]["id"] != list_b["devices"][0]["id"]


# ---------------------------------------------------------------------------
# 3. register idempotency
# ---------------------------------------------------------------------------


def test_register_idempotent(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_a")

    first = _register(client, user, ANDROID_TOKEN, device_id="dev-1")
    second = _register(client, user, ANDROID_TOKEN, device_id="dev-1")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    # re-register with a different device_id: the client statement wins
    third = _register(client, user, ANDROID_TOKEN, device_id="dev-1b")
    assert third.json()["id"] == first.json()["id"]
    assert third.json()["device_id"] == "dev-1b"

    body = client.get("/api/v1/push/devices", headers=_headers(user)).json()
    assert body["total_count"] == 1


# ---------------------------------------------------------------------------
# 4. token rotation (explicit previous_token)
# ---------------------------------------------------------------------------


def test_token_rotation(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_a")

    assert _register(client, user, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    rotated = _register(
        client, user, WEB_TOKEN, device_id="dev-1", previous_token=ANDROID_TOKEN
    )
    assert rotated.status_code == 200

    rows = registry.list_devices(db_session, user_id=user.id)
    assert len(rows) == 2
    old_row = _row_by_token(db_session, user.id, ANDROID_TOKEN)
    new_row = _row_by_token(db_session, user.id, WEB_TOKEN)
    assert old_row is not None and new_row is not None
    assert old_row.enabled is False
    assert old_row.invalidated_at is not None
    assert new_row.enabled is True
    assert new_row.invalidated_at is None


# ---------------------------------------------------------------------------
# 5. exact-token conditional invalidation (provider feedback path)
# ---------------------------------------------------------------------------


def test_exact_token_conditional_invalidation(client: TestClient, db_session: Session):
    user_a = _get_or_create_user(db_session, "push_a")
    user_b = _get_or_create_user(db_session, "push_b")
    assert _register(client, user_a, ANDROID_TOKEN).status_code == 200
    assert _register(client, user_a, WEB_TOKEN).status_code == 200
    assert _register(client, user_b, OTHER_TOKEN).status_code == 200

    invalidated = registry.invalidate_token(
        db_session, provider="fcm", token=ANDROID_TOKEN
    )
    assert invalidated == 1

    row_a1 = _row_by_token(db_session, user_a.id, ANDROID_TOKEN)
    row_a2 = _row_by_token(db_session, user_a.id, WEB_TOKEN)
    row_b = _row_by_token(db_session, user_b.id, OTHER_TOKEN)
    assert row_a1 is not None and row_a2 is not None and row_b is not None

    # ONLY the exact failed credential is retired
    assert row_a1.enabled is False
    assert row_a1.invalidated_at is not None
    assert row_a2.enabled is True and row_a2.invalidated_at is None
    assert row_b.enabled is True and row_b.invalidated_at is None

    # provider mismatch never invalidates: the credential is not the one
    # the provider reported dead
    assert (
        registry.invalidate_token(db_session, provider="webpush", token=WEB_TOKEN)
        == 0
    )
    db_session.refresh(row_a2)
    assert row_a2.enabled is True


# ---------------------------------------------------------------------------
# 6. single-device logout
# ---------------------------------------------------------------------------


def test_single_device_logout(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_a")
    assert _register(client, user, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    assert _register(client, user, WEB_TOKEN, device_id="dev-2").status_code == 200

    # logout device 1 by exact token
    out = client.post(
        "/api/v1/push/devices/unregister",
        json={"token": ANDROID_TOKEN},
        headers=_headers(user),
    )
    assert out.status_code == 200
    assert out.json()["disabled"] == 1

    row_1 = _row_by_token(db_session, user.id, ANDROID_TOKEN)
    row_2 = _row_by_token(db_session, user.id, WEB_TOKEN)
    assert row_1 is not None and row_2 is not None
    assert row_1.enabled is False
    # round 4b: logout RETIRES the row (releases its live-slot quota and
    # routes it into retention-bounded history)
    assert row_1.invalidated_at is not None
    assert row_2.enabled is True
    assert row_2.invalidated_at is None

    # logout device 2 by stable device_id
    out2 = client.post(
        "/api/v1/push/devices/unregister",
        json={"device_id": "dev-2"},
        headers=_headers(user),
    )
    assert out2.status_code == 200
    assert out2.json()["disabled"] == 1
    db_session.refresh(row_2)
    assert row_2.enabled is False
    assert row_2.invalidated_at is not None


def test_unregister_releases_quota_slot(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_quota_release")
    cap = registry.MAX_LIVE_DEVICES_PER_USER

    for i in range(cap):
        assert _register(client, user, f"pr6-release-credential-{i:02d}").status_code == 200
    assert _register(client, user, "pr6-release-credential-over").status_code == 409

    # The user retires one device through the public API...
    out = client.post(
        "/api/v1/push/devices/unregister",
        json={"token": "pr6-release-credential-00"},
        headers=_headers(user),
    )
    assert out.status_code == 200
    assert out.json()["disabled"] == 1

    # ...which frees a live slot: a new installation registers again.
    assert _register(client, user, "pr6-release-credential-after-logout").status_code == 200
    live = (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.invalidated_at.is_(None),
        )
        .count()
    )
    assert live == cap

    # A returning installation re-activates its own row — but only once a
    # live slot is free again (reactivation at the cap would push the
    # live count past the quota, so the cap holds even for own rows).
    assert _register(client, user, "pr6-release-credential-00").status_code == 409
    out2 = client.post(
        "/api/v1/push/devices/unregister",
        json={"token": "pr6-release-credential-01"},
        headers=_headers(user),
    )
    assert out2.status_code == 200 and out2.json()["disabled"] == 1
    assert _register(client, user, "pr6-release-credential-00").status_code == 200
    live = (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.invalidated_at.is_(None),
        )
        .count()
    )
    assert live == cap


def test_unregister_retires_disabled_rows_too(
    client: TestClient, db_session: Session
):
    user = _get_or_create_user(db_session, "push_toggle_off")
    cap = registry.MAX_LIVE_DEVICES_PER_USER

    for i in range(cap):
        assert _register(client, user, f"pr6-toggleoff-credential-{i:02d}").status_code == 200

    # toggle one device OFF: enabled=False, but NOT invalidated — the row
    # still holds a live-slot quota
    devices = client.get("/api/v1/push/devices", headers=_headers(user)).json()[
        "devices"
    ]
    target = devices[0]
    assert (
        client.post(
            f"/api/v1/push/devices/{target['id']}/toggle",
            json={"enabled": False},
            headers=_headers(user),
        ).status_code
        == 200
    )
    assert _register(client, user, "pr6-toggleoff-credential-over").status_code == 409

    # logout of the disabled device retires it and frees the slot —
    # without the fix this returned disabled: 0 and kept the slot
    out = client.post(
        "/api/v1/push/devices/unregister",
        json={"token": "pr6-toggleoff-credential-00"},
        headers=_headers(user),
    )
    assert out.status_code == 200
    assert out.json()["disabled"] == 1
    row = _row_by_token(db_session, user.id, "pr6-toggleoff-credential-00")
    assert row is not None
    assert row.enabled is False and row.invalidated_at is not None
    assert _register(client, user, "pr6-toggleoff-credential-after").status_code == 200


# ---------------------------------------------------------------------------
# 7. global opt-out: user-level master beats device-level switch
# ---------------------------------------------------------------------------


def test_global_opt_out_master_flag(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_a")
    # model default: user-level master is OFF (legacy semantics preserved)
    assert user.push_notifications_enabled is False

    assert _register(client, user, ANDROID_TOKEN).status_code == 200
    device_id = client.get("/api/v1/push/devices", headers=_headers(user)).json()[
        "devices"
    ][0]["id"]

    # master OFF wins even though the device is enabled
    assert registry.list_sendable_tokens(db_session, user_id=user.id) == []

    user.push_notifications_enabled = True
    db_session.commit()
    assert registry.list_sendable_tokens(db_session, user_id=user.id) == [
        ANDROID_TOKEN
    ]

    # device-level switch is independent of the master
    toggle = client.post(
        f"/api/v1/push/devices/{device_id}/toggle",
        json={"enabled": False},
        headers=_headers(user),
    )
    assert toggle.status_code == 200
    assert toggle.json()["enabled"] is False
    assert registry.list_sendable_tokens(db_session, user_id=user.id) == []

    toggle_back = client.post(
        f"/api/v1/push/devices/{device_id}/toggle",
        json={"enabled": True},
        headers=_headers(user),
    )
    assert toggle_back.status_code == 200
    assert registry.list_sendable_tokens(db_session, user_id=user.id) == [
        ANDROID_TOKEN
    ]


# ---------------------------------------------------------------------------
# 8. no cross-user deletion
# ---------------------------------------------------------------------------


def test_no_cross_user_deletion(client: TestClient, db_session: Session):
    user_a = _get_or_create_user(db_session, "push_a")
    user_b = _get_or_create_user(db_session, "push_b")
    assert _register(client, user_a, ANDROID_TOKEN, device_id="dev-a").status_code == 200
    assert _register(client, user_b, OTHER_TOKEN).status_code == 200

    # B tries to unregister A's credential: B owns no matching row
    out = client.post(
        "/api/v1/push/devices/unregister",
        json={"token": ANDROID_TOKEN},
        headers=_headers(user_b),
    )
    assert out.status_code == 200
    assert out.json()["disabled"] == 0

    row_a = _row_by_token(db_session, user_a.id, ANDROID_TOKEN)
    assert row_a is not None
    assert row_a.enabled is True and row_a.invalidated_at is None

    # B tries to toggle A's device row: 404, row untouched
    forbidden = client.post(
        f"/api/v1/push/devices/{row_a.id}/toggle",
        json={"enabled": False},
        headers=_headers(user_b),
    )
    assert forbidden.status_code == 404
    db_session.refresh(row_a)
    assert row_a.enabled is True


# ---------------------------------------------------------------------------
# 9. concurrent refresh/replace — unique-slot recovery + DB-level guard
# ---------------------------------------------------------------------------


def test_concurrent_refresh_and_replace(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_a")

    # (a) concurrent refresh of the same credential collapses into one row
    assert _register(client, user, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    again = _register(client, user, ANDROID_TOKEN, device_id="dev-1")
    assert again.status_code == 200
    assert (
        db_session.query(PushDevice).filter(PushDevice.user_id == user.id).count() == 1
    )

    # (b) concurrent/rotated replace: applying the same rotation twice is
    # safe — the old row is retired once, the new row stays single
    assert _register(
        client, user, WEB_TOKEN, device_id="dev-1", previous_token=ANDROID_TOKEN
    ).status_code == 200
    assert _register(
        client, user, WEB_TOKEN, device_id="dev-1", previous_token=ANDROID_TOKEN
    ).status_code == 200
    assert (
        db_session.query(PushDevice).filter(PushDevice.user_id == user.id).count() == 2
    )
    old_row = _row_by_token(db_session, user.id, ANDROID_TOKEN)
    assert old_row is not None
    assert old_row.enabled is False and old_row.invalidated_at is not None

    # (c) unique-slot recovery: a row that already occupies
    # (user_id, token) — the retired outcome of a rotation, i.e. what a
    # lost INSERT race leaves behind — is adopted and re-activated by
    # register, never duplicated.
    stale = _row_by_token(db_session, user.id, ANDROID_TOKEN)
    assert stale is not None
    assert stale.enabled is False and stale.invalidated_at is not None

    recovered = registry.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token=ANDROID_TOKEN,
        device_id="dev-1",
    )
    assert recovered.id == stale.id
    assert recovered.enabled is True
    assert recovered.invalidated_at is None
    assert (
        db_session.query(PushDevice).filter(PushDevice.user_id == user.id).count() == 2
    )

    # (d) the DB-level guard behind the recovery: a duplicate
    # (user_id, token_hash) INSERT is rejected by the constraint.
    duplicate = PushDevice(
        user_id=user.id,
        provider="fcm",
        platform="android",
        token=ANDROID_TOKEN,
        token_hash=registry.token_hash(ANDROID_TOKEN),
        token_fingerprint="dup",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    # (e) the digest-uniqueness contract: a credential far beyond any
    # B-tree-safe raw-TEXT size registers fine, because uniqueness is
    # keyed on the fixed-length token_hash, not on the raw TEXT.
    huge_token = "pr6-huge-" + "x" * 40000
    huge = _register(client, user, huge_token, device_id="dev-huge")
    assert huge.status_code == 200
    assert huge.json()["token_fingerprint"] == registry.token_fingerprint(huge_token)


# ---------------------------------------------------------------------------
# 9b. account switch — one credential, ONE active owner
# ---------------------------------------------------------------------------


def test_account_switch_retires_previous_owner(
    client: TestClient, db_session: Session
):
    user_a = _get_or_create_user(db_session, "push_a")
    user_b = _get_or_create_user(db_session, "push_b")

    # Shared installation: A registers the device credential first
    assert _register(client, user_a, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    user_a.push_notifications_enabled = True
    db_session.commit()
    assert registry.list_sendable_tokens(db_session, user_id=user_a.id) == [
        ANDROID_TOKEN
    ]

    # B signs in on the same installation and registers the SAME
    # physical credential: A must lose the delivery destination.
    switched = _register(client, user_b, ANDROID_TOKEN, device_id="dev-1")
    assert switched.status_code == 200

    row_a = _row_by_token(db_session, user_a.id, ANDROID_TOKEN)
    row_b = _row_by_token(db_session, user_b.id, ANDROID_TOKEN)
    assert row_a is not None and row_b is not None
    assert row_a.id != row_b.id
    assert row_a.enabled is False and row_a.invalidated_at is not None
    assert row_b.enabled is True and row_b.invalidated_at is None

    user_b.push_notifications_enabled = True
    db_session.commit()
    assert registry.list_sendable_tokens(db_session, user_id=user_a.id) == []
    assert registry.list_sendable_tokens(db_session, user_id=user_b.id) == [
        ANDROID_TOKEN
    ]

    # re-registration by B keeps the single-owner state (idempotent)
    assert _register(client, user_b, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    assert (
        db_session.query(PushDevice)
        .filter(
            PushDevice.token_hash == registry.token_hash(ANDROID_TOKEN),
            PushDevice.enabled.is_(True),
            PushDevice.invalidated_at.is_(None),
        )
        .count()
        == 1
    )

    # A registering a DIFFERENT credential is untouched by all of this
    assert _register(client, user_a, OTHER_TOKEN).status_code == 200
    row_a_other = _row_by_token(db_session, user_a.id, OTHER_TOKEN)
    assert row_a_other is not None
    assert row_a_other.enabled is True


# ---------------------------------------------------------------------------
# 10. legacy compatibility
# ---------------------------------------------------------------------------


def test_legacy_compatibility(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_a")
    user.device_token = "legacy-device-token-value"
    db_session.commit()
    db_session.refresh(user)

    # new registry surface writes ONLY push_devices
    assert _register(client, user, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    db_session.refresh(user)
    assert user.device_token == "legacy-device-token-value"

    # legacy /fcm endpoints keep working unchanged (current APK fleet)
    legacy = client.post(
        "/api/v1/fcm/register-token",
        json={"device_token": "legacy-device-token-2", "device_type": "android"},
        headers=_headers(user),
    )
    assert legacy.status_code == 200
    db_session.refresh(user)
    assert user.device_token == "legacy-device-token-2"

    # legacy writes do not create registry rows
    body = client.get("/api/v1/push/devices", headers=_headers(user)).json()
    assert body["total_count"] == 1
    assert body["devices"][0]["token_fingerprint"] == registry.token_fingerprint(
        ANDROID_TOKEN
    )

    # registry logout never touches the legacy column
    assert (
        client.post(
            "/api/v1/push/devices/unregister",
            json={"token": ANDROID_TOKEN},
            headers=_headers(user),
        ).status_code
        == 200
    )
    db_session.refresh(user)
    assert user.device_token == "legacy-device-token-2"

    # legacy unregister keeps clearing the legacy column (unchanged)
    legacy_out = client.delete("/api/v1/fcm/unregister-token", headers=_headers(user))
    assert legacy_out.status_code == 200
    db_session.refresh(user)
    assert user.device_token is None


# ---------------------------------------------------------------------------
# 11. credential hygiene: never in responses, never in logs
# ---------------------------------------------------------------------------


def test_credential_never_in_responses_or_logs(
    client: TestClient, db_session: Session, caplog: pytest.LogCaptureFixture
):
    user = _get_or_create_user(db_session, "push_a")

    with caplog.at_level(logging.DEBUG):
        registered = _register(client, user, ANDROID_TOKEN, device_id="dev-1")
        assert registered.status_code == 200
        listed = client.get("/api/v1/push/devices", headers=_headers(user))
        assert listed.status_code == 200
        assert (
            registry.invalidate_token(
                db_session, provider="fcm", token=ANDROID_TOKEN
            )
            == 1
        )

    # responses never carry the credential
    assert ANDROID_TOKEN not in json.dumps(registered.json())
    assert ANDROID_TOKEN not in json.dumps(listed.json())
    # ...but the fingerprint does, so support can still identify the device
    assert registry.token_fingerprint(ANDROID_TOKEN) in json.dumps(
        registered.json()
    )

    # logs never carry the credential
    assert ANDROID_TOKEN not in caplog.text
    assert registry.token_fingerprint(ANDROID_TOKEN) in caplog.text


# ---------------------------------------------------------------------------
# 9c. reverse transfer A -> B -> A (flush-order: retire BEFORE reactivating)
# ---------------------------------------------------------------------------


def test_reverse_transfer_abab_reactivates_first_owner(
    client: TestClient, db_session: Session
):
    user_a = _get_or_create_user(db_session, "push_a")
    user_b = _get_or_create_user(db_session, "push_b")

    # A -> B: A's row is retired, B becomes the single active owner
    assert _register(client, user_a, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    assert _register(client, user_b, ANDROID_TOKEN, device_id="dev-1").status_code == 200

    # B -> A: A's LOWER-id historical row is reactivated while B's
    # HIGHER-id row must be retired first — the retirement is flushed
    # before the reactivation, so the partial unique index never sees
    # two active owners mid-flush.
    back = _register(client, user_a, ANDROID_TOKEN, device_id="dev-1")
    assert back.status_code == 200

    row_a = _row_by_token(db_session, user_a.id, ANDROID_TOKEN)
    row_b = _row_by_token(db_session, user_b.id, ANDROID_TOKEN)
    assert row_a is not None and row_b is not None
    assert row_a.enabled is True and row_a.invalidated_at is None
    assert row_b.enabled is False and row_b.invalidated_at is not None
    assert (
        db_session.query(PushDevice)
        .filter(
            PushDevice.token_hash == registry.token_hash(ANDROID_TOKEN),
            PushDevice.enabled.is_(True),
            PushDevice.invalidated_at.is_(None),
        )
        .count()
        == 1
    )


# ---------------------------------------------------------------------------
# 9d. toggle cannot resurrect a credential lost to an account switch
# ---------------------------------------------------------------------------


def test_toggle_cannot_resurrect_transferred_credential(
    client: TestClient, db_session: Session
):
    user_a = _get_or_create_user(db_session, "push_a")
    user_b = _get_or_create_user(db_session, "push_b")
    user_a.push_notifications_enabled = True
    db_session.commit()

    # A registers, then logs out (row: enabled=False, invalidated NULL)
    assert _register(client, user_a, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    device_id = client.get("/api/v1/push/devices", headers=_headers(user_a)).json()[
        "devices"
    ][0]["id"]
    assert (
        client.post(
            "/api/v1/push/devices/unregister",
            json={"token": ANDROID_TOKEN},
            headers=_headers(user_a),
        ).status_code
        == 200
    )

    # B claims the same physical credential (A's disabled row must be
    # invalidated too — not just active rows) and later logs out as well
    assert _register(client, user_b, ANDROID_TOKEN, device_id="dev-1").status_code == 200
    row_a = _row_by_token(db_session, user_a.id, ANDROID_TOKEN)
    assert row_a is not None
    assert row_a.enabled is False and row_a.invalidated_at is not None
    assert (
        client.post(
            "/api/v1/push/devices/unregister",
            json={"token": ANDROID_TOKEN},
            headers=_headers(user_b),
        ).status_code
        == 200
    )

    # A toggles their stale row back on: it must NOT become sendable —
    # the credential was taken over by another account in between.
    toggled = client.post(
        f"/api/v1/push/devices/{device_id}/toggle",
        json={"enabled": True},
        headers=_headers(user_a),
    )
    assert toggled.status_code == 200
    db_session.refresh(row_a)
    assert row_a.invalidated_at is not None
    assert registry.list_sendable_tokens(db_session, user_id=user_a.id) == []
    assert registry.list_sendable_tokens(db_session, user_id=user_b.id) == []


# ---------------------------------------------------------------------------
# 9e. oversized credential: 422 must not echo the credential anywhere
# ---------------------------------------------------------------------------


def test_validation_error_does_not_leak_credential(
    client: TestClient, db_session: Session, caplog: pytest.LogCaptureFixture
):
    user = _get_or_create_user(db_session, "push_a")
    oversized = "pr6-oversized-" + "z" * 65537

    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/v1/push/devices/register",
            json={"provider": "fcm", "platform": "android", "token": oversized},
            headers=_headers(user),
        )

    assert response.status_code == 422
    # neither the 422 response nor the warning log may carry the credential
    assert oversized not in json.dumps(response.json())
    assert oversized not in caplog.text


# ---------------------------------------------------------------------------
# 12. per-user live-slot quota (codex round 4 P1): bounded registry growth
# ---------------------------------------------------------------------------


def test_quota_bounds_live_registry_slots(client: TestClient, db_session: Session):
    user = _get_or_create_user(db_session, "push_quota")
    cap = registry.MAX_LIVE_DEVICES_PER_USER

    # Fill the quota to the brim: distinct credentials, all live.
    for i in range(cap):
        response = _register(client, user, f"pr6-quota-credential-{i:02d}")
        assert response.status_code == 200

    # One beyond the cap: rejected, nothing stored.
    rejected = _register(client, user, "pr6-quota-credential-over-the-cap")
    assert rejected.status_code == 409
    assert (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.token == "pr6-quota-credential-over-the-cap",
        )
        .count()
        == 0
    )

    # Idempotent refresh of an EXISTING credential never trips the quota.
    assert _register(client, user, "pr6-quota-credential-00").status_code == 200

    # Explicit rotation frees the slot in the SAME transaction: the
    # rotated-away credential stops counting, the new one takes it.
    rotated = _register(
        client,
        user,
        "pr6-quota-credential-rotated-in",
        previous_token="pr6-quota-credential-00",
    )
    assert rotated.status_code == 200
    old_row = _row_by_token(db_session, user.id, "pr6-quota-credential-00")
    assert old_row is not None
    assert old_row.invalidated_at is not None

    # Invalidated history does not count: retire one live credential via
    # the provider-feedback path and the freed slot accepts a new one.
    assert (
        registry.invalidate_token(
            db_session, provider="fcm", token="pr6-quota-credential-01"
        )
        == 1
    )
    assert _register(client, user, "pr6-quota-credential-after-invalidation").status_code == 200


def test_quota_is_per_user(client: TestClient, db_session: Session):
    user_a = _get_or_create_user(db_session, "push_quota_a")
    user_b = _get_or_create_user(db_session, "push_quota_b")

    # A exhausts their own quota...
    for i in range(registry.MAX_LIVE_DEVICES_PER_USER):
        assert _register(client, user_a, f"pr6-quota-a-credential-{i:02d}").status_code == 200
    assert _register(client, user_a, "pr6-quota-a-credential-over").status_code == 409

    # ...which says nothing about B's registry.
    assert _register(client, user_b, OTHER_TOKEN).status_code == 200


# ---------------------------------------------------------------------------
# 13. blank credentials never become a registry identity
# (codex round 4 P2: whitespace-only token passed min_length=1, then the
# service stripped it to "" and persisted the SHA-256 of an empty string)
# ---------------------------------------------------------------------------


def test_blank_credentials_rejected_at_boundary(
    client: TestClient, db_session: Session
):
    user = _get_or_create_user(db_session, "push_blank")

    blank_payloads = [
        {"provider": "fcm", "platform": "android", "token": "   "},
        {"provider": "fcm", "platform": "android", "token": "\t\n"},
        {"provider": "fcm", "platform": "android", "token": "ok", "previous_token": "  "},
    ]
    for payload in blank_payloads:
        response = client.post(
            "/api/v1/push/devices/register", json=payload, headers=_headers(user)
        )
        assert response.status_code == 422, payload

    # refresh and unregister resolve credentials by hash — a whitespace
    # token must not silently resolve to (or create) a bogus row.
    assert (
        client.post(
            "/api/v1/push/devices/refresh",
            json={"token": "   "},
            headers=_headers(user),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/push/devices/unregister",
            json={"token": "   "},
            headers=_headers(user),
        ).status_code
        == 422
    )

    # nothing was stored under the empty-credential identity
    empty_hash = registry.token_hash("")
    assert (
        db_session.query(PushDevice)
        .filter(PushDevice.user_id == user.id, PushDevice.token_hash == empty_hash)
        .count()
        == 0
    )
    assert (
        db_session.query(PushDevice).filter(PushDevice.user_id == user.id).count() == 0
    )

    # service-level guard for direct (non-HTTP) callers
    with pytest.raises(ValueError):
        registry.register_device(
            db_session, user_id=user.id, provider="fcm", platform="android", token="  "
        )


def test_unregister_empty_body_matches_published_422_contract(
    client: TestClient, db_session: Session
):
    user = _get_or_create_user(db_session, "push_empty_body")

    response = client.post(
        "/api/v1/push/devices/unregister", json={}, headers=_headers(user)
    )
    assert response.status_code == 422
    body = response.json()
    # the wrapped envelope from the global RequestValidationError handler —
    # exactly the published PushDeviceValidationError schema (round 6 P2)
    assert body["error"] == "validation_error"
    assert isinstance(body["message"], str)
    assert isinstance(body["detail"], list)


def test_double_serialized_body_not_echoed_in_422(
    client: TestClient, db_session: Session
):
    # Round 9 (codex P2): a double-serialized registration object arrives
    # as a SHORT string input under loc=("body",) — the 422 must scrub it
    # even below the truncation bound, not echo the credential verbatim.
    user = _get_or_create_user(db_session, "push_double_serialized")
    inner = json.dumps(
        {"provider": "fcm", "platform": "android", "token": ANDROID_TOKEN}
    )

    response = client.post(
        "/api/v1/push/devices/register", json=inner, headers=_headers(user)
    )
    assert response.status_code == 422
    assert ANDROID_TOKEN not in json.dumps(response.json())


def test_form_encoded_body_not_echoed_in_422(
    client: TestClient, db_session: Session
):
    # Round 10 (codex P1): a non-JSON content type hands Pydantic the raw
    # body as BYTES — the byte-valued input must be decoded and scrubbed
    # before it reaches the 422 response or the warning log.
    user = _get_or_create_user(db_session, "push_form_body")

    response = client.post(
        "/api/v1/push/devices/register",
        content=f"token={ANDROID_TOKEN}&provider=fcm".encode(),
        headers={
            "Authorization": _headers(user)["Authorization"],
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert response.status_code == 422
    assert ANDROID_TOKEN not in json.dumps(response.json())


def test_percent_encoded_form_body_not_echoed_in_422(
    client: TestClient, db_session: Session
):
    # Round 11 (codex P1): percent-encoded field names ("%74oken") decode
    # to credential keys — the 422 must not echo the credential either.
    user = _get_or_create_user(db_session, "push_pct_body")

    response = client.post(
        "/api/v1/push/devices/register",
        content=f"%74oken={ANDROID_TOKEN}&provider=fcm".encode(),
        headers={
            "Authorization": _headers(user)["Authorization"],
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert response.status_code == 422
    assert ANDROID_TOKEN not in json.dumps(response.json())


def test_operational_error_keeps_sanitized_503_mapping(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    # Round 11 (codex P2): database-availability failures must stay
    # OperationalError (mapped by the global handler to retryable 503),
    # with a parameter-free message — not a credential-bearing 500.
    from sqlalchemy.exc import OperationalError as OperationalErrorExc

    user = _get_or_create_user(db_session, "push_op_fail")

    def broken_flush():
        raise OperationalErrorExc("connection dropped", None, None)

    monkeypatch.setattr(db_session, "flush", broken_flush)

    with pytest.raises(OperationalErrorExc) as exc_info:
        registry.register_device(
            db_session,
            user_id=user.id,
            provider="fcm",
            platform="android",
            token=ANDROID_TOKEN,
        )
    message = str(exc_info.value)
    assert "parameters hidden" in message
    assert ANDROID_TOKEN not in message
    assert "connection dropped" not in message


def test_unregister_schema_publishes_either_or_constraint():
    # Round 7-9 (codex P2): the at-least-one requirement is expressed as a
    # REAL union of two concrete request models — the OpenAPI requestBody
    # anyOf references concrete object schemas (no unconstrained base
    # member in the generated TypeScript).
    from app.main import app

    schema = app.openapi()
    request_body = schema["paths"]["/api/v1/push/devices/unregister"]["post"][
        "requestBody"
    ]["content"]["application/json"]["schema"]
    refs = sorted(
        alt["$ref"].rsplit("/", 1)[-1] for alt in request_body.get("anyOf", [])
    )
    assert refs == [
        "PushDeviceUnregisterByDeviceId",
        "PushDeviceUnregisterByToken",
    ]
    by_token = schema["components"]["schemas"]["PushDeviceUnregisterByToken"]
    assert "token" in by_token.get("required", [])
    by_device = schema["components"]["schemas"]["PushDeviceUnregisterByDeviceId"]
    assert "device_id" in by_device.get("required", [])


def test_surrounding_whitespace_is_stripped_consistently(
    client: TestClient, db_session: Session
):
    user = _get_or_create_user(db_session, "push_strip")

    response = _register(client, user, f"  {ANDROID_TOKEN}  ")
    assert response.status_code == 200
    # the stored identity is the STRIPPED credential — the same statement
    # as a plain-token registration (idempotent across the two forms)
    assert response.json()["token_fingerprint"] == registry.token_fingerprint(
        ANDROID_TOKEN
    )
    assert _register(client, user, ANDROID_TOKEN).status_code == 200
    assert (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.token_hash == registry.token_hash(ANDROID_TOKEN),
        )
        .count()
        == 1
    )


# ---------------------------------------------------------------------------
# 14. commit-time conflicts are covered by the bounded retry
# (codex round 4 P2: two users re-registering a credential whose rows are
# BOTH already invalidated conflict on the reactivation UPDATE, which
# surfaces on flush/commit — not on the insert flush)
# ---------------------------------------------------------------------------


def test_reactivation_commit_conflict_is_retried(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    user = _get_or_create_user(db_session, "push_retry")

    # Historical invalidated row for the credential (provider-dead earlier)
    assert _register(client, user, ANDROID_TOKEN).status_code == 200
    assert (
        registry.invalidate_token(db_session, provider="fcm", token=ANDROID_TOKEN)
        == 1
    )
    stale = _row_by_token(db_session, user.id, ANDROID_TOKEN)
    assert stale is not None and stale.invalidated_at is not None

    # Simulate the concurrent-reactivation conflict: the conflict is
    # raised while COMMITTING the reactivation (after the insert-flush
    # window the old retry loop covered).
    real_commit = db_session.commit
    commit_calls = {"n": 0}

    def flaky_commit():
        commit_calls["n"] += 1
        if commit_calls["n"] == 1:
            raise IntegrityError(
                "simulated concurrent reactivation conflict",
                params=None,
                orig=None,
            )
        return real_commit()

    monkeypatch.setattr(db_session, "commit", flaky_commit)

    result = registry.register_device(
        db_session,
        user_id=user.id,
        provider="fcm",
        platform="android",
        token=ANDROID_TOKEN,
    )

    assert commit_calls["n"] == 2  # first commit conflicted, retry committed
    assert result.invalidated_at is None
    assert result.enabled is True
    db_session.refresh(stale)
    assert stale.id == result.id


# ---------------------------------------------------------------------------
# 15. rotation history is retention-bounded (codex round 4b P1: the live
# quota alone cannot bound storage — rotating a fresh 64 KiB credential
# per request while naming the current token as previous_token keeps the
# live count at one while every request commits another historical row)
# ---------------------------------------------------------------------------


def test_rotation_history_is_retention_bounded(
    client: TestClient, db_session: Session
):
    user = _get_or_create_user(db_session, "push_history")
    cap_live = registry.MAX_LIVE_DEVICES_PER_USER
    cap_history = registry.MAX_INVALIDATED_ROWS_PER_USER

    current = "pr6-history-credential-0000"
    assert _register(client, user, current).status_code == 200

    # Hostile rotation loop: one live row, one NEW historical row per
    # request — far beyond the history bound.
    for i in range(cap_history + 5):
        new_token = f"pr6-history-credential-{i + 1:04d}"
        assert _register(
            client, user, new_token, previous_token=current
        ).status_code == 200
        current = new_token

    total = (
        db_session.query(PushDevice).filter(PushDevice.user_id == user.id).count()
    )
    assert total <= cap_live + cap_history

    live_rows = (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.invalidated_at.is_(None),
        )
        .count()
    )
    assert live_rows == 1

    history_rows = (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.invalidated_at.is_not(None),
        )
        .count()
    )
    assert history_rows == cap_history

    # the newest history row survived; the oldest ones were pruned
    assert (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.token == "pr6-history-credential-0000",
        )
        .count()
        == 0
    )
    assert (
        db_session.query(PushDevice)
        .filter(
            PushDevice.user_id == user.id,
            PushDevice.token == current,
        )
        .count()
        == 1
    )
