"""
API endpoints для управления пользователями
"""

import json  # noqa: F401
import re  # noqa: F401
from datetime import datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import (  # noqa: F401
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session  # noqa: F401

from app.api.deps import get_current_user, require_roles, require_staff  # noqa: F401
from app.crud.user_management import (  # noqa: F401
    user_audit_log,
    user_notification_settings,
    user_preferences,
    user_profile,
)
from app.db.session import get_db  # noqa: F401
from app.models.user import User  # noqa: F401
from app.schemas.misc_endpoints import UserPreferencesRequest  # noqa: F401
from app.schemas.user_management import (  # noqa: F401
    UserAuditLogResponse,
    UserBulkActionRequest,
    UserBulkActionResponse,
    UserCreateRequest,
    UserExportRequest,
    UserExportResponse,
    UserListResponse,
    UserNotificationSettingsResponse,
    UserNotificationSettingsUpdate,
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserProfileResponse,
    UserProfileUpdate,
    UserResponse,
    UserSearchRequest,
    UserStatsResponse,
    UserUpdateRequest,
)
from app.services.user_management_api_service import (
    UserManagementApiService,  # noqa: F401
)
from app.services.user_management_service import (  # noqa: F401
    get_user_management_service,
)

router = APIRouter()

USER_EXPORT_DIR = Path("exports/users")
USER_EXPORT_FILENAME_RE = re.compile(
    r"^users_export_\d{8}_\d{6}\.(csv|json|xlsx|pdf|txt)$"
)


def _safe_user_export_filename(filename: str) -> str:
    if not filename or filename != filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Недопустимое имя файла"
        )

    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Недопустимое имя файла"
        )

    if not USER_EXPORT_FILENAME_RE.fullmatch(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Недопустимое имя файла"
        )

    return filename


def _find_user_export_file(filename: str) -> Path:
    safe_filename = _safe_user_export_filename(filename)
    export_root = USER_EXPORT_DIR.resolve()

    if not export_root.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден"
        )

    for export_path in export_root.iterdir():
        resolved_path = export_path.resolve()
        if resolved_path.parent != export_root or not resolved_path.is_file():
            continue
        if export_path.name == safe_filename:
            return resolved_path

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")


def _user_export_mime_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return "text/csv"
    if suffix == ".json":
        return "application/json"
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".txt":
        return "text/plain"
    return "application/octet-stream"


def _normalize_theme(theme: str | None) -> str:
    if theme == "system":
        return "auto"
    return theme or "auto"


def _coerce_json_mapping(value, default=None):
    if default is None:
        default = {}

    if value is None:
        return default
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return default
    return value if isinstance(value, dict) else default


# ============================================
# CURRENT USER SELF-SERVICE ENDPOINTS
# IMPORTANT: These must be BEFORE /users/{user_id} routes!
# ============================================

