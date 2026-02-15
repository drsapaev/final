"""Repository helpers for admin users API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminUsersApiRepository:
    """Shared DB session adapter for admin users service."""

    def __init__(self, db: Session):
        self.db = db
