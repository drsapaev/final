"""
Pydantic схемы для управления табло
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ===================== ТАБЛО =====================


class DisplayBoardBase(BaseModel):
    name: str = Field(..., max_length=100, description="Уникальное имя табло")
    display_name: str = Field(..., max_length=150, description="Отображаемое имя")
    location: str | None = Field(None, max_length=200, description="Расположение")

    # Настройки отображения
    theme: str = Field("light", max_length=50, description="Тема: light, dark, custom")
    show_patient_names: str = Field("initials", description="full, initials, none")
    show_doctor_photos: bool = Field(True, description="Показывать фото врачей")
    queue_display_count: int = Field(
        5, ge=1, le=20, description="Количество номеров в очереди"
    )

    # Настройки контента
    show_announcements: bool = True
    show_banners: bool = True
    show_videos: bool = False

    # Настройки вызовов
    call_display_duration: int = Field(
        30, ge=5, le=300, description="Длительность показа вызова в секундах"
    )
    sound_enabled: bool = True
    voice_announcements: bool = False
    voice_language: str = Field("ru", max_length=5, description="Язык озвучки")
    volume_level: int = Field(70, ge=0, le=100, description="Уровень громкости")

    # Цветовая схема
    colors: dict[str, str] | None = Field(None, description="Настройки цветов")

    active: bool = True


class DisplayBoardCreate(DisplayBoardBase):
    pass


class DisplayBoardUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=150)
    location: str | None = Field(None, max_length=200)
    theme: str | None = Field(None, max_length=50)
    show_patient_names: str | None = None
    show_doctor_photos: bool | None = None
    queue_display_count: int | None = Field(None, ge=1, le=20)
    show_announcements: bool | None = None
    show_banners: bool | None = None
    show_videos: bool | None = None
    call_display_duration: int | None = Field(None, ge=5, le=300)
    sound_enabled: bool | None = None
    voice_announcements: bool | None = None
    voice_language: str | None = Field(None, max_length=5)
    volume_level: int | None = Field(None, ge=0, le=100)
    colors: dict[str, str] | None = None
    active: bool | None = None


class DisplayBoardOut(DisplayBoardBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    banners: list["DisplayBannerOut"] = []
    videos: list["DisplayVideoOut"] = []


# ===================== БАННЕРЫ =====================


class DisplayBannerBase(BaseModel):
    board_id: int
    title: str = Field(..., max_length=200)
    description: str | None = None
    image_url: str | None = Field(None, max_length=500)
    link_url: str | None = Field(None, max_length=500)

    display_order: int = Field(0, description="Порядок показа")
    display_duration: int = Field(
        10, ge=1, le=300, description="Длительность показа в секундах"
    )

    start_date: datetime | None = None
    end_date: datetime | None = None
    language: str = Field("ru", max_length=5)
    active: bool = True


class DisplayBannerCreate(DisplayBannerBase):
    pass


class DisplayBannerUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = None
    image_url: str | None = Field(None, max_length=500)
    link_url: str | None = Field(None, max_length=500)
    display_order: int | None = None
    display_duration: int | None = Field(None, ge=1, le=300)
    start_date: datetime | None = None
    end_date: datetime | None = None
    language: str | None = Field(None, max_length=5)
    active: bool | None = None


class DisplayBannerOut(DisplayBannerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None


# ===================== ВИДЕО =====================


class DisplayVideoBase(BaseModel):
    board_id: int
    title: str = Field(..., max_length=200)
    description: str | None = None
    video_url: str = Field(..., max_length=500)
    thumbnail_url: str | None = Field(None, max_length=500)

    duration_seconds: int | None = Field(None, ge=1)
    file_size_mb: float | None = Field(None, ge=0)
    video_format: str | None = Field(None, max_length=20)

    display_order: int = Field(0, description="Порядок воспроизведения")
    loop_count: int = Field(1, ge=0, description="Количество повторов, 0 = бесконечно")

    start_date: datetime | None = None
    end_date: datetime | None = None
    active: bool = True


class DisplayVideoCreate(DisplayVideoBase):
    pass


class DisplayVideoUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = None
    video_url: str | None = Field(None, max_length=500)
    thumbnail_url: str | None = Field(None, max_length=500)
    duration_seconds: int | None = Field(None, ge=1)
    file_size_mb: float | None = Field(None, ge=0)
    video_format: str | None = Field(None, max_length=20)
    display_order: int | None = None
    loop_count: int | None = Field(None, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    active: bool | None = None


class DisplayVideoOut(DisplayVideoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None


# ===================== ОБЪЯВЛЕНИЯ =====================


class DisplayAnnouncementBase(BaseModel):
    board_id: int | None = None  # None = для всех табло
    title: str = Field(..., max_length=200)
    message: str = Field(..., description="Текст объявления")
    announcement_type: str = Field("info", description="info, warning, urgent")

    priority: int = Field(0, description="Приоритет (чем выше, тем важнее)")
    scroll_speed: int = Field(50, ge=10, le=100, description="Скорость бегущей строки")

    start_date: datetime | None = None
    end_date: datetime | None = None
    language: str = Field("ru", max_length=5)
    active: bool = True


class DisplayAnnouncementCreate(DisplayAnnouncementBase):
    pass


class DisplayAnnouncementUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    message: str | None = None
    announcement_type: str | None = None
    priority: int | None = None
    scroll_speed: int | None = Field(None, ge=10, le=100)
    start_date: datetime | None = None
    end_date: datetime | None = None
    language: str | None = Field(None, max_length=5)
    active: bool | None = None


class DisplayAnnouncementOut(DisplayAnnouncementBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ===================== ТЕМЫ =====================


class DisplayThemeBase(BaseModel):
    name: str = Field(..., max_length=100, description="Уникальное имя темы")
    display_name: str = Field(..., max_length=150, description="Отображаемое имя")
    css_variables: dict[str, str] = Field(..., description="CSS переменные")
    font_family: str = Field("system-ui", max_length=100)
    font_sizes: dict[str, str] | None = None
    background_config: dict[str, Any] | None = None
    active: bool = True
    is_default: bool = False


class DisplayThemeCreate(DisplayThemeBase):
    pass


class DisplayThemeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=150)
    css_variables: dict[str, str] | None = None
    font_family: str | None = Field(None, max_length=100)
    font_sizes: dict[str, str] | None = None
    background_config: dict[str, Any] | None = None
    active: bool | None = None
    is_default: bool | None = None


class DisplayThemeOut(DisplayThemeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ===================== СОСТОЯНИЕ ТАБЛО =====================


class DisplayBoardState(BaseModel):
    """Текущее состояние табло для отображения"""

    board_id: int
    updated_at: datetime

    # Очереди по специалистам
    specialists: list[dict[str, Any]] = []

    # Текущие вызовы
    current_calls: list[dict[str, Any]] = []

    # Объявления
    announcements: list[dict[str, Any]] = []

    # Баннеры
    banners: list[dict[str, Any]] = []

    # Видео (если включены)
    videos: list[dict[str, Any]] = []


class DisplayTestRequest(BaseModel):
    """Запрос на тестирование табло"""

    board_id: int
    test_type: str = Field("call", description="call, announcement, banner")
    test_data: dict[str, Any] | None = None
