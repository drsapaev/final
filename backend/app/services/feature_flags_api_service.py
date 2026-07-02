"""Service layer for feature_flags API endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.feature_flags import FeatureFlag
from app.repositories.feature_flags_api_repository import FeatureFlagsApiRepository
from app.services.feature_flags import FeatureFlagService, get_feature_flag_service


@dataclass
class FeatureFlagsApiDomainError(Exception):
    status_code: int
    detail: str


class FeatureFlagsApiService:
    """Orchestrates endpoint-level FeatureFlag operations."""

    def __init__(
        self,
        db: Session,
        repository: FeatureFlagsApiRepository | None = None,
        feature_service: FeatureFlagService | None = None,
    ):
        self.repository = repository or FeatureFlagsApiRepository(db)
        self.feature_service = feature_service or get_feature_flag_service(db)

    def get_flag_or_error(self, flag_key: str) -> FeatureFlag:
        flag = self.repository.get_by_key(flag_key)
        if not flag:
            raise FeatureFlagsApiDomainError(
                status_code=404,
                detail=f"Фича-флаг '{flag_key}' не найден",
            )
        return flag

    def ensure_flag_not_exists(self, flag_key: str) -> None:
        if self.repository.exists(flag_key):
            raise FeatureFlagsApiDomainError(
                status_code=400,
                detail=f"Фича-флаг с ключом '{flag_key}' уже существует",
            )

    def create_flag(
        self,
        *,
        key: str,
        name: str,
        description: str | None,
        enabled: bool,
        config: dict,
        category: str,
        environment: str,
        user_id: str,
    ) -> FeatureFlag:
        self.ensure_flag_not_exists(key)
        return self.feature_service.create_flag(
            key=key,
            name=name,
            description=description,
            enabled=enabled,
            config=config,
            category=category,
            environment=environment,
            user_id=user_id,
        )

    def update_flag(
        self,
        *,
        flag_key: str,
        name: str | None,
        description: str | None,
        category: str | None,
        environment: str | None,
        enabled: bool | None,
        config: dict | None,
        reason: str | None,
        user_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> FeatureFlag:
        flag = self.get_flag_or_error(flag_key)

        if name is not None:
            flag.name = name
        if description is not None:
            flag.description = description
        if category is not None:
            flag.category = category
        if environment is not None:
            flag.environment = environment

        if enabled is not None:
            self.feature_service.set_flag(
                flag_key=flag_key,
                enabled=enabled,
                user_id=user_id,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        if config is not None:
            self.feature_service.update_flag_config(
                flag_key=flag_key,
                config=config,
                user_id=user_id,
                reason=reason,
            )

        flag.updated_by = user_id
        return self.repository.save(flag)

    def rollback(self) -> None:
        self.repository.rollback()

