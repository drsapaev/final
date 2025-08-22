from __future__ import annotations

import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Общие
    APP_NAME: str = "Clinic Manager API"
    APP_VERSION: str = "0.9.0"
    API_V1_STR: str = "/api/v1"

    # --- БД ---
    # По умолчанию локальный SQLite-файл рядом с проектом (./data.db).
    # Если хочешь Postgres — просто задай ENV DATABASE_URL.
    # Примеры:
    #  - sqlite (относительный файл): sqlite:///./data.db
    #  - sqlite (абсолютный путь на Windows): sqlite:///C:/final/backend/data.db
    #  - postgres: postgresql+psycopg2://user:pass@localhost:5432/clinic
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data.db")
    )
    # Включить SQL логирование (1) при отладке
    DATABASE_ECHO: bool = Field(default_factory=lambda: os.getenv("DATABASE_ECHO", "0") == "1")

    # --- JWT (совпадает с тем, что использует fallback-логин в main.py) ---
    AUTH_SECRET: str = Field(default_factory=lambda: os.getenv("JWT_SECRET", "dev-secret"))
    AUTH_ALGORITHM: str = Field(default_factory=lambda: os.getenv("JWT_ALG", "HS256"))
    # Минуты жизни токена; если задан JWT_TTL (секунды) — считаем из него
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default_factory=lambda: max(1, int(int(os.getenv("JWT_TTL", "7200")) / 60))
    )

    # --- CORS ---
    CORS_DISABLE: bool = Field(default_factory=lambda: os.getenv("CORS_DISABLE", "0") == "1")
    CORS_ALLOW_ALL: bool = Field(default_factory=lambda: os.getenv("CORS_ALLOW_ALL", "0") == "1")
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
