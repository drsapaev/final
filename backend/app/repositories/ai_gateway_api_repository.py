"""Repository helpers for ai gateway API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AiGatewayApiRepository:
    """Shared DB session adapter for ai gateway service."""

    def __init__(self, db: Session):
        self.db = db
