"""Repository helpers for emr lab integration API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmrLabIntegrationApiRepository:
    """Shared DB session adapter for emr lab integration service."""

    def __init__(self, db: Session):
        self.db = db
