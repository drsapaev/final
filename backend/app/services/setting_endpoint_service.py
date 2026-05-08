"""Service layer for settings endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.setting_api_repository import SettingApiRepository


@dataclass
class SettingDomainError(Exception):
    status_code: int
    detail: str


class SettingService:
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
            raise SettingDomainError(status_code=500, detail=str(exc)) from exc
