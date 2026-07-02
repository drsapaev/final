"""Repository helpers for feature_flags API endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.feature_flags import FeatureFlag


class FeatureFlagsApiRepository:
    """Encapsulates direct FeatureFlag ORM operations for endpoint service."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, flag_key: str) -> FeatureFlag | None:
        return self.db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()

    def exists(self, flag_key: str) -> bool:
        return self.get_by_key(flag_key) is not None

    def save(self, flag: FeatureFlag) -> FeatureFlag:
        self.db.commit()
        self.db.refresh(flag)
        return flag

    def rollback(self) -> None:
        self.db.rollback()

