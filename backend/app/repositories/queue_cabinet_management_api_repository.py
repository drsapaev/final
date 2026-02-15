"""Repository helpers for queue cabinet management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class QueueCabinetManagementApiRepository:
    """Shared DB session adapter for queue cabinet management service."""

    def __init__(self, db: Session):
        self.db = db
