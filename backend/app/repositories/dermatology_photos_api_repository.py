"""Repository helpers for dermatology photos API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DermatologyPhotosApiRepository:
    """Shared DB session adapter for dermatology photos service."""

    def __init__(self, db: Session):
        self.db = db
