"""
Схемы для версий EMR
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import ORMModel


class EMRVersionBase(ORMModel):
    """Базовая схема версии EMR"""

    emr_id: int
    version_number: int
    data: dict[str, Any]
    change_type: str = Field(..., max_length=50)  # created, updated, deleted
    change_description: str | None = Field(None, max_length=1000)
    changed_by: int
    is_current: bool = False


class EMRVersionCreate(EMRVersionBase):
    """Схема создания версии EMR"""

    created_at: datetime = Field(default_factory=datetime.utcnow)


class EMRVersionUpdate(ORMModel):
    """Схема обновления версии EMR"""

    change_description: str | None = Field(None, max_length=1000)
    is_current: bool | None = None


class EMRVersionOut(EMRVersionBase):
    """Схема вывода версии EMR"""

    id: int
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_orm = True


class EMRVersionComparison(ORMModel):
    """Схема сравнения версий EMR"""

    version1_id: int
    version2_id: int
    fields_changed: list[str]
    changes: dict[str, dict[str, Any]]
    summary: dict[str, Any]


class EMRVersionTimeline(ORMModel):
    """Схема временной линии версий EMR"""

    versions: list[EMRVersionOut]
    total_versions: int
    current_version_id: int | None = None


class EMRVersionStatistics(ORMModel):
    """Схема статистики версий EMR"""

    total_versions: int
    versions_by_type: dict[str, int]
    recent_changes: list[EMRVersionOut]
    most_active_users: list[dict[str, Any]]
