"""Repository helpers for integrations API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class IntegrationsApiRepository:
    """Shared DB session adapter for integrations service."""

    def __init__(self, db: Session):
        self.db = db
