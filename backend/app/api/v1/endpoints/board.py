from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.display_config import DisplayBoard
from app.services.online_queue import load_stats

router = APIRouter(prefix="/board", tags=["board"])


@router.get("/state", summary="Состояние очереди для табло", response_model=dict[str, Any])
def board_state(
    department: str | None = Query(None, min_length=1, max_length=64),
    date: str = Query(..., description="YYYY-MM-DD"),
    board: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    """Return the legacy board stats snapshot plus board-scoped settings.

    The board state endpoint is intentionally public: it only exposes
    aggregate counters (``last_ticket``/``waiting``/``serving``/``done``)
    and non-PHI presentation settings. It must NOT leak live queue
    entries, current calls, or announcements — those are owned by the
    display board WebSocket initial_state/update stream, which is
    separately authenticated. Keeping this REST endpoint public lets the
    stats-only contract be verified without auth headers.

    DISPLAYCONFIG-FE-001 (audit PR #3961): the settings snapshot is
    board-scoped — an optional ``board`` name selects THAT board's row
    (a missing board is an honest 404) instead of always ``main_board``;
    the privacy setting of the selected board must not be replaced by
    the main board's.

    DISPLAYOPTIONS-FE-001 (audit PR #3961): the response additionally
    exposes the selected board's non-PHI presentation fields
    (``queue_display_count``/``show_announcements``/``voice_announcements``
    /``sound_enabled``) so the live TV screen can apply what the admin
    saved.

    DISPLAYDEPT-FE-001 (audit PR #3961): ``department`` is now optional —
    a public board route without a configured department (multi-
    department kiosk) suppresses the legacy counters honestly
    (``stats_available: false``) instead of inferring them from literal
    ``undefined`` URL text.
    """
    selected_board: DisplayBoard | None = None
    if board is not None:
        selected_board = (
            db.query(DisplayBoard).filter(DisplayBoard.name == board).first()
        )
        if not selected_board:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=404,
                detail=f"Табло {board} не найдено",
            )
    else:
        # RQ-24.a.1: sync the board privacy setting so the frontend can
        # gate patient names (rows + current call) exactly like the WS
        # channel. DisplayBoard keyed by `name` (no board_id column).
        selected_board = (
            db.query(DisplayBoard)
            .filter(DisplayBoard.name == "main_board")
            .first()
        )

    if department is None:
        # Multi-department board: honest suppression of the legacy
        # counters (they would be inferred from arbitrary URL text).
        return {
            "department": None,
            "show_patient_names": (
                selected_board.show_patient_names
                if selected_board
                else "initials"
            ),
            "date_str": date,
            "is_open": False,
            "start_number": 1,
            "last_ticket": 0,
            "waiting": 0,
            "serving": 0,
            "done": 0,
            "stats_available": False,
            "queue_display_count": (
                selected_board.queue_display_count
                if selected_board
                else 5
            ),
            "show_announcements": (
                selected_board.show_announcements
                if selected_board
                else True
            ),
            "voice_announcements": (
                selected_board.voice_announcements
                if selected_board
                else False
            ),
            "sound_enabled": (
                selected_board.sound_enabled if selected_board else True
            ),
        }

    s = load_stats(db, department=department, date_str=date)
    return {
        "department": s.department,
        "show_patient_names": (
            selected_board.show_patient_names
            if selected_board
            else "initials"
        ),
        "date_str": s.date_str,
        "is_open": s.is_open,
        "start_number": s.start_number,
        "last_ticket": s.last_ticket,
        "waiting": s.waiting,
        "serving": s.serving,
        "done": s.done,
        "stats_available": True,
        "queue_display_count": (
            selected_board.queue_display_count if selected_board else 5
        ),
        "show_announcements": (
            selected_board.show_announcements if selected_board else True
        ),
        "voice_announcements": (
            selected_board.voice_announcements if selected_board else False
        ),
        "sound_enabled": (
            selected_board.sound_enabled if selected_board else True
        ),
    }
