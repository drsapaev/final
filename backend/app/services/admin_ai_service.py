"""Service layer for admin AI endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.admin_ai_repository import AdminAIRepository


class AdminAIService:
    """Orchestrates admin AI operations."""

    def __init__(
        self,
        db: Session,
        repository: AdminAIRepository | None = None,
    ):
        self.repository = repository or AdminAIRepository(db)

    def get_usage_logs(
        self,
        *,
        skip: int,
        limit: int,
        provider_id: int | None,
        task_type: str | None,
        success_only: bool | None,
    ):
        return self.repository.list_usage_logs(
            skip=skip,
            limit=limit,
            provider_id=provider_id,
            task_type=task_type,
            success_only=success_only,
        )

