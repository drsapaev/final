"""Repository helpers for emr export API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class EmrExportApiRepository:
    """Shared DB session adapter for emr export service."""

    def __init__(self, db: Session):
        self.db = db
