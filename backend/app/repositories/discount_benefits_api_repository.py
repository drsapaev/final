"""Repository helpers for discount benefits API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DiscountBenefitsApiRepository:
    """Shared DB session adapter for discount benefits service."""

    def __init__(self, db: Session):
        self.db = db
