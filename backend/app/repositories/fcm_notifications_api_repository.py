"""Repository helpers for fcm notifications API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class FcmNotificationsApiRepository:
    """Shared DB session adapter for fcm notifications service."""

    def __init__(self, db: Session):
        self.db = db
