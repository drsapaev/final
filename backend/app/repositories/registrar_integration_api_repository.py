"""Repository helpers for registrar integration API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class RegistrarIntegrationApiRepository:
    """Shared DB session adapter for registrar integration service."""

    def __init__(self, db: Session):
        self.db = db
