"""Repository helpers for notification websocket API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class NotificationWebsocketApiRepository:
    """Shared DB session adapter for notification websocket service."""

    def __init__(self, db: Session):
        self.db = db
