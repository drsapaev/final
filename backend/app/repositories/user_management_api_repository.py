"""Repository helpers for user management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class UserManagementApiRepository:
    """Shared DB session adapter for user management service."""

    def __init__(self, db: Session):
        self.db = db
