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

    def _sync_doctor_active(
        self,
        db: Session,
        user_id: int,
        active: bool,
        *,
        reason: str = "owner_state_change",
        detach_owner: bool = False,
    ) -> int:
        """Mirror User.is_active onto the linked Doctor profile(s).

        Lifecycle contract (ghost-doctor prevention):
        - a deactivated User must not keep an ACTIVE clinical Doctor
          profile (it would stay visible in registrar selectors, queues
          and morning assignment while being unable to log in);
        - reactivating the User restores the Doctor profile;
        - when the owner User is deleted (detach_owner=True), the Doctor
          profile is deactivated and detached from the owner in the same
          transaction — never deleted. All historical visits/EMR/audit
          references to the Doctor row stay intact.

        detach_owner also makes the behavior deterministic on backends where
        the FK ``ON DELETE SET NULL`` action might not be enforced (e.g.
        SQLite connections without the foreign_keys pragma) — the ORM sets
        doctors.user_id to NULL explicitly instead of relying on the DDL.

        Returns the number of Doctor rows updated.
        """
        values: dict[str, object] = {"active": active}
        if detach_owner:
            values["user_id"] = None
        filters = [Doctor.user_id == user_id]
        if not detach_owner:
            # No-op sync: skip rows already in the requested state.
            filters.append(Doctor.active != active)
        updated = (
            db.query(Doctor)
            .filter(*filters)
            .update(values, synchronize_session=False)
        )
        if updated:
            logger.info(
                "Doctor profiles synced to owner state: user_id=%s "
                "active=%s reason=%s rows=%s",
                user_id,
                active,
                reason,
                updated,
            )
        return updated












































































































































