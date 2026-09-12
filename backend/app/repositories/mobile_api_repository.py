"""Repository helpers for mobile_api endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MobileApiRepository:
    """Encapsulates small persistence operations used by mobile API."""

    def __init__(self, db: Session):
        self.db = db

    def update_device_token(self, *, user, device_token: str):  # type: ignore[no-untyped-def]
        user.device_token = device_token
        # PR-5: registering a token on the single-device registry is an
        # explicit opt-in act. Without this, a login-time registration would
        # leave push_notifications_enabled=False and the sender-level flag
        # gate would silently skip every login-registered device.
        user.push_notifications_enabled = True
        self.db.commit()
        self.db.refresh(user)
        return user

    def mark_notification_read(self, *, notification):  # type: ignore[no-untyped-def]
        if hasattr(notification, "read"):
            notification.read = True
            self.db.commit()
            self.db.refresh(notification)
            return True
        return True

