"""Backward-compatible shim for notification_platform package."""
from __future__ import annotations

from app.services.notification_platform import NotificationPlatformService  # noqa: F401
from app.services.notification_platform._rest import (
    get_notification_platform_service,  # noqa: F401
)
from app.services.notification_websocket import (
    get_notification_ws_manager,  # noqa: F401
)

__all__ = ["NotificationPlatformService", "get_notification_platform_service", "get_notification_ws_manager"]
