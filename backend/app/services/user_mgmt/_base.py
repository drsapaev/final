"""
Сервис для управления пользователями
"""

import csv
import json
import logging
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User
from app.models.user_profile import (
    UserAuditLog,
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
    UserStatus,
)
from app.schemas.user_management import (
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












































































































































