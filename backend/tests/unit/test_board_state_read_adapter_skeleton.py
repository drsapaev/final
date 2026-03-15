from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.models.setting import Setting
from app.services.board_state_read_adapter import BoardStateReadAdapter
from app.services.online_queue import get_or_create_day


def _upsert_setting(db_session, *, key: str, value: int) -> None:
    setting = (
        db_session.query(Setting)
        .filter(Setting.category == "queue", Setting.key == key)
        .first()
    )
    if setting is None:
        setting = Setting(category="queue", key=key, value=str(value))
        db_session.add(setting)
    else:
        setting.value = str(value)


def _seed_legacy_board_stats(
    db_session,
    *,
    department: str,
    date_str: str,
    start_number: int,
    is_open: bool,
    last_ticket: int,
    waiting: int,
    serving: int,
    done: int,
) -> None:
    get_or_create_day(
        db_session,
        department=department,
        date_str=date_str,
        start_number=start_number,
        open_flag=is_open,
    )
    for name, value in {
        "last_ticket": last_ticket,
        "waiting": waiting,
        "serving": serving,
        "done": done,
    }.items():
        queue_key = f"{department}::{date_str}::{name}"
        _upsert_setting(db_session, key=queue_key, value=value)
    db_session.commit()


@pytest.mark.unit
def test_board_state_read_adapter_builds_empty_skeleton_sections():
    adapter = BoardStateReadAdapter()

    payload = adapter.build_skeleton()

    assert payload.to_dict() == {
        "display_metadata": {
            "brand": None,
            "logo": None,
            "is_paused": None,
            "is_closed": None,
            "announcement": None,
            "announcement_ru": None,
            "announcement_uz": None,
            "announcement_en": None,
            "primary_color": None,
            "bg_color": None,
            "text_color": None,
            "contrast_default": None,
            "kiosk_default": None,
            "sound_default": None,
        },
        "queue_state": {
            "department": None,
            "date_str": None,
            "last_ticket": None,
            "waiting": None,
            "serving": None,
            "done": None,
        },
        "compatibility": {
            "is_open": None,
            "start_number": None,
        },
    }


@pytest.mark.unit
def test_board_state_read_adapter_separates_display_queue_and_compatibility_inputs():
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
        queue_state={
            "department": "reg",
            "date_str": "2026-03-10",
            "last_ticket": 17,
            "waiting": 5,
            "serving": 2,
            "done": 11,
        },
        compatibility_fields={
            "is_open": True,
            "start_number": 1,
        },
    )

    assert payload.display_metadata.brand == "Main Board"
    assert payload.display_metadata.sound_default is True
    assert payload.display_metadata.primary_color == "#0066cc"
    assert payload.queue_state.last_ticket == 17
    assert payload.queue_state.waiting == 5
    assert payload.compatibility.is_open is True
    assert payload.compatibility.start_number == 1


@pytest.mark.unit
def test_legacy_board_state_endpoint_contract_remains_unchanged(client, db_session):
    target_day = date.today()
    date_str = target_day.isoformat()
    _seed_legacy_board_stats(
        db_session,
        department="Reg",
        date_str=date_str,
        start_number=3,
        is_open=True,
        last_ticket=12,
        waiting=4,
        serving=2,
        done=6,
    )

    response = client.get(
        "/api/v1/board/state",
        params={"department": "Reg", "date": date_str},
    )

    assert response.status_code == 200
    assert response.json() == {
        "department": "Reg",
        "date_str": date_str,
        "is_open": True,
        "start_number": 3,
        "last_ticket": 12,
        "waiting": 4,
        "serving": 2,
        "done": 6,
    }
