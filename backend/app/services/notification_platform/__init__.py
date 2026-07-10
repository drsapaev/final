"""notification_platform — split from notification_platform_service.py.

Re-exports NotificationPlatformService for backward compatibility.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.notification_platform_repository import (
    NotificationPlatformRepository,
)
from app.services.notification_platform._base import *  # noqa: F401, F403
from app.services.notification_platform._base import (
    NotificationPlatformServiceMixinBase,
)
from app.services.notification_platform._core import CoreMixin
from app.services.notification_platform._policy import PolicyMixin
from app.services.notification_platform._rest import RestMixin
from app.services.notification_websocket import get_notification_ws_manager

__all__ = ["NotificationPlatformService"]


class NotificationPlatformService(
    CoreMixin,
    PolicyMixin,
    RestMixin,
    NotificationPlatformServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = NotificationPlatformRepository(db)
        self._ws_manager = None

    @property
    def ws_manager(self):
        if self._ws_manager is None:
            self._ws_manager = get_notification_ws_manager()
        return self._ws_manager

    @ws_manager.setter
    def ws_manager(self, value):
        self._ws_manager = value

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------
