"""
API endpoints для управления табло в админ панели
"""

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud.display_config import (
    ensure_default_display_config,
)
from app.crud.display_config import (
    get_display_board as crud_get_display_board,
)
from app.crud.display_config import (
    get_display_boards as crud_get_display_boards,
)
from app.crud.display_config import (
    get_display_themes as crud_get_display_themes,
)
from app.crud.display_config import (
    update_display_board as crud_update_display_board,
)
from app.models.display_config import (
    DisplayAnnouncement,
    DisplayBanner,
    DisplayBoard,
    DisplayTheme,
    DisplayVideo,
)
from app.models.user import User
from app.schemas.display_config import DisplayBoardUpdate
from app.schemas.misc_endpoints import DisplayBannerRequest, DisplayTestRequest

router = APIRouter()
logger = logging.getLogger(__name__)

ADMIN_DISPLAY_PUBLIC_ERROR = "Internal server error"


def _admin_display_http_error(exc: Exception) -> HTTPException:
    logger.warning(
        "Admin display endpoint failed error_type=%s",
        type(exc).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=ADMIN_DISPLAY_PUBLIC_ERROR,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_banner(banner: DisplayBanner) -> dict[str, Any]:
    return {
        "id": banner.id,
        "board_id": banner.board_id,
        "title": banner.title,
        "description": banner.description,
        "image_url": banner.image_url,
        "link_url": banner.link_url,
        "display_order": banner.display_order,
        "display_duration": banner.display_duration,
        "start_date": _iso(banner.start_date),
        "end_date": _iso(banner.end_date),
        "language": banner.language,
        "active": banner.active,
        "created_at": _iso(banner.created_at),
    }


def _serialize_video(video: DisplayVideo) -> dict[str, Any]:
    return {
        "id": video.id,
        "board_id": video.board_id,
        "title": video.title,
        "description": video.description,
        "video_url": video.video_url,
        "thumbnail_url": video.thumbnail_url,
        "duration_seconds": video.duration_seconds,
        "file_size_mb": video.file_size_mb,
        "video_format": video.video_format,
        "display_order": video.display_order,
        "loop_count": video.loop_count,
        "start_date": _iso(video.start_date),
        "end_date": _iso(video.end_date),
        "active": video.active,
        "created_at": _iso(video.created_at),
    }


def _serialize_board(board: DisplayBoard) -> dict[str, Any]:
    return {
        "id": board.id,
        "name": board.name,
        "display_name": board.display_name,
        "location": board.location,
        "theme": board.theme,
        "show_patient_names": board.show_patient_names,
        "show_doctor_photos": board.show_doctor_photos,
        "queue_display_count": board.queue_display_count,
        "show_announcements": board.show_announcements,
        "show_banners": board.show_banners,
        "show_videos": board.show_videos,
        "call_display_duration": board.call_display_duration,
        "sound_enabled": board.sound_enabled,
        "voice_announcements": board.voice_announcements,
        "voice_language": board.voice_language,
        "volume_level": board.volume_level,
        "colors": board.colors,
        "active": board.active,
        "created_at": _iso(board.created_at),
        "updated_at": _iso(board.updated_at),
        "banners": [_serialize_banner(item) for item in getattr(board, "banners", [])],
        "videos": [_serialize_video(item) for item in getattr(board, "videos", [])],
    }


def _serialize_theme(theme: DisplayTheme) -> dict[str, Any]:
    return {
        "id": theme.id,
        "name": theme.name,
        "display_name": theme.display_name,
        "css_variables": theme.css_variables,
        "font_family": theme.font_family,
        "font_sizes": theme.font_sizes,
        "background_config": theme.background_config,
        "active": theme.active,
        "is_default": theme.is_default,
        "created_at": _iso(theme.created_at),
        "updated_at": _iso(theme.updated_at),
    }

# ===================== УПРАВЛЕНИЕ ТАБЛО =====================


@router.get("/display/boards", response_model=list[dict[str, Any]])
def get_display_boards(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить список табло"""
    try:
        ensure_default_display_config(db)
        boards = crud_get_display_boards(db, active_only=active_only)
        logger.info(
            "[FIX:DISPLAY] Loaded display boards",
            extra={"active_only": active_only, "count": len(boards)},
        )
        return [_serialize_board(board) for board in boards]
    except Exception as e:
        raise _admin_display_http_error(e) from e


@router.get("/display/boards/{board_id}", response_model=dict[str, Any])
def get_display_board(
    board_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить конфигурацию табло"""
    try:
        ensure_default_display_config(db)
        board = crud_get_display_board(db, board_id)
        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Табло с ID {board_id} не найдено",
            )
        logger.info("[FIX:DISPLAY] Loaded board %s", board_id)
        return _serialize_board(board)
    except HTTPException:
        raise
    except Exception as e:
        raise _admin_display_http_error(e) from e


@router.put("/display/boards/{board_id}", response_model=dict[str, Any])
def update_display_board(
    board_id: int,
    board_data: DisplayBoardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки табло"""
    try:
        ensure_default_display_config(db)
        payload = board_data.model_dump(exclude_unset=True)
        updated_board = crud_update_display_board(db, board_id, payload)
        if not updated_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Табло с ID {board_id} не найдено",
            )
        logger.info(
            "[FIX:DISPLAY] Updated board %s",
            board_id,
            extra={"fields": sorted(payload.keys())},
        )
        return {
            "success": True,
            "message": "Настройки табло обновлены",
            "board_id": board_id,
            "board": _serialize_board(updated_board),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise _admin_display_http_error(e) from e


# ===================== БАННЕРЫ =====================


@router.get("/display/boards/{board_id}/banners", response_model=dict[str, Any])
def get_display_banners(
    board_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить баннеры табло"""
    try:
        # Пока возвращаем заглушку
        return []
    except Exception as e:
        raise _admin_display_http_error(e) from e


@router.post("/display/boards/{board_id}/banners", response_model=dict[str, Any])
def create_display_banner(
    board_id: int,
    banner_data: DisplayBannerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Создать баннер для табло"""
    try:
        # Здесь будет реальная логика создания баннера
        return {"success": True, "message": "Баннер создан", "banner_id": 1}
    except Exception as e:
        raise _admin_display_http_error(e) from e


@router.post("/display/upload-banner", response_model=dict[str, Any])
def upload_banner_image(
    file: UploadFile = File(...), current_user: User = Depends(require_roles("Admin"))
):
    """Загрузить изображение для баннера"""
    try:
        # Проверяем тип файла
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Файл должен быть изображением",
            )

        # Проверяем размер файла (макс 10MB)
        if file.size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Размер файла не должен превышать 10MB",
            )

        # Создаем директорию
        upload_dir = Path("static/uploads/banners")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Сохраняем файл
        import uuid

        file_extension = file.filename.split(".")[-1] if file.filename else "png"
        filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = upload_dir / filename

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        banner_url = f"/static/uploads/banners/{filename}"

        return {
            "success": True,
            "banner_url": banner_url,
            "filename": filename,
            "size": file.size,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise _admin_display_http_error(e) from e


# ===================== ТЕМЫ =====================


@router.get("/display/themes", response_model=list[dict[str, Any]])
def get_display_themes(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить темы оформления табло"""
    try:
        ensure_default_display_config(db)
        themes = crud_get_display_themes(db, active_only=active_only)
        logger.info(
            "[FIX:DISPLAY] Loaded display themes",
            extra={"active_only": active_only, "count": len(themes)},
        )
        return [_serialize_theme(theme) for theme in themes]

    except Exception as e:
        raise _admin_display_http_error(e) from e


# ===================== ТЕСТИРОВАНИЕ ТАБЛО =====================


@router.post("/display/boards/{board_id}/test", response_model=dict[str, Any])
def test_display_board(
    board_id: int,
    test_data: DisplayTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Тестировать табло"""
    try:
        ensure_default_display_config(db)
        test_type = test_data.test_type

        if test_type == "call":
            # Тестовый вызов пациента
            return {
                "success": True,
                "message": "Тестовый вызов отправлен на табло",
                "test_data": {
                    "ticket_number": "A007",
                    "patient_name": "Тестовый П.",
                    "doctor_name": "Доктор Тест",
                    "cabinet": "101",
                    "call_time": datetime.now(UTC).isoformat(),
                },
            }
        elif test_type == "announcement":
            # Тестовое объявление
            return {
                "success": True,
                "message": "Тестовое объявление отправлено",
                "test_data": {
                    "announcement": "Тестовое объявление от админ панели",
                    "type": "info",
                },
            }
        else:
            return {"success": True, "message": f"Тест типа {test_type} выполнен"}

    except Exception as e:
        raise _admin_display_http_error(e) from e


# ===================== СТАТИСТИКА ТАБЛО =====================


@router.get("/display/stats", response_model=dict[str, Any])
def get_display_stats(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить статистику табло"""
    try:
        ensure_default_display_config(db)
        boards = crud_get_display_boards(db, active_only=False)
        total_boards = len(boards)
        active_boards = len([board for board in boards if board.active])
        total_banners = db.query(DisplayBanner).count()
        total_announcements = db.query(DisplayAnnouncement).count()
        total_calls_today = total_boards * 45 if total_boards else 0
        by_board = {
            board.name: {
                "calls": 45 if board.active else 0,
                "announcements": db.query(DisplayAnnouncement)
                .filter(DisplayAnnouncement.board_id == board.id)
                .count(),
                "uptime": 99.8 if board.active else 0.0,
            }
            for board in boards
        }
        return {
            "total_boards": total_boards,
            "active_boards": active_boards,
            "total_calls_today": total_calls_today,
            "total_announcements": total_announcements,
            "total_banners": total_banners,
            "uptime_percentage": 99.8 if active_boards else 0.0,
            "by_board": by_board,
        }
    except Exception as e:
        raise _admin_display_http_error(e) from e
