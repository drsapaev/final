"""
Сервис для аутентификации с JWT токенами
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, UTC
from typing import Any

import jwt
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.authentication import (
    EmailVerificationToken,
    LoginAttempt,
    PasswordResetToken,
    RefreshToken,
    SecurityEvent,
    UserSession,
)
from app.models.user import User
from app.services.user_management_service import get_user_management_service

logger = logging.getLogger(__name__)

# Используем функции из app.core.security




class AuthenticationServiceMixinBase:
    """Type-hint anchor."""
    pass
