from __future__ import annotations

import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _exp_minutes_default() -> int:
    # приоритет: ACCESS_TOKEN_EXPIRE_MINUTES (мин), иначе JWT_TTL (сек) -> мин
    if os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"):
        return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    return int(int(os.getenv("JWT_TTL", "7200")) // 60)


class Settings(BaseSettings):
    # Общее
    APP_NAME: str = "Clinic Queue Manager"
    APP_VERSION: str = "0.9.0"

    # БД (оставь свой URL, если у тебя в .env)
    DATABASE_URL: str = Field(default=os.getenv("DATABASE_URL", "sqlite:///./app.db"))

    # JWT
    AUTH_SECRET: str = Field(default=os.getenv("JWT_SECRET", "dev-secret"))
    AUTH_ALGORITHM: str = Field(default=os.getenv("JWT_ALG", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default_factory=_exp_minutes_default)

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
            ).split(",")
            if o.strip()
        ]
    )
    CORS_DISABLE: bool = Field(default=os.getenv("CORS_DISABLE", "0") == "1")
    CORS_ALLOW_ALL: bool = Field(default=os.getenv("CORS_ALLOW_ALL", "0") == "1")

    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__")


settings = Settings()
