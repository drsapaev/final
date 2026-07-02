"""Repository helpers for board API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class BoardApiRepository:
    """Shared DB session adapter for board service."""

    def __init__(self, db: Session):
        self.db = db
