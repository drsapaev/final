from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.board_state_read_adapter import BoardStateReadAdapter


@pytest.mark.unit
def test_board_state_display_wiring_reads_confirmed_display_board_fields():
    adapter = BoardStateReadAdapter()
    display_board = SimpleNamespace(
        name="main_board",
        display_name="Main Board",
        sound_enabled=True,
        colors={
            "primary": "#0066cc",
            "background": "#ffffff",
            "text": "#222222",
        },
    )

    payload = adapter.assemble_candidate(
        display_board=display_board,
        display_settings={
            "logo": "/static/uploads/display/main-logo.png",
            "contrast_default": "true",
            "kiosk_default": "false",
        },
    )

    assert payload.display_metadata.brand == "Main Board"
    assert payload.display_metadata.logo == "/static/uploads/display/main-logo.png"
    assert payload.display_metadata.primary_color == "#0066cc"
    assert payload.display_metadata.bg_color == "#ffffff"
    assert payload.display_metadata.text_color == "#222222"
    assert payload.display_metadata.contrast_default is True
    assert payload.display_metadata.kiosk_default is False
    assert payload.display_metadata.sound_default is True


@pytest.mark.unit
def test_board_state_display_wiring_flattens_announcements_and_keeps_unresolved_fields_empty():
    adapter = BoardStateReadAdapter()
    display_board = SimpleNamespace(
        name="main_board",
        display_name="Main Board",
        sound_enabled=False,
        colors={"primary": "#123456"},
    )
    display_announcements = [
        SimpleNamespace(message="English notice", language="en", priority=1, active=True),
        SimpleNamespace(message="Русское объявление", language="ru", priority=5, active=True),
        SimpleNamespace(message="O'zbekcha e'lon", language="uz", priority=3, active=True),
        SimpleNamespace(message="Inactive", language="ru", priority=99, active=False),
    ]

    payload = adapter.assemble_candidate(
        display_board=display_board,
        display_announcements=display_announcements,
    )

    assert payload.display_metadata.announcement == "Русское объявление"
    assert payload.display_metadata.announcement_ru == "Русское объявление"
    assert payload.display_metadata.announcement_uz == "O'zbekcha e'lon"
    assert payload.display_metadata.announcement_en == "English notice"
    assert payload.display_metadata.logo is None
    assert payload.display_metadata.is_paused is None
    assert payload.display_metadata.is_closed is None
    assert payload.display_metadata.contrast_default is None
    assert payload.display_metadata.kiosk_default is None


@pytest.mark.unit
def test_board_state_display_wiring_leaves_queue_state_untouched():
    adapter = BoardStateReadAdapter()
    display_board = SimpleNamespace(
        name="main_board",
        display_name="Main Board",
        sound_enabled=True,
        colors={},
    )

    payload = adapter.assemble_candidate(display_board=display_board)

    assert payload.queue_state.department is None
    assert payload.queue_state.last_ticket is None
    assert payload.queue_state.waiting is None
    assert payload.compatibility.is_open is None
    assert payload.compatibility.start_number is None
