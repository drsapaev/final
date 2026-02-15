"""Repository helpers for group permissions API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class GroupPermissionsApiRepository:
    """Shared DB session adapter for group permissions service."""

    def __init__(self, db: Session):
        self.db = db
