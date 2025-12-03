# app/core/config.py
from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
    # SECURITY WARNING: В продакшене ОБЯЗАТЕЛЬНО установите SECRET_KEY через переменную окружения!
    # Используйте: python -c "import secrets; print(secrets.token_urlsafe(32))" для генерации безопасного ключа
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="JWT secret key - MUST be set via environment variable in production (min 32 chars)"
    )  # ⚠️ REQUIRED: No default value for security
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней

    # --- CORS (при необходимости) ---
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
    )
    CORS_DISABLE: bool = False
    CORS_ALLOW_ALL: bool = Field(default=False, description="Allow all CORS origins (dev only)")

    # --- Frontend URL для QR кодов и ссылок ---
    # Для локальной сети (WiFi): оставьте значение по умолчанию или локальный IP
    # Для доступа через интернет (мобильные данные): задайте публичный домен/IP
    # Примеры:
    #   - Локальная сеть: "http://192.168.1.9:5173" (автоматически определится)
    #   - Публичный доступ: "https://clinic.example.com" или "http://123.45.67.89:5173"
    #   - Туннель (ngrok): "https://abc123.ngrok.io"
    # Установите через переменную окружения: FRONTEND_URL=https://your-domain.com
    FRONTEND_URL: str = Field(default="http://192.168.1.9:5173", env="FRONTEND_URL")

    # --- Queue / Time ---
    TIMEZONE: str = "Asia/Tashkent"
    QUEUE_START_HOUR: int = 7  # локальное время, начало утреннего окна
    ONLINE_MAX_PER_DAY: int = 15  # лимит онлайн-талонов на отделение/день

    # --- App meta ---
    APP_NAME: str = "Clinic Manager"
    APP_VERSION: str = "0.9.0"
    ENV: str = "dev"
    
    # --- Backup Settings ---
    AUTO_BACKUP_ENABLED: bool = Field(default=False, description="Enable automated daily backups")
    BACKUP_RETENTION_DAYS: int = Field(default=30, ge=1, le=365, description="Number of days to retain backups")

    # --- MCP Settings ---
    MCP_ENABLED: bool = True
    MCP_LOG_REQUESTS: bool = True
    MCP_FALLBACK_TO_DIRECT: bool = True
    MCP_REQUEST_TIMEOUT: int = 30  # seconds
    MCP_HEALTH_CHECK_INTERVAL: int = 60  # seconds
    MCP_MAX_BATCH_SIZE: int = 10

    # --- AI Provider API Keys ---
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None

    # --- Printing / PDF ---
    PDF_FOOTER_ENABLED: bool = True
    CLINIC_LOGO_PATH: Optional[str] = None

    # ESC/POS settings (may be missing in env; safe defaults)
    PRINTER_TYPE: Optional[str] = None  # none|network|usb

    # --- SMS Providers ---
    # Eskiz SMS (Узбекистан)
    ESKIZ_EMAIL: Optional[str] = None
    ESKIZ_PASSWORD: Optional[str] = None

    # PlayMobile SMS (Узбекистан)
    PLAYMOBILE_API_KEY: Optional[str] = None
    PLAYMOBILE_API_SECRET: Optional[str] = None

    # SMS общие настройки
    SMS_SENDER: str = "Clinic"
    SMS_DEFAULT_PROVIDER: str = "mock"  # eskiz, playmobile, mock

    # --- Firebase Cloud Messaging (FCM) ---
    FCM_SERVER_KEY: Optional[str] = Field(default=None, description="FCM Server Key for push notifications")
    FCM_SENDER_ID: Optional[str] = Field(default=None, description="FCM Sender ID")
    FCM_PROJECT_ID: Optional[str] = Field(default=None, description="FCM Project ID")
    FCM_ENABLED: bool = Field(default=False, description="Enable FCM push notifications")

    # --- Email Settings ---
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True

    # --- Cloud Printing Settings ---
    # Microsoft Universal Print
    MICROSOFT_PRINT_TENANT_ID: Optional[str] = None
    MICROSOFT_PRINT_CLIENT_ID: Optional[str] = None
    MICROSOFT_PRINT_CLIENT_SECRET: Optional[str] = None

    # Cloud Printing общие настройки
    CLOUD_PRINTING_ENABLED: bool = True
    CLOUD_PRINTING_DEFAULT_PROVIDER: str = "mock"  # microsoft, mock
    PRINTER_NET_HOST: Optional[str] = None
    PRINTER_NET_PORT: Optional[int] = None
    PRINTER_USB_VID: Optional[int] = None
    PRINTER_USB_PID: Optional[int] = None

    @field_validator(
        "PRINTER_USB_VID", "PRINTER_USB_PID", "PRINTER_NET_PORT", mode="before"
    )
    @classmethod
    def _empty_str_to_none(cls, v):  # type: ignore[no-untyped-def]
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


