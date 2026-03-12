from __future__ import annotations

from datetime import date

import pytest

from app.models.clinic import ClinicSettings
from app.models.display_config import DisplayAnnouncement, DisplayBoard
from app.models.setting import Setting
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


def _seed_display_board(db_session) -> DisplayBoard:
    board = DisplayBoard(
        name="main_board",
        display_name="Main Board",
        location="Floor 1",
        colors={
            "primary": "#0066cc",
            "background": "#ffffff",
            "text": "#222222",
        },
        sound_enabled=True,
        active=True,
    )
    db_session.add(board)
    db_session.commit()
    db_session.refresh(board)

    db_session.add_all(
        [
            DisplayAnnouncement(
                board_id=board.id,
                title="RU",
                message="Русское объявление",
                language="ru",
                priority=5,
                active=True,
            ),
            DisplayAnnouncement(
                board_id=board.id,
                title="UZ",
                message="O'zbekcha e'lon",
                language="uz",
                priority=3,
                active=True,
            ),
            DisplayAnnouncement(
                board_id=board.id,
                title="EN",
                message="English notice",
                language="en",
                priority=1,
                active=True,
            ),
        ]
    )
    db_session.commit()
    return board


def _upsert_display_board_setting(db_session, *, key: str, value: str) -> None:
    setting = (
        db_session.query(Setting)
        .filter(Setting.category == "display_board", Setting.key == key)
        .first()
    )
    if setting is None:
        setting = Setting(category="display_board", key=key, value=value)
        db_session.add(setting)
    else:
        setting.value = value


def _upsert_clinic_setting(db_session, *, key: str, value: str) -> None:
    setting = db_session.query(ClinicSettings).filter(ClinicSettings.key == key).first()
    if setting is None:
        setting = ClinicSettings(category="clinic", key=key, value=value)
        db_session.add(setting)
    else:
        setting.value = value


@pytest.mark.integration
def test_board_new_endpoint_is_mounted_and_returns_metadata_only_contract(client, db_session):
    _seed_display_board(db_session)
    _upsert_display_board_setting(
        db_session, key="logo", value="/static/uploads/display/main-logo.png"
    )
    _upsert_display_board_setting(db_session, key="contrast_default", value="true")
    _upsert_display_board_setting(db_session, key="kiosk_default", value="false")
    db_session.commit()

    response = client.get("/api/v1/display/boards/main_board/state")

    assert response.status_code == 200
    assert response.json() == {
        "board_key": "main_board",
        "display_metadata": {
            "brand": "Main Board",
            "logo": "/static/uploads/display/main-logo.png",
            "announcement": "Русское объявление",
            "announcement_ru": "Русское объявление",
            "announcement_uz": "O'zbekcha e'lon",
            "announcement_en": "English notice",
            "primary_color": "#0066cc",
            "bg_color": "#ffffff",
            "text_color": "#222222",
            "contrast_default": True,
            "kiosk_default": False,
            "sound_default": True,
        },
    }


@pytest.mark.integration
def test_board_new_endpoint_can_fallback_logo_to_clinic_setting(client, db_session):
    _seed_display_board(db_session)
    _upsert_clinic_setting(
        db_session, key="logo_url", value="/static/uploads/clinic/logo.png"
    )
    db_session.commit()

    response = client.get("/api/v1/display/boards/main_board/state")

    assert response.status_code == 200
    assert response.json()["display_metadata"]["logo"] == "/static/uploads/clinic/logo.png"


@pytest.mark.integration
def test_board_new_endpoint_openapi_registration_is_present(client):
    schema = client.get("/openapi.json").json()

    assert "/api/v1/display/boards/{board_key}/state" in schema["paths"]
    operation = schema["paths"]["/api/v1/display/boards/{board_key}/state"]["get"]
    assert operation["summary"] == "Board display state v1"


@pytest.mark.integration
def test_legacy_board_state_route_remains_unchanged(client, db_session):
    date_str = date.today().isoformat()
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
