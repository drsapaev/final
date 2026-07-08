"""notification_platform — split from notification_platform_service.py.

Re-exports NotificationPlatformService for backward compatibility.
"""
from __future__ import annotations

from app.services.notification_platform._base import *  # noqa: F401, F403
from app.services.notification_platform._base import (
    NotificationPlatformServiceMixinBase,
)
from app.services.notification_platform._core import CoreMixin
from app.services.notification_platform._policy import PolicyMixin
from app.services.notification_platform._rest import RestMixin

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
        self.ws_manager = get_notification_ws_manager()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------
