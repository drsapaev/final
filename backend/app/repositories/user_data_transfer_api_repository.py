"""Repository helpers for user data transfer API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class UserDataTransferApiRepository:
    """Shared DB session adapter for user data transfer service."""

    def __init__(self, db: Session):
        self.db = db
