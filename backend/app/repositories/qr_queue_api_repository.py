"""Repository helpers for QR queue API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QrQueueApiRepository:
    """Shared DB session adapter for QR queue service."""

    def __init__(self, db: Session):
        self.db = db
