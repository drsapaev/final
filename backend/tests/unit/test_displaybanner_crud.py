"""Contract tests — admin display banner CRUD (audit PR #3961).

Finding covered:

- DISPLAYBANNER-BE-001 (P2): ``GET /display/boards/{board_id}/banners``
  declared ``response_model=dict[str, Any]`` but unconditionally returned
  the LIST ``[]`` (FastAPI response-validation mismatch → 500 risk), and
  ``POST`` on the same route reported ``success: true, banner_id: 1`` for
  every request without inserting any ``DisplayBanner`` row.

Contract after the fix: GET returns a modeled dict envelope
(``{"banners": [...], "total": N}``) from real ``display_banners`` rows;
POST persists a real row with a unique id and a matching subsequent GET;
a missing board is an honest 404 on both routes; a banner without a
title is a 422, never a silent fake success.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin_display import (
    create_display_banner,
    get_display_banners,
)
from app.models.display_config import DisplayBanner, DisplayBoard
from app.models.user import User
from app.schemas.misc_endpoints import DisplayBannerRequest


def _make_user(db: Session, username: str) -> User:
    user = User(
        username=f"{username}_{datetime.now(UTC).timestamp()}",
        full_name=username.title(),
        hashed_password="x",
        role="Admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_board(db: Session, name: str) -> DisplayBoard:
    board = DisplayBoard(
        name=name,
        display_name=f"Табло {name}",
        location="Синтетика",
        theme="light",
        show_patient_names="full",
        queue_display_count=5,
        sound_enabled=True,
        voice_announcements=False,
        show_announcements=True,
        active=True,
    )
    db.add(board)
    db.flush()
    return board


# ---------------------------------------------------------------------------
# DISPLAYBANNER-BE-001 — honest GET / POST contracts
# ---------------------------------------------------------------------------


def test_get_banners_empty_board_returns_modeled_dict(db_session):
    """An Admin GET on a board without banners returns 200 with a modeled
    dict envelope — not a bare list, not a 500."""
    user = _make_user(db_session, "banner_admin_1")
    board = _make_board(db_session, "banner_board_1")

    result = get_display_banners(
        board_id=board.id, active_only=True, db=db_session, current_user=user
    )

    assert isinstance(result, dict)
    assert result["banners"] == []
    assert result["total"] == 0


def test_post_persists_real_unique_banner_and_get_matches(db_session):
    """POST inserts a real DisplayBanner row (unique id per request) and a
    subsequent GET returns it with the stored fields."""
    user = _make_user(db_session, "banner_admin_2")
    board = _make_board(db_session, "banner_board_2")

    first = create_display_banner(
        board_id=board.id,
        banner_data=DisplayBannerRequest(
            title="Синтетический баннер 1",
            description="Плановое сообщение",
            display_duration=15,
        ),
        db=db_session,
        current_user=user,
    )
    second = create_display_banner(
        board_id=board.id,
        banner_data=DisplayBannerRequest(title="Синтетический баннер 2"),
        db=db_session,
        current_user=user,
    )

    assert first["success"] is True
    assert second["success"] is True
    assert first["banner_id"] != second["banner_id"], "ids must be real and unique"
    assert first["banner_id"] != 1 or second["banner_id"] != 1

    row = db_session.get(DisplayBanner, first["banner_id"])
    assert row is not None
    assert row.board_id == board.id
    assert row.title == "Синтетический баннер 1"
    assert row.display_duration == 15

    listing = get_display_banners(
        board_id=board.id, active_only=True, db=db_session, current_user=user
    )
    assert listing["total"] == 2
    titles = [b["title"] for b in listing["banners"]]
    assert "Синтетический баннер 1" in titles
    assert "Синтетический баннер 2" in titles


def test_get_and_post_missing_board_404(db_session):
    """A missing board is an honest 404 on both routes."""
    user = _make_user(db_session, "banner_admin_3")

    with pytest.raises(HTTPException) as get_exc:
        get_display_banners(
            board_id=999999, active_only=True, db=db_session, current_user=user
        )
    assert get_exc.value.status_code == 404

    with pytest.raises(HTTPException) as post_exc:
        create_display_banner(
            board_id=999999,
            banner_data=DisplayBannerRequest(title="Синтетика"),
            db=db_session,
            current_user=user,
        )
    assert post_exc.value.status_code == 404


def test_post_without_title_422(db_session):
    """A banner body without a title is rejected — never a fake success."""
    user = _make_user(db_session, "banner_admin_4")
    board = _make_board(db_session, "banner_board_3")

    with pytest.raises(HTTPException) as exc:
        create_display_banner(
            board_id=board.id,
            banner_data=DisplayBannerRequest(description="Без заголовка"),
            db=db_session,
            current_user=user,
        )
    assert exc.value.status_code == 422

    rows = (
        db_session.query(DisplayBanner)
        .filter(DisplayBanner.board_id == board.id)
        .count()
    )
    assert rows == 0, "no phantom banner row may be created"
