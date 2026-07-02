"""Repository helpers for websocket auth API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class WebsocketAuthApiRepository:
    """Shared DB session adapter for websocket auth service."""

    def __init__(self, db: Session):
        self.db = db
