from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
NOTIFICATIONS_ENDPOINTS_JS = ROOT / "frontend" / "src" / "api" / "endpoints.js"
NOTIFICATIONS_SERVICES_JS = ROOT / "frontend" / "src" / "api" / "services.js"
BACKEND_NOTIFICATIONS_PY = ROOT / "backend" / "app" / "api" / "v1" / "endpoints" / "notifications.py"


ROUTE_PATTERN = re.compile(r'@router\.(get|post|put|patch|delete)\("([^"]+)"')


@pytest.mark.unit
def test_backend_notifications_minimal_inbox_contract_surface() -> None:
    content = BACKEND_NOTIFICATIONS_PY.read_text(encoding="utf-8")
    routes = {(method.upper(), path) for method, path in ROUTE_PATTERN.findall(content)}

    assert ("GET", "/history") in routes
    assert ("POST", "/send") in routes


@pytest.mark.unit
def test_backend_notifications_does_not_expose_legacy_rest_paths() -> None:
    content = BACKEND_NOTIFICATIONS_PY.read_text(encoding="utf-8")
    assert '@router.get("/{id}")' not in content
    assert '@router.post("/{id}/read")' not in content
    assert '@router.post("/mark-all-read")' not in content
    assert '@router.get("/types")' not in content


@pytest.mark.unit
def test_frontend_notifications_endpoints_follow_backend_minimal_contract() -> None:
    content = NOTIFICATIONS_ENDPOINTS_JS.read_text(encoding="utf-8")

    assert "HISTORY: '/notifications/history'" in content
    assert "HISTORY_STATS: '/notifications/history/stats'" in content
    assert "SEND: '/notifications/send'" in content

    notifications_block = content.split('NOTIFICATIONS: {', 1)[1].split('},', 1)[0]

    assert "MARK_ALL_READ" not in notifications_block
    assert "MARK_READ" not in notifications_block
    assert "TYPES" not in notifications_block


@pytest.mark.unit
def test_frontend_notifications_service_uses_history_and_send_only() -> None:
    content = NOTIFICATIONS_SERVICES_JS.read_text(encoding="utf-8")

    assert "API_ENDPOINTS.NOTIFICATIONS.HISTORY" in content
    assert "API_ENDPOINTS.NOTIFICATIONS.SEND" in content
    assert "[FIX:NOTIFICATIONS]" in content
