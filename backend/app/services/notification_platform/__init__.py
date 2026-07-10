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
        # Resolve ``get_notification_ws_manager`` via the
        # ``notification_platform_service`` shim at call time so unit tests
        # that monkeypatch ``notification_platform_service.get_notification_ws_manager``
        # see the patched value.
        from app.services.notification_platform_service import (
            get_notification_ws_manager as _get_notification_ws_manager,
        )
        self.db = db
        self.repository = NotificationPlatformRepository(db)
        self.ws_manager = _get_notification_ws_manager()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------
