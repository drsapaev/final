"""Repository helpers for audit API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AuditApiRepository:
    """Shared DB session adapter for audit service."""

    def __init__(self, db: Session):
        self.db = db
