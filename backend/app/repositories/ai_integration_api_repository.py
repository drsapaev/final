"""Repository helpers for ai integration API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AiIntegrationApiRepository:
    """Shared DB session adapter for ai integration service."""

    def __init__(self, db: Session):
        self.db = db
