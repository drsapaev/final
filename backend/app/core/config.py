# app/core/config.py
from __future__ import annotations

import secrets
from functools import lru_cache
from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- DB ---
    DATABASE_URL: str = "sqlite:///./clinic.db"

    # --- Auth / JWT ---
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32)
    )  # dev-значение; лучше задать в .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней

    # --- CORS (при необходимости) ---
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- Queue / Time ---
    TIMEZONE: str = "Asia/Tashkent"
    QUEUE_START_HOUR: int = 7  # локальное время, начало утреннего окна
    ONLINE_MAX_PER_DAY: int = 15  # лимит онлайн-талонов на отделение/день

    # --- App meta ---
    APP_NAME: str = "Clinic Manager"
    APP_VERSION: str = "0.9.0"
    ENV: str = "dev"

    # --- Printing / PDF ---
    PDF_FOOTER_ENABLED: bool = True
    CLINIC_LOGO_PATH: str | None = None

    # ESC/POS settings (may be missing in env; safe defaults)
    PRINTER_TYPE: str | None = None  # none|network|usb
    PRINTER_NET_HOST: str | None = None
    PRINTER_NET_PORT: int | None = None
    PRINTER_USB_VID: int | None = None
    PRINTER_USB_PID: int | None = None

    @field_validator("PRINTER_USB_VID", "PRINTER_USB_PID", "PRINTER_NET_PORT", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):  # type: ignore[no-untyped-def]
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


@lru_cache(1)
def get_settings() -> Settings:
    s = Settings()
    # на всякий случай гарантируем нормальный ключ в dev
    if not s.SECRET_KEY or len(s.SECRET_KEY) < 16:
        s.SECRET_KEY = secrets.token_urlsafe(32)
    return s

# --- backward-compat для старых импортов ---
settings = get_settings()
