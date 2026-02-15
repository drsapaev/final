"""Repository helpers for minimal auth API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class MinimalAuthApiRepository:
    """Shared DB session adapter for minimal auth service."""

    def __init__(self, db: Session):
        self.db = db
