"""Repository helpers for billing API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class BillingApiRepository:
    """Shared DB session adapter for billing service."""

    def __init__(self, db: Session):
        self.db = db
