"""Service layer for mobile_api endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.mobile_api_repository import MobileApiRepository


class MobileApiService:
    """Orchestrates persistence operations in mobile API endpoints."""

    def __init__(
        self,
        db: Session,
        repository: MobileApiRepository | None = None,
    ):
        self.repository = repository or MobileApiRepository(db)

    def update_user_device_token(self, *, user, device_token: str):  # type: ignore[no-untyped-def]
        return self.repository.update_device_token(user=user, device_token=device_token)

    def mark_notification_as_read(self, *, notification):  # type: ignore[no-untyped-def]
        return self.repository.mark_notification_read(notification=notification)

