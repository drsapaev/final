"""Repository helpers for admin display API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminDisplayApiRepository:
    """Shared DB session adapter for admin display service."""

    def __init__(self, db: Session):
        self.db = db
