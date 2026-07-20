from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
BACKEND_NOTIFICATIONS_PY = ROOT / "backend" / "app" / "api" / "v1" / "endpoints" / "notifications.py"
BACKEND_WS_PY = ROOT / "backend" / "app" / "api" / "v1" / "endpoints" / "notification_websocket.py"


def _src(path: str) -> Path:
    """Resolve a frontend source path, preferring .ts/.tsx over .js/.jsx.

    Frontend migrated .js -> .ts and .jsx -> .tsx (PR #2433 and predecessors).
    Tests must accept either extension to survive migration churn.
    """
    full = ROOT / path
    if full.exists():
        return full
    # Try the migrated extension
    if path.endswith(".jsx"):
        migrated = full.with_suffix(".tsx")
    elif path.endswith(".js"):
        migrated = full.with_suffix(".ts")
    else:
        migrated = full
    if migrated.exists():
        return migrated
    # Fall back to original (let the failure surface a clear FileNotFoundError)
    return full


FRONTEND_ENDPOINTS_JS = _src("frontend/src/api/endpoints.js")
FRONTEND_SERVICES_JS = _src("frontend/src/api/services.js")
FRONTEND_CENTER_JSX = _src("frontend/src/contexts/NotificationCenterContext.jsx")
FRONTEND_WS_JSX = _src("frontend/src/contexts/NotificationWebSocketContext.jsx")
FRONTEND_INBOX_JSX = _src("frontend/src/components/notifications/NotificationInbox.jsx")
FRONTEND_PROMPT_JSX = _src("frontend/src/components/chat/NotificationPrompt.jsx")
FRONTEND_ROLE_CENTER_JSX = _src("frontend/src/components/notifications/RoleNotificationCenter.jsx")
CARDIO_PANEL = _src("frontend/src/pages/CardiologistPanelUnified.jsx")
DENTIST_PANEL = _src("frontend/src/pages/DentistPanelUnified.jsx")
DERMA_PANEL = _src("frontend/src/pages/DermatologistPanelUnified.jsx")
LAB_PANEL = _src("frontend/src/pages/LabPanel.jsx")

ROUTE_PATTERN = re.compile(r'@router\.(get|post|put|patch|delete)\("([^"]+)"')


@pytest.mark.unit
def test_backend_notifications_surface_exposes_persistent_inbox_and_state_routes() -> None:
    content = BACKEND_NOTIFICATIONS_PY.read_text(encoding="utf-8")
    routes = {(method.upper(), path) for method, path in ROUTE_PATTERN.findall(content)}

    expected_routes = {
        ("GET", "/inbox"),
        ("GET", "/history"),
        ("GET", "/sync"),
        ("GET", "/unread-count"),
        ("GET", "/history/stats"),
        ("POST", "/{delivery_id}/seen"),
        ("POST", "/{delivery_id}/read"),
        ("POST", "/{delivery_id}/archive"),
        ("POST", "/mark-all-read"),
        ("POST", "/send"),
    }

    assert expected_routes.issubset(routes)


@pytest.mark.unit
def test_backend_websocket_surface_keeps_notification_sync_and_ack_envelopes() -> None:
    content = BACKEND_WS_PY.read_text(encoding="utf-8")

    for marker in [
        "connection_established",
        "notification_seen_ack",
        "notification_read_ack",
        "notification_archive_ack",
        "notification_mark_all_read_ack",
        "notification_sync_response",
    ]:
        assert marker in content


@pytest.mark.unit
def test_frontend_notifications_api_contract_matches_backend_surface() -> None:
    endpoints = FRONTEND_ENDPOINTS_JS.read_text(encoding="utf-8")
    services = FRONTEND_SERVICES_JS.read_text(encoding="utf-8")

    for marker in [
        "INBOX: '/notifications/inbox'",
        "HISTORY: '/notifications/history'",
        "SYNC: '/notifications/sync'",
        "UNREAD_COUNT: '/notifications/unread-count'",
        "MARK_ALL_READ: '/notifications/mark-all-read'",
        "HISTORY_STATS: '/notifications/history/stats'",
        "SEND: '/notifications/send'",
        "MARK_SEEN: (id) => `/notifications/${id}/seen`",
        "MARK_READ: (id) => `/notifications/${id}/read`",
        "ARCHIVE: (id) => `/notifications/${id}/archive`",
    ]:
        assert marker in endpoints

    for marker in [
        "getInbox(",
        "getSync(",
        "getUnreadCount(",
        "markSeen(",
        "markAsRead(",
        "archiveNotification(",
        "markAllAsRead(",
        "sendNotification(",
    ]:
        assert marker in services


@pytest.mark.unit
def test_frontend_notifications_context_and_inbox_use_canonical_delivery_model() -> None:
    center = FRONTEND_CENTER_JSX.read_text(encoding="utf-8")
    inbox = FRONTEND_INBOX_JSX.read_text(encoding="utf-8")
    ws = FRONTEND_WS_JSX.read_text(encoding="utf-8")
    role_center = FRONTEND_ROLE_CENTER_JSX.read_text(encoding="utf-8")

    for marker in [
        "queue_changed: 'queue_update'",
        "payment_success: 'payment_notification'",
        "loadNotifications",
        "markAllAsRead",
        "markAsSeen",
        "markAsRead",
        "archiveNotification",
        "getUnreadCount",
    ]:
        assert marker in center

    for marker in [
        "aria-label={t('misc.ni_otkryt_uvedomlenie_item_titl', { title: item.title })}",
        "all: 'unset'",
        "type=\"button\"",
    ]:
        assert marker in inbox

    for marker in [
        "queue_update",
        "notification_sync_response",
        "notification_seen_ack",
        "notification_read_ack",
        "notification_archive_ack",
        "notification_mark_all_read_ack",
    ]:
        assert marker in ws

    for marker in [
        "getProfile()",
        "recipient_id",
        "recipient_type",
    ]:
        assert marker in role_center


@pytest.mark.unit
def test_frontend_notifications_prompt_uses_safe_notification_checks() -> None:
    content = FRONTEND_PROMPT_JSX.read_text(encoding="utf-8")

    assert "typeof Notification !== 'undefined'" in content
    assert "notification-prompt-dismissed" in content
    assert "notify.warning(" in content


@pytest.mark.unit
def test_role_panels_delegate_notifications_to_global_center_without_direct_toasts() -> None:
    """After #2439, panels no longer import RoleNotificationCenter —
    GlobalNotificationCenter in App shell handles all panels."""
    page_files = [CARDIO_PANEL, DENTIST_PANEL, DERMA_PANEL, LAB_PANEL]

    for path in page_files:
        content = path.read_text(encoding="utf-8")
        assert "RoleNotificationCenter" not in content
        assert "react-toastify" not in content
