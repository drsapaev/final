"""Contract tests — board-scoped /board/state settings snapshot (audit #3961).

Findings covered:

- DISPLAYCONFIG-FE-001 (P2): the public board snapshot always selected
  ``main_board``'s privacy setting — a kiosk board configured ``full``/
  ``none`` had its frontend gate driven by ANOTHER board. ``?board=`` now
  selects that board's row (missing board → 404).
- DISPLAYOPTIONS-FE-001 (P2, backend half): the admin's saved
  ``queue_display_count``/``show_announcements``/``voice_announcements``
  /``sound_enabled`` are exposed so the live TV screen can apply them.
- DISPLAYDEPT-FE-001 (P2, backend half): a multi-department kiosk without
  a configured department gets an honest suppressed stats snapshot
  (``stats_available: false``) instead of counters inferred from literal
  ``undefined`` URL text.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.display_config import DisplayBoard
from app.models.setting import Setting


def _make_board(db: Session, name: str, **overrides) -> DisplayBoard:
    defaults = dict(
        name=name,
        display_name=f"Табло {name}",
        location="Синтетика",
        theme="light",
        show_patient_names="full",
        queue_display_count=12,
        sound_enabled=True,
        voice_announcements=True,
        show_announcements=False,
        active=True,
    )
    defaults.update(overrides)
    board = DisplayBoard(**defaults)
    db.add(board)
    db.flush()
    return board


def _seed_counters(db: Session, department: str, date_str: str) -> None:
    for key, value in {
        "last_ticket": "17",
        "waiting": "4",
        "serving": "2",
        "done": "1",
    }.items():
        db.add(
            Setting(
                category="queue",
                key=f"{department}::{date_str}::{key}",
                value=value,
            )
        )
    db.commit()


def test_board_param_returns_that_boards_settings(client, db_session):
    """?board=waiting_room_1 returns THAT board's privacy + presentation
    settings, not main_board's."""
    day = datetime.now(UTC).date().isoformat()
    _make_board(db_session, "waiting_room_1")
    _make_board(db_session, "main_board", show_patient_names="none")
    db_session.commit()

    response = client.get(
        "/api/v1/board/state",
        params={"department": "Reg", "date": day, "board": "waiting_room_1"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["show_patient_names"] == "full"
    assert payload["queue_display_count"] == 12
    assert payload["show_announcements"] is False
    assert payload["voice_announcements"] is True
    assert payload["sound_enabled"] is True
    assert payload["stats_available"] is True


def test_missing_board_name_404(client, db_session):
    """An unknown board name is an honest 404 — never a silent main_board
    fallback for an explicitly requested board."""
    day = datetime.now(UTC).date().isoformat()
    response = client.get(
        "/api/v1/board/state",
        params={"department": "Reg", "date": day, "board": "ghost_board"},
    )
    assert response.status_code == 404, response.text


def test_no_department_suppresses_stats_honestly(client, db_session):
    """Without a department the legacy counters are suppressed
    (stats_available: false, zeros) — never inferred from 'undefined'."""
    day = datetime.now(UTC).date().isoformat()
    _make_board(db_session, "waiting_room_1")
    db_session.commit()

    response = client.get(
        "/api/v1/board/state",
        params={"date": day, "board": "waiting_room_1"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["stats_available"] is False
    assert payload["last_ticket"] == 0
    assert payload["waiting"] == 0
    assert payload["show_patient_names"] == "full"
    assert payload["queue_display_count"] == 12


def test_department_payload_unchanged_with_new_keys(client, db_session):
    """Legacy department-scoped behavior keeps its counters; only additive
    settings keys appear (stats_available true)."""
    department = "Reg"
    date_str = "2026-05-23"
    _seed_counters(db_session, department, date_str)

    response = client.get(
        "/api/v1/board/state",
        params={"department": department, "date": date_str},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["department"] == department
    assert payload["last_ticket"] == 17
    assert payload["stats_available"] is True
    assert "queue_entries" not in payload
    assert "current_call" not in payload
    assert "announcements" not in payload
