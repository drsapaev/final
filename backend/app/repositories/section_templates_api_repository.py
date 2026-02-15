"""Repository helpers for section templates API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SectionTemplatesApiRepository:
    """Shared DB session adapter for section templates service."""

    def __init__(self, db: Session):
        self.db = db
