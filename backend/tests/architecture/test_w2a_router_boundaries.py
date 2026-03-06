from __future__ import annotations

import re
from pathlib import Path


def test_messages_router_uses_service_router_import() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "messages.py"
    )
    text = endpoint_path.read_text(encoding="utf-8")
    assert "from app.services.messages_api_service import router" in text


def test_messages_router_has_no_direct_db_calls() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "messages.py"
    )
    text = endpoint_path.read_text(encoding="utf-8")
    forbidden = re.search(
        r"\bdb\.(query|add|commit|refresh|rollback|delete|execute|flush)\(",
        text,
    )
    assert forbidden is None

