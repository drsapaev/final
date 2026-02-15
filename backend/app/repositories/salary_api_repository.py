"""Repository helpers for salary API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SalaryApiRepository:
    """Shared DB session adapter for salary service."""

    def __init__(self, db: Session):
        self.db = db
