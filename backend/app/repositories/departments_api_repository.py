"""Repository helpers for departments API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DepartmentsApiRepository:
    """Shared DB session adapter for departments service."""

    def __init__(self, db: Session):
        self.db = db
