"""Repository helpers for emr templates API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmrTemplatesApiRepository:
    """Shared DB session adapter for emr templates service."""

    def __init__(self, db: Session):
        self.db = db
