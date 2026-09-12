"""PR-5 FCM contour hygiene tests.

Covers the corrected C-plan:
* topic endpoints removed from the public contract (they called FCMService
  methods that never existed and always returned HTTP 500);
* POST /fcm/send-notification regression: the route passes ``click_action``
  which previously was not accepted by FCMService.send_notification
  (TypeError -> unconditional HTTP 500);
* honest sender-level push: opt-out flag respected, delivery outcome recorded
  in the audit trail ("sent"/"failed"), UNREGISTERED (404/410) tokens dropped
  from the single-device registry (users.device_token);
* FCM_ENABLED participates in FCMService.active;
* OAuth token refresh happens off the event loop.
"""
from __future__ import annotations

import asyncio
import threading
from unittest.mock import AsyncMock

import pytest

from app.core.security import get_password_hash
from app.models.notification import NotificationHistory
from app.models.user import User
from app.services.fcm_service import FCMResponse, FCMService
from app.services.notifications import notification_sender_service

from datetime import datetime
from uuid import uuid4


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_user(db_session, *, role: str = "Patient") -> User:
    s = _suffix()
    user = User(
        username=f"fcm5_{role.lower()}_{s}",
        email=f"fcm5-{role.lower()}-{s}@test.local",
        full_name=f"FCM5 Test {role}",
        hashed_password=get_password_hash("pass123"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _admin_headers(client, user: User) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


class _StubFCMService(FCMService):
    """Real FCMService shape without Google credentials loading."""

    def __init__(self):  # noqa: D107 - intentionally skip _load_credentials
        self.project_id = "test-project"
        self.fcm_url = (
            "https://fcm.googleapis.com/v1/projects/test-project/messages:send"
        )
        self.credentials = object()
        self.access_token = "stub-access-token"
        self.token_expiry = 0
        self._send_semaphore = asyncio.Semaphore(10)

    @property
    def active(self) -> bool:  # noqa: D102
        return True


# ---------------------------------------------------------------------------
# Contract hygiene: topic endpoints removed
# ---------------------------------------------------------------------------


def test_topic_endpoints_removed_from_openapi_contract():
    """The three topic endpoints called non-existent service methods (always
    HTTP 500) and are unreachable by construction — they must not lie in the
    published OpenAPI contract anymore."""
    from app.main import app

    paths = app.openapi()["paths"]
    for removed in (
        "/api/v1/fcm/subscribe-topic",
        "/api/v1/fcm/unsubscribe-topic",
        "/api/v1/fcm/send-topic-notification",
    ):
        assert removed not in paths, f"{removed} must be removed from the contract"


def test_topic_endpoints_return_404(client, db_session):
    """Behavioral discriminator: the routes are gone (version-independent)."""
    admin = _make_user(db_session, role="Admin")
    headers = _admin_headers(client, admin)

    for method, path in (
        ("post", "/api/v1/fcm/subscribe-topic"),
        ("post", "/api/v1/fcm/unsubscribe-topic"),
        ("post", "/api/v1/fcm/send-topic-notification"),
    ):
        response = getattr(client, method)(
            path, headers=headers, json={"topic": "t", "device_tokens": ["x"]}
        )
        assert response.status_code == 404, (path, response.status_code)


# ---------------------------------------------------------------------------
# send-notification: click_action regression + honest counters
# ---------------------------------------------------------------------------


def _patch_route_service(monkeypatch, stub: _StubFCMService) -> None:
    from app.api.v1.endpoints import fcm_notifications as route_module

    monkeypatch.setattr(route_module, "get_fcm_service", lambda: stub)


def test_send_notification_accepts_click_action(client, db_session, monkeypatch):
    """Regression: route always forwarded click_action; the service signature
    did not accept it -> TypeError -> HTTP 500 on every single send."""
    stub = _StubFCMService()
    stub.send_notification = AsyncMock(
        return_value=FCMResponse(success=True, message_id="projects/p/messages/1")
    )
    _patch_route_service(monkeypatch, stub)

    admin = _make_user(db_session, role="Admin")
    headers = _admin_headers(client, admin)

    response = client.post(
        "/api/v1/fcm/send-notification",
        headers=headers,
        json={
            "title": "Broadcast",
            "body": "Hello",
            "device_tokens": ["tok-1"],
            "click_action": "OPEN_SCHEDULE",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["sent_count"] == 1

    stub.send_notification.assert_awaited_once()
    assert stub.send_notification.await_args.kwargs["click_action"] == "OPEN_SCHEDULE"


def test_send_notification_multicast_counters(client, db_session, monkeypatch):
    stub = _StubFCMService()
    stub.send_notification = AsyncMock(
        side_effect=[
            FCMResponse(success=True, message_id="m-1"),
            FCMResponse(success=False, error="Requested entity was not found", error_code="404"),
        ]
    )
    _patch_route_service(monkeypatch, stub)

    admin = _make_user(db_session, role="Admin")
    headers = _admin_headers(client, admin)

    response = client.post(
        "/api/v1/fcm/send-notification",
        headers=headers,
        json={
            "title": "Broadcast",
            "body": "Hello",
            "device_tokens": ["tok-ok", "tok-dead"],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sent_count"] == 1
    assert body["failed_count"] == 1
    assert body["total_count"] == 2


def test_send_notification_honest_400_when_disabled(client, db_session):
    """With FCM_ENABLED=false (default) the real service is inactive — the
    admin broadcast must fail honestly with 400, not pretend to send."""
    admin = _make_user(db_session, role="Admin")
    headers = _admin_headers(client, admin)

    response = client.post(
        "/api/v1/fcm/send-notification",
        headers=headers,
        json={"title": "t", "body": "b", "device_tokens": ["tok-1"]},
    )
    assert response.status_code == 400, response.text
    assert "не настроен" in response.json()["detail"]


def test_status_reflects_enabled_flag(client, db_session):
    admin = _make_user(db_session, role="Admin")
    headers = _admin_headers(client, admin)

    response = client.get("/api/v1/fcm/status", headers=headers)
    assert response.status_code == 200, response.text
    service_info = response.json()["fcm_service"]
    assert service_info["enabled"] is False  # default settings
    assert service_info["active"] is False


# ---------------------------------------------------------------------------
# register-token validation
# ---------------------------------------------------------------------------


def test_register_token_rejects_empty_token(client, db_session):
    user = _make_user(db_session)
    headers = _admin_headers(client, user)

    response = client.post(
        "/api/v1/fcm/register-token",
        headers=headers,
        json={"device_token": "", "device_type": "web"},
    )
    assert response.status_code == 422, response.text


def test_register_token_rejects_unknown_device_type(client, db_session):
    user = _make_user(db_session)
    headers = _admin_headers(client, user)

    response = client.post(
        "/api/v1/fcm/register-token",
        headers=headers,
        json={"device_token": "tok", "device_type": "toaster"},
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Sender-level honest push (facade)
# ---------------------------------------------------------------------------


def _mobile_history_rows(db_session, user_id: int) -> list[NotificationHistory]:
    return (
        db_session.query(NotificationHistory)
        .filter(
            NotificationHistory.recipient_id == user_id,
            NotificationHistory.channel == "mobile",
        )
        .all()
    )


@pytest.mark.asyncio
async def test_send_push_records_honest_sent_status(db_session, monkeypatch):
    user = _make_user(db_session)
    user.device_token = "tok-live"
    user.push_notifications_enabled = True
    db_session.commit()

    stub = _StubFCMService()
    stub.send_notification = AsyncMock(
        return_value=FCMResponse(success=True, message_id="m-ok")
    )
    monkeypatch.setattr(notification_sender_service, "fcm_service", stub)

    sent = await notification_sender_service.send_push(
        user_id=user.id,
        title="Queue",
        message="You are next",
        data={"type": "queue"},
        db=db_session,
    )
    assert sent is True
    stub.send_notification.assert_awaited_once()

    rows = _mobile_history_rows(db_session, user.id)
    assert len(rows) == 1
    assert rows[0].status == "sent"


@pytest.mark.asyncio
async def test_send_push_records_failed_status_and_drops_unregistered_token(
    db_session, monkeypatch
):
    user = _make_user(db_session)
    user.device_token = "tok-dead"
    user.device_type = "android"
    user.push_notifications_enabled = True
    db_session.commit()

    stub = _StubFCMService()
    stub.send_notification = AsyncMock(
        return_value=FCMResponse(
            success=False, error="Requested entity was not found", error_code="410"
        )
    )
    monkeypatch.setattr(notification_sender_service, "fcm_service", stub)

    sent = await notification_sender_service.send_push(
        user_id=user.id,
        title="Queue",
        message="You are next",
        db=db_session,
    )
    assert sent is True  # WS/platform path still succeeded

    db_session.expire_all()
    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token is None  # UNREGISTERED cleanup
    assert refreshed.push_notifications_enabled is False

    rows = _mobile_history_rows(db_session, user.id)
    assert len(rows) == 1
    assert rows[0].status == "failed"


@pytest.mark.asyncio
async def test_transient_404_does_not_purge_token(db_session, monkeypatch):
    """Codex round 1: error_code carries the generic HTTP status — a bare 404
    (proxy hiccup, wrong fcm_url) must NOT wipe the user's token."""
    user = _make_user(db_session)
    user.device_token = "tok-alive"
    user.device_type = "android"
    user.push_notifications_enabled = True
    db_session.commit()

    stub = _StubFCMService()
    stub.send_notification = AsyncMock(
        return_value=FCMResponse(
            success=False, error="Route not found", error_code="404"
        )
    )
    monkeypatch.setattr(notification_sender_service, "fcm_service", stub)

    await notification_sender_service.send_push(
        user_id=user.id,
        title="Queue",
        message="You are next",
        db=db_session,
    )

    db_session.expire_all()
    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.device_token == "tok-alive"  # token survives
    assert refreshed.push_notifications_enabled is True

    rows = _mobile_history_rows(db_session, user.id)
    assert len(rows) == 1
    assert rows[0].status == "failed"  # honest failure is still recorded


def test_unregistered_predicate_matrix():
    from app.services.fcm_service import is_unregistered_token_response as pred

    # Canonical v1 UNREGISTERED verdicts (410 status / 404 not-found message).
    assert pred(FCMResponse(success=False, error="Token is UNREGISTERED", error_code="410"))
    assert pred(
        FCMResponse(
            success=False,
            error="Requested entity was not found.",
            error_code="404",
        )
    )
    # Generic HTTP failures that look similar but must not purge.
    assert not pred(FCMResponse(success=False, error="Route not found", error_code="404"))
    assert not pred(FCMResponse(success=False, error="Requested entity was not found", error_code="429"))
    assert not pred(FCMResponse(success=False, error=None, error_code="404"))
    assert not pred(FCMResponse(success=True, message_id="m-1"))


@pytest.mark.asyncio
async def test_send_push_respects_opt_out_flag(db_session, monkeypatch):
    user = _make_user(db_session)
    user.device_token = "tok-opted-out"
    user.push_notifications_enabled = False
    db_session.commit()

    stub = _StubFCMService()
    stub.send_notification = AsyncMock(
        return_value=FCMResponse(success=True, message_id="m-2")
    )
    monkeypatch.setattr(notification_sender_service, "fcm_service", stub)

    sent = await notification_sender_service.send_push(
        user_id=user.id,
        title="Promo",
        message="Check this",
        db=db_session,
    )
    assert sent is True
    stub.send_notification.assert_not_awaited()

    # The mobile channel was never attempted — no mobile audit row.
    assert _mobile_history_rows(db_session, user.id) == []


@pytest.mark.asyncio
async def test_send_push_skips_when_service_inactive(db_session, monkeypatch):
    user = _make_user(db_session)
    user.device_token = "tok-live"
    user.push_notifications_enabled = True
    db_session.commit()

    class _InactiveFCMService(_StubFCMService):
        @property
        def active(self) -> bool:  # noqa: D102
            return False

    inactive = _InactiveFCMService()
    inactive.send_notification = AsyncMock(
        return_value=FCMResponse(success=True, message_id="m-3")
    )
    monkeypatch.setattr(notification_sender_service, "fcm_service", inactive)

    sent = await notification_sender_service.send_push(
        user_id=user.id,
        title="Queue",
        message="You are next",
        db=db_session,
    )
    assert sent is True
    inactive.send_notification.assert_not_awaited()
    assert _mobile_history_rows(db_session, user.id) == []


# ---------------------------------------------------------------------------
# fcm_service unit: off-loop refresh + honest error handling
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse, **_kwargs):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        return self._response


class _StubCredentials:
    def __init__(self):
        self.token = "refreshed-token"
        self.refresh_thread_ident: int | None = None

    def refresh(self, request):
        self.refresh_thread_ident = threading.get_ident()


def _fresh_service(monkeypatch, *, enabled: bool) -> tuple[FCMService, _StubCredentials]:
    from app.services import fcm_service as fcm_module

    monkeypatch.setattr(fcm_module.settings, "FCM_ENABLED", enabled)
    credentials = _StubCredentials()
    service = FCMService.__new__(FCMService)
    service.project_id = "test-project"
    service.fcm_url = (
        "https://fcm.googleapis.com/v1/projects/test-project/messages:send"
    )
    service.credentials = credentials
    service.access_token = None
    service.token_expiry = 0
    service._send_semaphore = asyncio.Semaphore(10)
    return service, credentials


@pytest.mark.asyncio
async def test_send_notification_refreshes_token_off_event_loop(monkeypatch):
    service, credentials = _fresh_service(monkeypatch, enabled=True)
    monkeypatch.setattr(
        "app.services.fcm_service.httpx.AsyncClient",
        lambda **kw: _FakeClient(_FakeResponse(200, {"name": "projects/p/messages/ok"})),
    )

    main_ident = threading.get_ident()
    result = await service.send_notification(
        device_token="tok", title="t", body="b"
    )

    assert result.success is True
    assert result.message_id == "projects/p/messages/ok"
    assert credentials.refresh_thread_ident is not None
    assert credentials.refresh_thread_ident != main_ident


@pytest.mark.asyncio
async def test_send_notification_survives_non_json_error_body(monkeypatch):
    service, _credentials = _fresh_service(monkeypatch, enabled=True)
    monkeypatch.setattr(
        "app.services.fcm_service.httpx.AsyncClient",
        lambda **kw: _FakeClient(_FakeResponse(502, None)),
    )

    result = await service.send_notification(
        device_token="tok", title="t", body="b"
    )

    assert result.success is False
    assert result.error_code == "502"
    assert result.error  # human-readable fallback present


@pytest.mark.asyncio
async def test_send_notification_inactive_returns_failure(monkeypatch):
    service, _credentials = _fresh_service(monkeypatch, enabled=False)

    result = await service.send_notification(
        device_token="tok", title="t", body="b"
    )
    assert result.success is False
    assert "not configured" in result.error


def test_get_status_includes_enabled_flag(monkeypatch):
    service, _credentials = _fresh_service(monkeypatch, enabled=True)
    status_info = service.get_status()
    assert status_info["enabled"] is True
    assert status_info["active"] is True  # credentials + project + enabled
    assert status_info["credentials_loaded"] is True
