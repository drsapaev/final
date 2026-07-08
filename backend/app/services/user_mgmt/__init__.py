"""user_mgmt — split from user_management_service.py."""
from __future__ import annotations

from app.services.user_mgmt._base import *  # noqa: F401, F403
from app.services.user_mgmt._base import UserManagementServiceMixinBase
from app.services.user_mgmt._core import CoreMixin
from app.services.user_mgmt._operations import OperationsMixin

__all__ = ["UserManagementService"]


class UserManagementService(
    CoreMixin,
    OperationsMixin,
    UserManagementServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self):
        # TODO(DB_ROLES): Move permissions to role_permissions table in Phase 4
        self.default_permissions = {
            "Admin": ["*"],  # Все права
            "Doctor": [
                "patients:read",
                "patients:write",
                "appointments:read",
                "appointments:write",
                "emr:read",
                "emr:write",
                "prescriptions:read",
                "prescriptions:write",
                "schedules:read",
                "schedules:write",
            ],
            "Nurse": [
                "patients:read",
                "appointments:read",
                "emr:read",
                "schedules:read",
            ],
            "Receptionist": [
                "patients:read",
                "patients:write",
                "appointments:read",
                "appointments:write",
                "schedules:read",
                "schedules:write",
                "payments:read",
                "payments:write",
            ],
            "Cashier": [
                "payments:read",
                "payments:write",
                "patients:read",
                "appointments:read",
            ],
            "Lab": [
                "patients:read",
                "emr:read",
                "lab_results:read",
                "lab_results:write",
            ],
            "Patient": [
                "profile:read",
                "profile:write",
                "appointments:read",
                "payments:read",
            ],
        }
