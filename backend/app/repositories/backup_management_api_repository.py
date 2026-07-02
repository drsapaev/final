"""Repository helpers for backup management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class BackupManagementApiRepository:
    """Shared DB session adapter for backup management service."""

    def __init__(self, db: Session):
        self.db = db
