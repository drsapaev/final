"""
Сервис для управления пользователями
"""

import csv  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
from datetime import UTC, datetime, timedelta  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401

from sqlalchemy import and_, or_  # noqa: F401
from sqlalchemy.exc import IntegrityError  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.core.security import get_password_hash  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_profile import (  # noqa: F401
    UserAuditLog,
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
    UserStatus,
)
from app.schemas.user_management import (  # noqa: F401
    UserBulkActionRequest,
    UserCreateRequest,
    UserExportRequest,
    UserNotificationSettingsUpdate,
    UserPreferencesUpdate,
    UserSearchRequest,
    UserUpdateRequest,
)

logger = logging.getLogger(__name__)



class UserManagementServiceMixinBase:
    """Type-hint anchor."""












































































































































