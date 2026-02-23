"""Repository helpers for clinic management API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class ClinicManagementApiRepository:
    """Shared DB session adapter for clinic management service."""

    def __init__(self, db: Session):
        self.db = db
