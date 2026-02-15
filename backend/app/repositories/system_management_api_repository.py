"""Repository helpers for system management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SystemManagementApiRepository:
    """Shared DB session adapter for system management service."""

    def __init__(self, db: Session):
        self.db = db
