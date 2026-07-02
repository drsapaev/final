"""Repository helpers for mcp API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class McpApiRepository:
    """Shared DB session adapter for mcp service."""

    def __init__(self, db: Session):
        self.db = db
