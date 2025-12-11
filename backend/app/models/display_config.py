"""
Модели для конфигурации табло и информационных экранов
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class DisplayBoard(Base):
    """Конфигурация информационных табло"""

    __tablename__ = "display_boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # main_board, waiting_room_1
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)  # "Главное табло"
    location: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )  # "Зона ожидания, 1 этаж"

    # Настройки отображения
    theme: Mapped[str] = mapped_column(String(50), default="light", nullable=False)  # light, dark, custom
    show_patient_names: Mapped[str] = mapped_column(
        String(20), default="initials", nullable=False
    )  # full, initials, none
    show_doctor_photos: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    queue_display_count: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )  # Количество номеров в очереди

    # Настройки контента
    show_announcements: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_banners: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_videos: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Настройки вызовов
    call_display_duration: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )  # Секунды показа вызова
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    voice_announcements: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voice_language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)
    volume_level: Mapped[int] = mapped_column(Integer, default=70, nullable=False)  # 0-100

    # Цветовая схема
    colors: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON, nullable=True
    )  # {"primary": "#0066cc", "secondary": "#f8f9fa"}

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    banners: Mapped[List["DisplayBanner"]] = relationship(
        "DisplayBanner", back_populates="board", cascade="all, delete-orphan"
    )
    videos: Mapped[List["DisplayVideo"]] = relationship(
        "DisplayVideo", back_populates="board", cascade="all, delete-orphan"
    )


class DisplayBanner(Base):
    """Баннеры для табло"""

    __tablename__ = "display_banners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    board_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    link_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Настройки показа
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_duration: Mapped[int] = mapped_column(Integer, default=10, nullable=False)  # Секунды

    # Планирование
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Языки
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    board: Mapped["DisplayBoard"] = relationship("DisplayBoard", back_populates="banners")


class DisplayVideo(Base):
    """Видеоролики для табло"""

    __tablename__ = "display_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    board_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    video_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Метаданные видео
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_size_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    video_format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # mp4, webm, avi

    # Настройки показа
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    loop_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 0 = бесконечно

    # Планирование
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    board: Mapped["DisplayBoard"] = relationship("DisplayBoard", back_populates="videos")


class DisplayAnnouncement(Base):
    """Объявления для табло"""

    __tablename__ = "display_announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    board_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=True
    )

    # Контент
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    announcement_type: Mapped[str] = mapped_column(
        String(50), default="info", nullable=False
    )  # info, warning, urgent

    # Настройки отображения
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Чем выше, тем важнее
    scroll_speed: Mapped[int] = mapped_column(
        Integer, default=50, nullable=False
    )  # Скорость бегущей строки

    # Планирование
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Языки
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DisplayTheme(Base):
    """Темы оформления табло"""

    __tablename__ = "display_themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # light, dark, medical, modern
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)  # "Светлая тема"

    # CSS переменные темы
    css_variables: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )  # {"--primary-color": "#0066cc"}

    # Настройки шрифтов
    font_family: Mapped[str] = mapped_column(String(100), default="system-ui", nullable=False)
    font_sizes: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON, nullable=True
    )  # {"small": "14px", "medium": "18px", "large": "24px"}

    # Фоновые изображения/градиенты
    background_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
