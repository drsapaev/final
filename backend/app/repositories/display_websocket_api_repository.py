"""Repository helpers for display websocket API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DisplayWebsocketApiRepository:
    """Shared DB session adapter for display websocket service."""

    def __init__(self, db: Session):
        self.db = db
