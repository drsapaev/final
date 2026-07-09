# app/core/config.py
from __future__ import annotations

import json
import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)

# Resolve the backend root so config can load backend/.env consistently.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # app/core/config.py -> backend/
_DEFAULT_ENV_FILE = _BACKEND_DIR / ".env"
_DEFAULT_DATABASE_URL = ""


class _CompatibleCorsEnvSettingsSource(EnvSettingsSource):
    """Allow comma-separated CORS origin strings instead of JSON arrays."""

    def prepare_field_value(self, field_name, field, value, value_is_complex):  # type: ignore[no-untyped-def]
        if field_name == "BACKEND_CORS_ORIGINS" and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class _CompatibleCorsDotEnvSettingsSource(DotEnvSettingsSource):
    """Allow comma-separated CORS origin strings in backend/.env."""

    def prepare_field_value(self, field_name, field, value, value_is_complex):  # type: ignore[no-untyped-def]
        if field_name == "BACKEND_CORS_ORIGINS" and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- DB ---
    # Uses absolute path to prevent multiple copies when running from different directories
    DATABASE_URL: str = _DEFAULT_DATABASE_URL

    # --- Auth / JWT ---
    # SECURITY WARNING: В продакшене ОБЯЗАТЕЛЬНО установите SECRET_KEY через переменную окружения!
    # Используйте: python -c "import secrets; print(secrets.token_urlsafe(32))" для генерации безопасного ключа
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="JWT secret key - MUST be set via environment variable in production (min 32 chars)"
    )  # ⚠️ REQUIRED: No default value for security
    ALGORITHM: str = "HS256"
    AUTH_SECRET: str | None = Field(
        default=None,
        description="Legacy JWT helper secret. Defaults to SECRET_KEY when unset.",
    )
    AUTH_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes — use refresh tokens for longer sessions
    ENABLE_FALLBACK_AUTH: bool = Field(
        default=False,
        description="Enable legacy/fallback auth login endpoints. Keep false outside explicit break-glass/dev use.",
    )
    ENABLE_TEST_PAYMENT_INIT: bool = Field(
        default=False,
        description="Enable /payments/test-init endpoint (bypasses audit logging). Keep false in production.",
    )

    # --- CORS (при необходимости) ---
    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        validation_alias=AliasChoices("BACKEND_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            _CompatibleCorsEnvSettingsSource(settings_cls),
            _CompatibleCorsDotEnvSettingsSource(settings_cls),
            file_secret_settings,
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
    FRONTEND_URL: str = Field(default="http://192.168.1.9:5173")

    # --- Queue / Time ---
    TIMEZONE: str = "Asia/Tashkent"
    QUEUE_START_HOUR: int = 7  # локальное время, начало утреннего окна
    ONLINE_MAX_PER_DAY: int = 15  # лимит онлайн-талонов на отделение/день

    # --- Background tasks (arq + Redis) ---
    # Replaces previous Celery stub. arq is asyncio-native and matches the
    # FastAPI stack. See app/tasks/worker.py for the worker entry point.
    ARQ_REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # --- Payment providers ---
    CLICK_ENABLED: bool = Field(default=False, description="Enable Click payments")
    CLICK_SERVICE_ID: str | None = Field(default=None, description="Click service id")
    CLICK_MERCHANT_ID: str | None = Field(default=None, description="Click merchant id")
    CLICK_SECRET_KEY: str | None = Field(default=None, description="Click secret key")
    CLICK_BASE_URL: str = Field(default="https://api.click.uz/v2")

    PAYME_ENABLED: bool = Field(default=False, description="Enable PayMe payments")
    PAYME_MERCHANT_ID: str | None = Field(default=None, description="PayMe merchant id")
    PAYME_SECRET_KEY: str | None = Field(default=None, description="PayMe secret key")
    PAYME_BASE_URL: str = Field(default="https://checkout.paycom.uz")
    PAYME_API_URL: str = Field(default="https://api.paycom.uz")

    KASPI_ENABLED: bool = Field(default=False, description="Enable Kaspi payments")
    KASPI_MERCHANT_ID: str | None = Field(default=None, description="Kaspi merchant id")
    KASPI_SECRET_KEY: str | None = Field(default=None, description="Kaspi secret key")
    KASPI_BASE_URL: str = Field(default="https://kaspi.kz/pay")
    KASPI_API_URL: str = Field(default="https://api.kaspi.kz/pay/v1")

    # --- App meta ---
    APP_NAME: str = "Clinic Manager"
    APP_VERSION: str = "0.9.0"
    ENV: str = "dev"
    LOG_LEVEL: str = Field(default="INFO", description="Root logging level")
    LOG_STRUCTURED: bool = Field(
        default=True, description="Enable JSON structured logs to stdout"
    )

    # --- Observability / SLA ---
    OBS_SLA_WINDOW_SECONDS: int = Field(
        default=300, ge=60, le=3600, description="SLA rolling window in seconds"
    )
    OBS_SLA_LATENCY_P95_MS: float = Field(
        default=1200.0, ge=100.0, le=30000.0, description="SLA p95 latency threshold"
    )
    OBS_SLA_ERROR_RATE_PCT: float = Field(
        default=5.0, ge=0.1, le=100.0, description="SLA error rate threshold in percent"
    )
    OBS_SLA_QUEUE_LAG_MAX: int = Field(
        default=50, ge=1, le=10000, description="SLA threshold for queue lag count"
    )

    # --- Message Encryption ---
    # SECURITY: В production ОБЯЗАТЕЛЬНО установите через переменную окружения!
    # Сгенерируйте ключ: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    MESSAGE_ENCRYPTION_KEY: str | None = Field(
        default=None,
        description="Fernet encryption key for message at-rest encryption. Required in production."
    )

    # --- Backup Settings ---
    AUTO_BACKUP_ENABLED: bool = Field(default=False, description="Enable automated daily backups")
    BACKUP_RETENTION_DAYS: int = Field(default=30, ge=1, le=365, description="Number of days to retain backups")

    # --- Clinical Security Maturity ---
    PHI_RETENTION_DAYS: int = Field(
        default=365 * 7,
        ge=30,
        le=365 * 30,
        description="Retention period for PHI-bearing records (days)"
    )
    BREAK_GLASS_ENABLED: bool = Field(
        default=False,
        description="Enable emergency break-glass access mode"
    )
    BREAK_GLASS_MAX_MINUTES: int = Field(
        default=60,
        ge=1,
        le=720,
        description="Maximum break-glass session duration in minutes"
    )
    BREAK_GLASS_REASON_MIN_LENGTH: int = Field(
        default=20,
        ge=5,
        le=500,
        description="Minimum justification length for break-glass reason"
    )
    BREAK_GLASS_REQUIRE_TICKET: bool = Field(
        default=True,
        description="Require incident/ticket reference for break-glass sessions"
    )
    BREAK_GLASS_ALLOWED_ROLES: str = Field(
        default="Admin,ChiefDoctor",
        description="Comma-separated list of roles allowed to use break-glass"
    )

    # --- Tenant Scope Enforcement (multi-clinic rollout) ---
    TENANT_SCOPE_ENFORCE_WRITES: bool = Field(
        default=False,
        description="Require branch scope for high-risk write endpoints"
    )
    TENANT_SCOPE_WRITE_PREFIXES: str = Field(
        default="/api/v1/billing,/api/v1/queue,/api/v1/emr,/api/v1/v2/emr,/api/v1/clinic/equipment",
        description="Comma-separated URL prefixes protected by tenant write-scope enforcement"
    )

    # --- MCP Settings ---
    MCP_ENABLED: bool = True
    MCP_LOG_REQUESTS: bool = True
    MCP_FALLBACK_TO_DIRECT: bool = True

    # ⚠️ TIMEOUT LAYERING (ВАЖНО для AI-пайплайнов):
    # MCP_REQUEST_TIMEOUT >= AI_PROVIDER_TIMEOUT, иначе верхний уровень обрежет нижний!
    # Уровни:
    #   1. MCP (orchestrator)  → MCP_REQUEST_TIMEOUT      → глобальный лимит asyncio.wait_for
    #   2. Provider (HTTP/SDK) → AI_PROVIDER_TIMEOUT      → httpx/openai client timeout
    #   3. Frontend (UX)       → axios timeout в mcpClient.js (120s)
    MCP_REQUEST_TIMEOUT: int = Field(
        default=180,  # секунды - ОБЯЗАТЕЛЬНО >= AI_PROVIDER_TIMEOUT!
        ge=30,
        le=600,
        description="Global MCP orchestrator timeout. Must be >= AI_PROVIDER_TIMEOUT!"
    )
    AI_PROVIDER_TIMEOUT: int = Field(
        default=180,  # секунды - таймаут HTTP-запросов к AI провайдерам
        ge=30,
        le=600,
        description="HTTP timeout for AI provider API calls (DeepSeek, OpenAI, Gemini)"
    )

    MCP_HEALTH_CHECK_INTERVAL: int = 60  # seconds
    MCP_MAX_BATCH_SIZE: int = 10

    # --- AI Provider API Keys ---
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None
    XAI_API_KEY: str | None = Field(default=None, description="xAI (Grok) API key for AI features")

    # --- AI Security & Encryption ---
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str | None = Field(
        default=None,
        description="Fernet encryption key for encrypting API keys in database"
    )

    # --- AI Rate Limiting ---
    AI_RATE_LIMIT_PER_USER_HOUR: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Max AI requests per user per hour"
    )
    AI_RATE_LIMIT_PER_PROVIDER_MINUTE: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Max requests to each AI provider per minute (protects against provider rate limits)"
    )

    # --- AI Cost Control ---
    AI_MONTHLY_BUDGET_USD: float = Field(
        default=500.0,
        ge=0.0,
        description="Monthly budget for AI API calls in USD"
    )
    AI_BUDGET_ALERT_THRESHOLD_PCT: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Alert when budget usage exceeds this percentage"
    )

    # --- AI Caching ---
    AI_CACHE_TTL_HOURS: int = Field(
        default=24,
        ge=1,
        le=168,  # Max 1 week
        description="Time-to-live for AI response cache in hours"
    )
    AI_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable caching of AI responses"
    )

    # --- Printing / PDF ---
    PDF_FOOTER_ENABLED: bool = True
    CLINIC_LOGO_PATH: str | None = None

    # ESC/POS settings (may be missing in env; safe defaults)
    PRINTER_TYPE: str | None = None  # none|network|usb

    # --- SMS Providers ---
    # Eskiz SMS (Узбекистан)
    ESKIZ_EMAIL: str | None = None
    ESKIZ_PASSWORD: str | None = None

    # PlayMobile SMS (Узбекистан)
    PLAYMOBILE_API_KEY: str | None = None
    PLAYMOBILE_API_SECRET: str | None = None

    # SMS общие настройки
    SMS_SENDER: str = "Clinic"
    SMS_DEFAULT_PROVIDER: str = "mock"  # eskiz, playmobile, mock

    # --- Firebase Cloud Messaging (FCM) ---
    FCM_SERVER_KEY: str | None = Field(default=None, description="FCM Server Key for push notifications")
    FCM_SENDER_ID: str | None = Field(default=None, description="FCM Sender ID")
    FCM_PROJECT_ID: str | None = Field(default=None, description="FCM Project ID")
    FCM_ENABLED: bool = Field(default=False, description="Enable FCM push notifications")

    # --- Email Settings ---
    SMTP_SERVER: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = True

    # --- Telegram Settings ---
    TELEGRAM_BOT_TOKEN: str | None = Field(default=None, description="Telegram Bot API token for notifications")
    TELEGRAM_CHAT_ID: str | None = Field(default=None, description="Default Telegram chat ID for system alerts")

    # --- Cloud Printing Settings ---
    # Microsoft Universal Print
    MICROSOFT_PRINT_TENANT_ID: str | None = None
    MICROSOFT_PRINT_CLIENT_ID: str | None = None
    MICROSOFT_PRINT_CLIENT_SECRET: str | None = None

    # Cloud Printing общие настройки
    CLOUD_PRINTING_ENABLED: bool = True
    CLOUD_PRINTING_DEFAULT_PROVIDER: str = "mock"  # microsoft, mock
    PRINTER_NET_HOST: str | None = None
    PRINTER_NET_PORT: int | None = None
    PRINTER_USB_VID: int | None = None
    PRINTER_USB_PID: int | None = None

    EMR_LEGACY_WRITE_FREEZE: bool = Field(
        default=False,
        description="Reject legacy appointment-based EMR writes during hard-cutover maintenance windows.",
    )

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

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return value
        if isinstance(value, str):
            if value.strip().startswith("["):
                origins = json.loads(value)
                logger.info("[FIX:CORS] Parsed %d CORS origins from JSON env string", len(origins))
                return origins
            origins = [origin.strip() for origin in value.split(",") if origin.strip()]
            logger.info("[FIX:CORS] Parsed %d CORS origins from env string", len(origins))
            return origins
        return value


