from __future__ import annotations

import os
from pydantic import Field, BaseSettings, SettingsConfigDict

def _exp_minutes_default() -> int:
    if os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"):
        return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    return max(1, int(os.getenv("JWT_TTL", "7200")) // 60)

class Settings(BaseSettings):
    APP_NAME: str = "Clinic Queue Manager"
    APP_VERSION: str = "0.9.0"

    DATABASE_URL: str = Field(default=os.getenv("DATABASE_URL", "sqlite:///./app.db"))

    AUTH_SECRET: str = Field(default=os.getenv("JWT_SECRET", "dev-secret"))
    AUTH_ALGORITHM: str = Field(default=os.getenv("JWT_ALG", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default_factory=_exp_minutes_default)

    CORS_ORIGINS: str = Field(
        default=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()