from __future__ import annotations

from datetime import date

import pytest

from app.api.v1.endpoints import appointments as appointments_endpoints
from app.models.online import OnlineDay
from app.models.setting import Setting

pytestmark = pytest.mark.postgres_pilot


def _get_queue_setting(db_session, *, department: str, date_str: str, suffix: str) -> str | None:
    key = f"{department}::{date_str}::{suffix}"
    row = (
        db_session.query(Setting)
        .filter(Setting.category == "queue", Setting.key == key)
        .first()
    )
    return row.value if row else None


def _get_online_day(db_session, *, department: str, date_str: str) -> OnlineDay | None:
    return (
        db_session.query(OnlineDay)
        .filter(OnlineDay.department == department, OnlineDay.date_str == date_str)
        .first()
    )


@pytest.mark.integration
@pytest.mark.queue
def test_open_day_characterization_writes_settings_broadcasts_and_returns_requested_values(
    client,
    db_session,
    auth_headers,
    monkeypatch,
):
    department = "ENT"
    date_str = date.today().isoformat()
    captured: list[tuple[str, str, object]] = []

    def _fake_broadcast(dep: str, d: str, stats: object) -> None:
        captured.append((dep, d, stats))

    monkeypatch.setattr(appointments_endpoints, "_broadcast", _fake_broadcast)

    response = client.post(
        "/api/v1/appointments/open-day",
        params={
            "department": department,
            "date_str": date_str,
            "start_number": 25,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "start_number": 25,
        "is_open": True,
        "last_ticket": 0,
        "waiting": 0,
        "serving": 0,
        "done": 0,
    }

    assert _get_queue_setting(
        db_session, department=department, date_str=date_str, suffix="open"
    ) == "1"
    assert _get_queue_setting(
        db_session, department=department, date_str=date_str, suffix="start_number"
    ) == "25"

    day = _get_online_day(db_session, department=department, date_str=date_str)
    assert day is not None
    assert day.is_open is True
    # Characterization truth: response mirrors requested start_number,
    # but OnlineDay keeps its own default start_number when none existed.
    assert day.start_number == 1

    assert len(captured) == 1
    dep, d, stats = captured[0]
    assert dep == department
    assert d == date_str
    assert getattr(stats, "start_number") == 1
    assert getattr(stats, "is_open") is True
    assert getattr(stats, "last_ticket") == 0
    assert getattr(stats, "waiting") == 0
    assert getattr(stats, "serving") == 0
    assert getattr(stats, "done") == 0


@pytest.mark.integration
@pytest.mark.queue
def test_close_day_characterization_sets_onlineday_closed_without_broadcast(
    client,
    db_session,
    auth_headers,
    monkeypatch,
):
    department = "CARD"
    date_str = date.today().isoformat()

    day = OnlineDay(
        department=department,
        date_str=date_str,
        start_number=7,
        is_open=True,
    )
    db_session.add(day)
    db_session.add_all(
        [
            Setting(category="queue", key=f"{department}::{date_str}::last_ticket", value="11"),
            Setting(category="queue", key=f"{department}::{date_str}::waiting", value="4"),
            Setting(category="queue", key=f"{department}::{date_str}::serving", value="2"),
            Setting(category="queue", key=f"{department}::{date_str}::done", value="3"),
        ]
    )
    db_session.commit()

    called = {"count": 0}

    def _fake_broadcast(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        called["count"] += 1

    monkeypatch.setattr(appointments_endpoints, "_broadcast", _fake_broadcast)

    response = client.post(
        "/api/v1/appointments/close",
        params={"department": department, "date_str": date_str},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "is_open": False,
        "start_number": 7,
        "last_ticket": 11,
        "waiting": 4,
        "serving": 2,
        "done": 3,
    }

    db_session.refresh(day)
    assert day.is_open is False
    assert day.start_number == 7
    assert called["count"] == 0


@pytest.mark.integration
@pytest.mark.queue
def test_open_then_close_characterization_reveals_split_state_between_settings_and_onlineday(
    client,
    db_session,
    auth_headers,
    monkeypatch,
):
    department = "NEURO"
    date_str = date.today().isoformat()

    monkeypatch.setattr(appointments_endpoints, "_broadcast", lambda *args, **kwargs: None)

    open_response = client.post(
        "/api/v1/appointments/open-day",
        params={
            "department": department,
            "date_str": date_str,
            "start_number": 42,
        },
        headers=auth_headers,
    )
    close_response = client.post(
        "/api/v1/appointments/close",
        params={"department": department, "date_str": date_str},
        headers=auth_headers,
    )

    assert open_response.status_code == 200
    assert close_response.status_code == 200

    open_payload = open_response.json()
    close_payload = close_response.json()
    day = _get_online_day(db_session, department=department, date_str=date_str)

    assert day is not None
    assert open_payload["start_number"] == 42
    assert open_payload["is_open"] is True
    assert close_payload["start_number"] == 1
    assert close_payload["is_open"] is False

    assert _get_queue_setting(
        db_session, department=department, date_str=date_str, suffix="open"
    ) == "1"
    assert _get_queue_setting(
        db_session, department=department, date_str=date_str, suffix="start_number"
    ) == "42"

    assert day.start_number == 1
    assert day.is_open is False
