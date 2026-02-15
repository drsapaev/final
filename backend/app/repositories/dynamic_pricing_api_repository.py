"""Repository helpers for dynamic pricing API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DynamicPricingApiRepository:
    """Shared DB session adapter for dynamic pricing service."""

    def __init__(self, db: Session):
        self.db = db
