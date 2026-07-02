"""Repository helpers for webhooks API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class WebhooksApiRepository:
    """Shared DB session adapter for webhooks service."""

    def __init__(self, db: Session):
        self.db = db
