"""Repository helpers for security management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SecurityManagementApiRepository:
    """Shared DB session adapter for security management service."""

    def __init__(self, db: Session):
        self.db = db
