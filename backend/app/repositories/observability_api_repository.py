"""Repository helpers for observability API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class ObservabilityApiRepository:
    """Shared DB session adapter for observability service."""

    def __init__(self, db: Session):
        self.db = db
