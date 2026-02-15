"""Repository helpers for emr v2 API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmrV2ApiRepository:
    """Shared DB session adapter for emr v2 service."""

    def __init__(self, db: Session):
        self.db = db
