"""Repository helpers for roles API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class RolesApiRepository:
    """Shared DB session adapter for roles service."""

    def __init__(self, db: Session):
        self.db = db