# Default SECRET_KEY for development only (will be validated on startup)
_DEFAULT_SECRET_KEY = "dev-secret-key-for-clinic-management-system-change-in-production"


@lru_cache(1)
def get_settings() -> Settings:
    """Get application settings with validation"""
    # ✅ ИСПРАВЛЕНО: Сначала проверяем env var, затем создаем Settings с аргументами
    import os
    secret_key = os.getenv("SECRET_KEY")
    
    # Если SECRET_KEY в env - используем его
    if secret_key:
        s = Settings(SECRET_KEY=secret_key)
    else:
        # Fallback для dev mode - используем default или persistent key
        s = Settings(SECRET_KEY=_DEFAULT_SECRET_KEY)
    
    # Validate SECRET_KEY on load
    if not s.SECRET_KEY or s.SECRET_KEY == _DEFAULT_SECRET_KEY:
        # In production, this should fail - but for dev we allow it with warning
        import os
        env = os.getenv("ENV", "dev").lower()
        if env in ("prod", "production"):
            raise ValueError(
                "SECRET_KEY must be set via environment variable in production. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        # ✅ BUGFIX: In dev, use persistent key from file or generate once and save
        if s.SECRET_KEY == _DEFAULT_SECRET_KEY:
            import warnings
            import pathlib
            
            # Try to load persistent key from .secret_key file (dev only)
            secret_key_file = pathlib.Path(".secret_key")
            if secret_key_file.exists():
                try:
                    persistent_key = secret_key_file.read_text(encoding="utf-8").strip()
                    if len(persistent_key) >= 32:
                        s.SECRET_KEY = persistent_key
                        logger.info("Loaded persistent SECRET_KEY from .secret_key file (dev mode)")
                    else:
                        # Invalid key in file, regenerate
                        persistent_key = secrets.token_urlsafe(32)
                        secret_key_file.write_text(persistent_key, encoding="utf-8")
                        s.SECRET_KEY = persistent_key
                        logger.warning("Regenerated SECRET_KEY in .secret_key file (was too short)")
                except Exception as e:
                    logger.warning(f"Error reading .secret_key file: {e}, generating new key")
                    persistent_key = secrets.token_urlsafe(32)
                    try:
                        secret_key_file.write_text(persistent_key, encoding="utf-8")
                        s.SECRET_KEY = persistent_key
                    except Exception as write_error:
                        logger.error(f"Error writing .secret_key file: {write_error}")
                        # Fallback to in-memory key (will change on restart)
                        s.SECRET_KEY = secrets.token_urlsafe(32)
                        warnings.warn(
                            "Using temporary SECRET_KEY in development (will invalidate tokens on restart). "
                            "Set SECRET_KEY env var or ensure .secret_key file is writable!",
                            UserWarning
                        )
            else:
                # No persistent key file, generate and save
                persistent_key = secrets.token_urlsafe(32)
                try:
                    secret_key_file.write_text(persistent_key, encoding="utf-8")
                    s.SECRET_KEY = persistent_key
                    logger.info("Generated and saved persistent SECRET_KEY to .secret_key file (dev mode)")
                    warnings.warn(
                        "Generated SECRET_KEY for development. Set SECRET_KEY env var for production!",
                        UserWarning
                    )
                except Exception as e:
                    logger.error(f"Error writing .secret_key file: {e}")
                    # Fallback to in-memory key (will change on restart)
                    s.SECRET_KEY = persistent_key
                    warnings.warn(
                        "Using temporary SECRET_KEY in development (will invalidate tokens on restart). "
                        "Set SECRET_KEY env var or ensure .secret_key file is writable!",
                        UserWarning
                    )
    
    # Additional validation: SECRET_KEY must be at least 32 characters
    if len(s.SECRET_KEY) < 32:
        raise ValueError(
            f"SECRET_KEY must be at least 32 characters long. Current length: {len(s.SECRET_KEY)}"
        )
    
    return s


# --- backward-compat для старых импортов ---
settings = get_settings()
