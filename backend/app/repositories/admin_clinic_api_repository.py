"""Repository helpers for admin clinic API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AdminClinicApiRepository:
    """Shared DB session adapter for admin clinic service."""

    def __init__(self, db: Session):
        self.db = db
