"""
Pydantic схемы для управления табло
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ===================== ТАБЛО =====================

class DisplayBoardBase(BaseModel):
    name: str = Field(..., max_length=100, description="Уникальное имя табло")
    display_name: str = Field(..., max_length=150, description="Отображаемое имя")
    location: Optional[str] = Field(None, max_length=200, description="Расположение")
    
    # Настройки отображения
    theme: str = Field("light", max_length=50, description="Тема: light, dark, custom")
    show_patient_names: str = Field("initials", description="full, initials, none")
    show_doctor_photos: bool = Field(True, description="Показывать фото врачей")
    queue_display_count: int = Field(5, ge=1, le=20, description="Количество номеров в очереди")
    
    # Настройки контента
    show_announcements: bool = True
    show_banners: bool = True
    show_videos: bool = False
    
    # Настройки вызовов
    call_display_duration: int = Field(30, ge=5, le=300, description="Длительность показа вызова в секундах")
    sound_enabled: bool = True
    voice_announcements: bool = False
    voice_language: str = Field("ru", max_length=5, description="Язык озвучки")
    volume_level: int = Field(70, ge=0, le=100, description="Уровень громкости")
    
    # Цветовая схема
    colors: Optional[Dict[str, str]] = Field(None, description="Настройки цветов")
    
    active: bool = True


class DisplayBoardCreate(DisplayBoardBase):
    pass


class DisplayBoardUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=150)
    location: Optional[str] = Field(None, max_length=200)
    theme: Optional[str] = Field(None, max_length=50)
    show_patient_names: Optional[str] = None
    show_doctor_photos: Optional[bool] = None
    queue_display_count: Optional[int] = Field(None, ge=1, le=20)
    show_announcements: Optional[bool] = None
    show_banners: Optional[bool] = None
    show_videos: Optional[bool] = None
    call_display_duration: Optional[int] = Field(None, ge=5, le=300)
    sound_enabled: Optional[bool] = None
    voice_announcements: Optional[bool] = None
    voice_language: Optional[str] = Field(None, max_length=5)
    volume_level: Optional[int] = Field(None, ge=0, le=100)
    colors: Optional[Dict[str, str]] = None
    active: Optional[bool] = None


class DisplayBoardOut(DisplayBoardBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    banners: List["DisplayBannerOut"] = []
    videos: List["DisplayVideoOut"] = []


# ===================== БАННЕРЫ =====================

class DisplayBannerBase(BaseModel):
    board_id: int
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    link_url: Optional[str] = Field(None, max_length=500)
    
    display_order: int = Field(0, description="Порядок показа")
    display_duration: int = Field(10, ge=1, le=300, description="Длительность показа в секундах")
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    language: str = Field("ru", max_length=5)
    active: bool = True


class DisplayBannerCreate(DisplayBannerBase):
    pass


class DisplayBannerUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    link_url: Optional[str] = Field(None, max_length=500)
    display_order: Optional[int] = None
    display_duration: Optional[int] = Field(None, ge=1, le=300)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    language: Optional[str] = Field(None, max_length=5)
    active: Optional[bool] = None


class DisplayBannerOut(DisplayBannerBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None


# ===================== ВИДЕО =====================

class DisplayVideoBase(BaseModel):
    board_id: int
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    video_url: str = Field(..., max_length=500)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    
    duration_seconds: Optional[int] = Field(None, ge=1)
    file_size_mb: Optional[float] = Field(None, ge=0)
    video_format: Optional[str] = Field(None, max_length=20)
    
    display_order: int = Field(0, description="Порядок воспроизведения")
    loop_count: int = Field(1, ge=0, description="Количество повторов, 0 = бесконечно")
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    active: bool = True


class DisplayVideoCreate(DisplayVideoBase):
    pass


class DisplayVideoUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    video_url: Optional[str] = Field(None, max_length=500)
    thumbnail_url: Optional[str] = Field(None, max_length=500)
    duration_seconds: Optional[int] = Field(None, ge=1)
    file_size_mb: Optional[float] = Field(None, ge=0)
    video_format: Optional[str] = Field(None, max_length=20)
    display_order: Optional[int] = None
    loop_count: Optional[int] = Field(None, ge=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    active: Optional[bool] = None


class DisplayVideoOut(DisplayVideoBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None


# ===================== ОБЪЯВЛЕНИЯ =====================

class DisplayAnnouncementBase(BaseModel):
    board_id: Optional[int] = None  # None = для всех табло
    title: str = Field(..., max_length=200)
    message: str = Field(..., description="Текст объявления")
    announcement_type: str = Field("info", description="info, warning, urgent")
    
    priority: int = Field(0, description="Приоритет (чем выше, тем важнее)")
    scroll_speed: int = Field(50, ge=10, le=100, description="Скорость бегущей строки")
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    language: str = Field("ru", max_length=5)
    active: bool = True


class DisplayAnnouncementCreate(DisplayAnnouncementBase):
    pass


class DisplayAnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    message: Optional[str] = None
    announcement_type: Optional[str] = None
    priority: Optional[int] = None
    scroll_speed: Optional[int] = Field(None, ge=10, le=100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    language: Optional[str] = Field(None, max_length=5)
    active: Optional[bool] = None


class DisplayAnnouncementOut(DisplayAnnouncementBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ===================== ТЕМЫ =====================

class DisplayThemeBase(BaseModel):
    name: str = Field(..., max_length=100, description="Уникальное имя темы")
    display_name: str = Field(..., max_length=150, description="Отображаемое имя")
    css_variables: Dict[str, str] = Field(..., description="CSS переменные")
    font_family: str = Field("system-ui", max_length=100)
    font_sizes: Optional[Dict[str, str]] = None
    background_config: Optional[Dict[str, Any]] = None
    active: bool = True
    is_default: bool = False


class DisplayThemeCreate(DisplayThemeBase):
    pass


class DisplayThemeUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=150)
    css_variables: Optional[Dict[str, str]] = None
    font_family: Optional[str] = Field(None, max_length=100)
    font_sizes: Optional[Dict[str, str]] = None
    background_config: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    is_default: Optional[bool] = None


class DisplayThemeOut(DisplayThemeBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ===================== СОСТОЯНИЕ ТАБЛО =====================

class DisplayBoardState(BaseModel):
    """Текущее состояние табло для отображения"""
    board_id: int
    updated_at: datetime
    
    # Очереди по специалистам
    specialists: List[Dict[str, Any]] = []
    
    # Текущие вызовы
    current_calls: List[Dict[str, Any]] = []
    
    # Объявления
    announcements: List[Dict[str, Any]] = []
    
    # Баннеры
    banners: List[Dict[str, Any]] = []
    
    # Видео (если включены)
    videos: List[Dict[str, Any]] = []


class DisplayTestRequest(BaseModel):
    """Запрос на тестирование табло"""
    board_id: int
    test_type: str = Field("call", description="call, announcement, banner")
    test_data: Optional[Dict[str, Any]] = None
