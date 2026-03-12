from __future__ import annotations

"""Public metadata-first board-display endpoint skeleton."""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.crud import clinic as crud_clinic
from app.crud import display_config as crud_display
from app.repositories.setting_api_repository import SettingApiRepository
from app.services.board_state_read_adapter import (
    BoardStateAdapterPayload,
    BoardStateReadAdapter,
)

router = APIRouter(prefix="/display/boards", tags=["board-display"])


class BoardDisplayMetadataV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand: str | None = None
    logo: str | None = None
    announcement: str | None = None
    announcement_ru: str | None = None
    announcement_uz: str | None = None
    announcement_en: str | None = None
    primary_color: str | None = None
    bg_color: str | None = None
    text_color: str | None = None
    contrast_default: bool | None = None
    kiosk_default: bool | None = None
    sound_default: bool | None = None


class BoardDisplayStateV1Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board_key: str
    display_metadata: BoardDisplayMetadataV1


def build_board_display_state_v1_response(
    *,
    board_key: str,
    payload: BoardStateAdapterPayload,
) -> BoardDisplayStateV1Response:
    metadata = payload.display_metadata
    return BoardDisplayStateV1Response(
        board_key=board_key,
        display_metadata=BoardDisplayMetadataV1(
            brand=metadata.brand,
            logo=metadata.logo,
            announcement=metadata.announcement,
            announcement_ru=metadata.announcement_ru,
            announcement_uz=metadata.announcement_uz,
            announcement_en=metadata.announcement_en,
            primary_color=metadata.primary_color,
            bg_color=metadata.bg_color,
            text_color=metadata.text_color,
            contrast_default=metadata.contrast_default,
            kiosk_default=metadata.kiosk_default,
            sound_default=metadata.sound_default,
        ),
    )


def load_board_display_settings(db: Session) -> dict[str, object]:
    settings = {
        setting.key: setting.value
        for setting in SettingApiRepository(db).list_by_category(category="display_board")
    }

    clinic_logo = crud_clinic.get_setting_by_key(db, "logo_url")
    if clinic_logo is not None and clinic_logo.value and "logo" not in settings:
        settings["logo_url"] = clinic_logo.value

    return settings


@router.get(
    "/{board_key}/state",
    response_model=BoardDisplayStateV1Response,
    summary="Board display state v1",
)
def get_board_display_state_v1(
    board_key: str = Path(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    display_board = crud_display.get_display_board_by_name(db, board_key)
    if display_board is None or not display_board.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Display board '{board_key}' not found",
        )

    announcements = crud_display.get_board_announcements(
        db, display_board.id, active_only=True
    )
    display_settings = load_board_display_settings(db)
    payload = BoardStateReadAdapter().assemble_candidate(
        display_board=display_board,
        display_announcements=announcements,
        display_settings=display_settings,
    )
    return build_board_display_state_v1_response(
        board_key=board_key,
        payload=payload,
    )
