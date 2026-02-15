"""Repository helpers for admin doctors API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminDoctorsApiRepository:
    """Shared DB session adapter for admin doctors service."""

    def __init__(self, db: Session):
        self.db = db
