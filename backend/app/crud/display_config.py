"""
CRUD операции для системы табло
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.display_config import DisplayAnnouncement, DisplayBoard, DisplayTheme

# ===================== ТАБЛО =====================


def get_display_board(db: Session, board_id: int) -> Optional[DisplayBoard]:
    """Получить табло по ID"""
    return db.query(DisplayBoard).filter(DisplayBoard.id == board_id).first()


def get_display_board_by_name(db: Session, name: str) -> Optional[DisplayBoard]:
    """Получить табло по имени"""
    return db.query(DisplayBoard).filter(DisplayBoard.name == name).first()


def get_display_boards(
    db: Session, active_only: bool = True, skip: int = 0, limit: int = 100
) -> List[DisplayBoard]:
    """Получить список табло"""
    query = db.query(DisplayBoard)

    if active_only:
        query = query.filter(DisplayBoard.active == True)

    return query.offset(skip).limit(limit).all()


def create_display_board(db: Session, board_data: Dict[str, Any]) -> DisplayBoard:
    """Создать табло"""
    board = DisplayBoard(**board_data)
    db.add(board)
    db.commit()
    db.refresh(board)
    return board


def update_display_board(
    db: Session, board_id: int, board_data: Dict[str, Any]
) -> Optional[DisplayBoard]:
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


# ===================== ТЕМЫ =====================


def get_display_themes(db: Session, active_only: bool = True) -> List[DisplayTheme]:
    """Получить темы табло"""
    query = db.query(DisplayTheme)

    if active_only:
        query = query.filter(DisplayTheme.active == True)

    return query.all()


def create_display_theme(db: Session, theme_data: Dict[str, Any]) -> DisplayTheme:
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
) -> List[DisplayAnnouncement]:
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
    db: Session, announcement_data: Dict[str, Any]
) -> DisplayAnnouncement:
    """Создать объявление для табло"""
    announcement = DisplayAnnouncement(**announcement_data)
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement
