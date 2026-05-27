"""Service layer for settings API endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.setting_api_repository import SettingApiRepository

logger = logging.getLogger(__name__)


@dataclass
class SettingApiDomainError(Exception):
    status_code: int
    detail: str


class SettingApiService:
    """Orchestrates setting endpoint operations."""

    def __init__(
        self,
        db: Session,
        repository: SettingApiRepository | None = None,
    ):
        self.repository = repository or SettingApiRepository(db)

    def get_settings(self, *, category: str):
        try:
            return self.repository.list_by_category(category=category)
        except Exception as exc:
            logger.warning(
                "Setting list query failed error_type=%s",
                type(exc).__name__,
            )
            raise SettingApiDomainError(
                status_code=500,
                detail="Internal server error",
            ) from exc

    def upsert_setting(self, *, category: str, key: str, value: str):
        try:
            return self.repository.upsert(category=category, key=key, value=value)
        except Exception as exc:
            logger.warning(
                "Setting upsert failed error_type=%s",
                type(exc).__name__,
            )
            raise SettingApiDomainError(
                status_code=500,
                detail="Internal server error",
            ) from exc
