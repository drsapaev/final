"""
Сервис для аутентификации с JWT токенами
"""

import logging  # noqa: F401
import secrets  # noqa: F401
import uuid  # noqa: F401
from datetime import UTC, datetime, timedelta  # noqa: F401
from typing import Any  # noqa: F401

import jwt  # noqa: F401
from sqlalchemy import and_, desc, or_  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.core.security import get_password_hash, verify_password  # noqa: F401
from app.models.authentication import (  # noqa: F401
    EmailVerificationToken,
    LoginAttempt,
    PasswordResetToken,
    RefreshToken,
    SecurityEvent,
    UserSession,
)
from app.models.user import User  # noqa: F401
from app.services.user_management_service import (
    get_user_management_service,  # noqa: F401
)

logger = logging.getLogger(__name__)

# Используем функции из app.core.security




class AuthenticationServiceMixinBase:
    """Type-hint anchor."""
    pass
