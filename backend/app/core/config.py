# app/core/config.py
from __future__ import annotations

import secrets
from functools import lru_cache
from pydantic import Field
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


@lru_cache(1)
def get_settings() -> Settings:
    s = Settings()
    # на всякий случай гарантируем нормальный ключ в dev
    if not s.SECRET_KEY or len(s.SECRET_KEY) < 16:
        s.SECRET_KEY = secrets.token_urlsafe(32)
    return s

# --- backward-compat для старых импортов ---
settings = get_settings()
