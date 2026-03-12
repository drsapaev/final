from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.board_display_state import (
    build_board_display_state_v1_response,
)
from app.services.board_state_read_adapter import BoardStateReadAdapter


@pytest.mark.unit
def test_board_new_endpoint_response_builder_exposes_only_v1_metadata_fields():
    adapter = BoardStateReadAdapter()
    payload = adapter.assemble_candidate(
        display_board=SimpleNamespace(
            name="main_board",
            display_name="Main Board",
            sound_enabled=True,
            colors={
                "primary": "#0066cc",
                "background": "#ffffff",
                "text": "#222222",
            },
        ),
        display_settings={
            "logo": "/static/uploads/display/main-logo.png",
            "contrast_default": "true",
            "kiosk_default": "false",
        },
        display_announcements=[
            SimpleNamespace(message="Русское объявление", language="ru", priority=5, active=True),
            SimpleNamespace(message="English notice", language="en", priority=1, active=True),
        ],
        queue_state={
            "department": "Reg",
            "date_str": "2026-03-10",
            "last_ticket": 17,
            "waiting": 4,
            "serving": 2,
            "done": 8,
        },
        compatibility_fields={"is_open": True, "start_number": 1},
    )

    response = build_board_display_state_v1_response(
        board_key="main_board",
        payload=payload,
    )

    assert response.model_dump() == {
        "board_key": "main_board",
        "display_metadata": {
            "brand": "Main Board",
            "logo": "/static/uploads/display/main-logo.png",
            "announcement": "Русское объявление",
            "announcement_ru": "Русское объявление",
            "announcement_uz": None,
            "announcement_en": "English notice",
            "primary_color": "#0066cc",
            "bg_color": "#ffffff",
            "text_color": "#222222",
            "contrast_default": True,
            "kiosk_default": False,
            "sound_default": True,
        },
    }


@pytest.mark.unit
def test_board_new_endpoint_response_builder_does_not_invent_unresolved_or_queue_fields():
    adapter = BoardStateReadAdapter()
    payload = adapter.build_skeleton()

    response = build_board_display_state_v1_response(
        board_key="main_board",
        payload=payload,
    )
    dumped = response.model_dump()

    assert set(dumped.keys()) == {"board_key", "display_metadata"}
    assert "queue_state" not in dumped
    assert "compatibility" not in dumped
    assert "is_paused" not in dumped["display_metadata"]
    assert "is_closed" not in dumped["display_metadata"]
    assert dumped["display_metadata"]["logo"] is None
    assert dumped["display_metadata"]["contrast_default"] is None
    assert dumped["display_metadata"]["kiosk_default"] is None
