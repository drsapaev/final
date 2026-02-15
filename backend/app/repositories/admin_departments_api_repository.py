"""Repository helpers for admin departments API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminDepartmentsApiRepository:
    """Shared DB session adapter for admin departments service."""

    def __init__(self, db: Session):
        self.db = db
