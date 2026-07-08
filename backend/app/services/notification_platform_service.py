"""Backward-compatible shim for notification_platform package."""
from __future__ import annotations
from app.services.notification_platform import NotificationPlatformService
from app.services.notification_platform._rest import get_notification_platform_service

__all__ = ["NotificationPlatformService", "get_notification_platform_service"]