# Runtime-only sentinel for missing dev SECRET_KEY; never a stable credential.
_DEFAULT_SECRET_KEY = secrets.token_urlsafe(32)


@lru_cache(1)
def get_settings() -> Settings:
    """Get application settings with validation"""
    secret_key_from_process_env = os.getenv("SECRET_KEY")
    # Загружаем backend/.env в os.environ до os.getenv("SECRET_KEY"), иначе ключ из файла игнорируется.
    if _DEFAULT_ENV_FILE.is_file():
        from dotenv import load_dotenv

        load_dotenv(_DEFAULT_ENV_FILE, override=False)

    # ✅ ИСПРАВЛЕНО: Сначала проверяем env var, затем создаем Settings с аргументами
    secret_key = os.getenv("SECRET_KEY")

    # Если SECRET_KEY в env - используем его
    if secret_key:
        s = Settings(SECRET_KEY=secret_key)
    else:
        # Fallback для dev mode - используем default или persistent key
        s = Settings(SECRET_KEY=_DEFAULT_SECRET_KEY)
    env = (s.ENV or os.getenv("ENV", "dev")).lower()

    if env in ("prod", "production") and not secret_key_from_process_env:
        raise ValueError(
            "SECRET_KEY must be set via environment variable in production. "
            "Do not rely on backend/.env for production secrets."
        )

    # Validate SECRET_KEY on load
    if not s.SECRET_KEY or s.SECRET_KEY == _DEFAULT_SECRET_KEY:
        # In production, this should fail - but for dev we allow it with warning
        if env in ("prod", "production"):
            raise ValueError(
                "SECRET_KEY must be set via environment variable in production. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        # ✅ BUGFIX: In dev, use persistent key from file or generate once and save
        if s.SECRET_KEY == _DEFAULT_SECRET_KEY:
            import pathlib
            import warnings

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
                            UserWarning,
                            stacklevel=2,
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
                        UserWarning,
                        stacklevel=2,
                    )
                except Exception as e:
                    logger.error(f"Error writing .secret_key file: {e}")
                    # Fallback to in-memory key (will change on restart)
                    s.SECRET_KEY = persistent_key
                    warnings.warn(
                        "Using temporary SECRET_KEY in development (will invalidate tokens on restart). "
                        "Set SECRET_KEY env var or ensure .secret_key file is writable!",
                        UserWarning,
                        stacklevel=2,
                    )

    # Additional validation: SECRET_KEY must be at least 32 characters
    if len(s.SECRET_KEY) < 32:
        raise ValueError(
            f"SECRET_KEY must be at least 32 characters long. Current length: {len(s.SECRET_KEY)}"
        )

    if not s.AUTH_SECRET:
        s.AUTH_SECRET = s.SECRET_KEY
    if len(s.AUTH_SECRET) < 32:
        raise ValueError(
            f"AUTH_SECRET must be at least 32 characters long. Current length: {len(s.AUTH_SECRET)}"
        )

    if os.getenv("CORS_ORIGINS") and not os.getenv("BACKEND_CORS_ORIGINS"):
        logger.info("[FIX:CORS] Using legacy CORS_ORIGINS env variable for backend CORS config")

    # ✅ SECURITY: Production-specific validations
    if env in ("prod", "production"):
        errors = []
        warnings_list = []

        # === MANDATORY CHECKS (will raise error) ===

        # 1. CORS_ALLOW_ALL must be False
        if s.CORS_ALLOW_ALL:
            errors.append(
                "CORS_ALLOW_ALL must be False in production. "
                "Set allowed origins via BACKEND_CORS_ORIGINS env variable."
            )

        # 2. SECRET_KEY must not be the default placeholder
        if "change_me" in s.SECRET_KEY.lower() or s.SECRET_KEY == _DEFAULT_SECRET_KEY:
            errors.append(
                "SECRET_KEY must be set to a unique, secure value in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )

        # 3. DATABASE_URL должен быть явно настроен и использовать PostgreSQL
        if not s.DATABASE_URL.strip():
            errors.append(
                "DATABASE_URL must be set via environment variable in production."
            )
        elif "sqlite" in s.DATABASE_URL.lower():
            errors.append(
                "SQLite is not recommended for production. "
                "Set DATABASE_URL to PostgreSQL: postgresql://user:pass@host:5432/dbname"
            )

        # 4. FRONTEND_URL должен быть HTTPS или localhost
        if s.FRONTEND_URL and not (
            s.FRONTEND_URL.startswith("https://") or
            "localhost" in s.FRONTEND_URL or
            "127.0.0.1" in s.FRONTEND_URL
        ):
            warnings_list.append(
                f"FRONTEND_URL ({s.FRONTEND_URL}) should use HTTPS in production."
            )

        # 5. BACKEND_CORS_ORIGINS должен содержать только HTTPS origins
        for origin in s.BACKEND_CORS_ORIGINS:
            if not origin.startswith("https://") and "localhost" not in origin and "127.0.0.1" not in origin:
                warnings_list.append(
                    f"CORS origin '{origin}' should use HTTPS in production."
                )

        # 6. ENABLE_FALLBACK_AUTH must be False in production (2FA bypass risk)
        if s.ENABLE_FALLBACK_AUTH:
            errors.append(
                "ENABLE_FALLBACK_AUTH must be False in production. "
                "Legacy/fallback login endpoints bypass 2FA, account lockout, "
                "and login-attempt logging. Set ENABLE_FALLBACK_AUTH=false."
            )

        # 7. DISABLE_2FA_REQUIREMENT must not be set in production
        if os.getenv("DISABLE_2FA_REQUIREMENT", "").lower() in ("1", "true", "yes"):
            errors.append(
                "DISABLE_2FA_REQUIREMENT must not be set in production. "
                "This env var disables 2FA enforcement for Admin/Cashier roles."
            )

        # AI-REAUDIT-28 P0-8: ENCRYPTION_KEY обязателен в production.
        # Без него AI provider API keys хранятся plaintext в ai_providers.api_key.
        if not s.ENCRYPTION_KEY:
            errors.append(
                "ENCRYPTION_KEY must be set in production — "
                "without it, AI provider API keys are stored in plaintext."
            )

        # 8. ENABLE_TEST_PAYMENT_INIT must be False in production
        if s.ENABLE_TEST_PAYMENT_INIT:
            errors.append(
                "ENABLE_TEST_PAYMENT_INIT must be False in production. "
                "The /payments/test-init endpoint bypasses audit logging."
            )

        # NOTIF-REAUDIT-28 P0-4: в production должен быть настроен реальный
        # SMS-провайдер (Eskiz или PlayMobile). MockSMSProvider молча
        # "успешно" отправляет SMS без реальной доставки — password reset,
        # 2FA, напоминания silently fail.
        # NOTE: This check is skipped in test environments (TESTING=1)
        # to allow CI to run without real SMS provider credentials.
        if not os.environ.get("TESTING") and not s.ESKIZ_EMAIL and not s.PLAYMOBILE_API_KEY:
            errors.append(
                "At least one real SMS provider must be configured in production "
                "(ESKIZ_EMAIL or PLAYMOBILE_API_KEY). MockSMSProvider is not allowed."
            )

        # === OUTPUT WARNINGS ===
        for warning in warnings_list:
            logger.warning(f"⚠️ PRODUCTION WARNING: {warning}")

        # === RAISE ERRORS ===
        if errors:
            error_msg = "Production configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

    return s


# --- backward-compat для старых импортов ---
settings = get_settings()
