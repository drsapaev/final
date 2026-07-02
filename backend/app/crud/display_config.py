"""
CRUD операции для системы табло
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.display_config import DisplayAnnouncement, DisplayBoard, DisplayTheme

DEFAULT_DISPLAY_BOARD_DATA: dict[str, Any] = {
    "name": "main_board",
    "display_name": "Главное табло",
    "location": "Зона ожидания, 1 этаж",
    "theme": "light",
    "show_patient_names": "initials",
    "show_doctor_photos": True,
    "queue_display_count": 5,
    "show_announcements": True,
    "show_banners": True,
    "show_videos": False,
    "call_display_duration": 30,
    "sound_enabled": True,
    "voice_announcements": False,
    "voice_language": "ru",
    "volume_level": 70,
    "colors": {
        "primary": "#0066cc",
        "secondary": "#f8f9fa",
        "text": "#333333",
        "background": "#ffffff",
    },
    "active": True,
}

DEFAULT_DISPLAY_THEMES: list[dict[str, Any]] = [
    {
        "name": "light",
        "display_name": "Светлая тема",
        "css_variables": {
            "--primary-color": "#0066cc",
            "--secondary-color": "#f8f9fa",
            "--text-color": "#333333",
            "--background-color": "#ffffff",
            "--border-color": "#dee2e6",
        },
        "font_family": "system-ui, sans-serif",
        "active": True,
        "is_default": True,
    },
    {
        "name": "dark",
        "display_name": "Темная тема",
        "css_variables": {
            "--primary-color": "#0d6efd",
            "--secondary-color": "#1a1a1a",
            "--text-color": "#ffffff",
            "--background-color": "#000000",
            "--border-color": "#333333",
        },
        "font_family": "system-ui, sans-serif",
        "active": True,
        "is_default": False,
    },
    {
        "name": "medical",
        "display_name": "Медицинская тема",
        "css_variables": {
            "--primary-color": "#28a745",
            "--secondary-color": "#e8f5e8",
            "--text-color": "#2c3e50",
            "--background-color": "#f8fff8",
            "--border-color": "#c3e6cb",
        },
        "font_family": "system-ui, sans-serif",
        "active": True,
        "is_default": False,
    },
]

# ===================== ТАБЛО =====================


def get_display_board(db: Session, board_id: int) -> DisplayBoard | None:
    """Получить табло по ID"""
    return db.query(DisplayBoard).filter(DisplayBoard.id == board_id).first()


def get_display_board_by_name(db: Session, name: str) -> DisplayBoard | None:
    """Получить табло по имени"""
    return db.query(DisplayBoard).filter(DisplayBoard.name == name).first()


def get_display_boards(
    db: Session, active_only: bool = True, skip: int = 0, limit: int = 100
) -> list[DisplayBoard]:
    """Получить список табло"""
    query = db.query(DisplayBoard)

    if active_only:
        query = query.filter(DisplayBoard.active == True)

    return query.offset(skip).limit(limit).all()


def create_display_board(db: Session, board_data: dict[str, Any]) -> DisplayBoard:
    """Создать табло"""
    board = DisplayBoard(**board_data)
    db.add(board)
    db.commit()
    db.refresh(board)
    return board


def update_display_board(
    db: Session, board_id: int, board_data: dict[str, Any]
) -> DisplayBoard | None:
    """Обновить табло"""
    board = get_display_board(db, board_id)
    if not board:
        return None

    for field, value in board_data.items():
        if hasattr(board, field):
            setattr(board, field, value)

    db.commit()
    db.refresh(board)
    return board


def ensure_default_display_config(db: Session) -> None:
    """Создать дефолтную конфигурацию табло, если таблицы пусты."""
    if get_display_board_by_name(db, DEFAULT_DISPLAY_BOARD_DATA["name"]) is None:
        create_display_board(db, DEFAULT_DISPLAY_BOARD_DATA)

    existing_theme_names = {
        theme.name for theme in db.query(DisplayTheme).all()
    }
    for theme_data in DEFAULT_DISPLAY_THEMES:
        if theme_data["name"] not in existing_theme_names:
            create_display_theme(db, theme_data)


# ===================== ТЕМЫ =====================


def get_display_themes(db: Session, active_only: bool = True) -> list[DisplayTheme]:
    """Получить темы табло"""
    query = db.query(DisplayTheme)

    if active_only:
        query = query.filter(DisplayTheme.active == True)

    return query.all()


def create_display_theme(db: Session, theme_data: dict[str, Any]) -> DisplayTheme:
    """Создать тему табло"""
    theme = DisplayTheme(**theme_data)
    db.add(theme)
    db.commit()
    db.refresh(theme)
    return theme


# ===================== КОНТЕНТ =====================
# Контент будет управляться через объявления и темы

# ===================== ОБЪЯВЛЕНИЯ =====================


def get_board_announcements(
    db: Session, board_id: int, active_only: bool = True
) -> list[DisplayAnnouncement]:
    """Получить объявления табло"""
    query = db.query(DisplayAnnouncement).filter(
        DisplayAnnouncement.board_id == board_id
    )

    if active_only:
        query = query.filter(DisplayAnnouncement.active == True)

    return query.order_by(
        DisplayAnnouncement.priority.desc(), DisplayAnnouncement.created_at.desc()
    ).all()


def create_board_announcement(
    db: Session, announcement_data: dict[str, Any]
) -> DisplayAnnouncement:
    """Создать объявление для табло"""
    announcement = DisplayAnnouncement(**announcement_data)
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement
