"""Repository helpers for admin stats endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminStatsApiRepository:
    """Thin ORM access layer for admin statistics service."""

    def __init__(self, db: Session):
        self.db = db

    def query(self, *entities):
        return self.db.query(*entities)
