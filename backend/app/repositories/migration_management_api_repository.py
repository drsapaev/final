"""Repository helpers for migration management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MigrationManagementApiRepository:
    """Shared DB session adapter for migration management service."""

    def __init__(self, db: Session):
        self.db = db
