"""
Модели для конфигурации табло и информационных экранов
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class DisplayBoard(Base):
    """Конфигурация информационных табло"""
    __tablename__ = "display_boards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # main_board, waiting_room_1
    display_name = Column(String(150), nullable=False)  # "Главное табло"
    location = Column(String(200), nullable=True)  # "Зона ожидания, 1 этаж"
    
    # Настройки отображения
    theme = Column(String(50), default="light", nullable=False)  # light, dark, custom
    show_patient_names = Column(String(20), default="initials", nullable=False)  # full, initials, none
    show_doctor_photos = Column(Boolean, default=True, nullable=False)
    queue_display_count = Column(Integer, default=5, nullable=False)  # Количество номеров в очереди
    
    # Настройки контента
    show_announcements = Column(Boolean, default=True, nullable=False)
    show_banners = Column(Boolean, default=True, nullable=False)
    show_videos = Column(Boolean, default=False, nullable=False)
    
    # Настройки вызовов
    call_display_duration = Column(Integer, default=30, nullable=False)  # Секунды показа вызова
    sound_enabled = Column(Boolean, default=True, nullable=False)
    voice_announcements = Column(Boolean, default=False, nullable=False)
    voice_language = Column(String(5), default="ru", nullable=False)
    volume_level = Column(Integer, default=70, nullable=False)  # 0-100
    
    # Цветовая схема
    colors = Column(JSON, nullable=True)  # {"primary": "#0066cc", "secondary": "#f8f9fa"}
    
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    banners = relationship("DisplayBanner", back_populates="board", cascade="all, delete-orphan")
    videos = relationship("DisplayVideo", back_populates="board", cascade="all, delete-orphan")


class DisplayBanner(Base):
    """Баннеры для табло"""
    __tablename__ = "display_banners"
    
    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    link_url = Column(String(500), nullable=True)
    
    # Настройки показа
    display_order = Column(Integer, default=0, nullable=False)
    display_duration = Column(Integer, default=10, nullable=False)  # Секунды
    
    # Планирование
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Языки
    language = Column(String(5), default="ru", nullable=False)
    
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    board = relationship("DisplayBoard", back_populates="banners")


class DisplayVideo(Base):
    """Видеоролики для табло"""
    __tablename__ = "display_videos"
    
    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    video_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    
    # Метаданные видео
    duration_seconds = Column(Integer, nullable=True)
    file_size_mb = Column(Float, nullable=True)
    video_format = Column(String(20), nullable=True)  # mp4, webm, avi
    
    # Настройки показа
    display_order = Column(Integer, default=0, nullable=False)
    loop_count = Column(Integer, default=1, nullable=False)  # 0 = бесконечно
    
    # Планирование
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    board = relationship("DisplayBoard", back_populates="videos")


class DisplayAnnouncement(Base):
    """Объявления для табло"""
    __tablename__ = "display_announcements"
    
    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=True)
    
    # Контент
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    announcement_type = Column(String(50), default="info", nullable=False)  # info, warning, urgent
    
    # Настройки отображения
    priority = Column(Integer, default=0, nullable=False)  # Чем выше, тем важнее
    scroll_speed = Column(Integer, default=50, nullable=False)  # Скорость бегущей строки
    
    # Планирование
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Языки
    language = Column(String(5), default="ru", nullable=False)
    
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DisplayTheme(Base):
    """Темы оформления табло"""
    __tablename__ = "display_themes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # light, dark, medical, modern
    display_name = Column(String(150), nullable=False)  # "Светлая тема"
    
    # CSS переменные темы
    css_variables = Column(JSON, nullable=False)  # {"--primary-color": "#0066cc"}
    
    # Настройки шрифтов
    font_family = Column(String(100), default="system-ui", nullable=False)
    font_sizes = Column(JSON, nullable=True)  # {"small": "14px", "medium": "18px", "large": "24px"}
    
    # Фоновые изображения/градиенты
    background_config = Column(JSON, nullable=True)
    
    active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
