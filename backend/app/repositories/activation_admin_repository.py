"""Repository helpers for activation admin endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activation import Activation, ActivationStatus


class ActivationAdminRepository:
    """Encapsulates Activation ORM operations for admin API layer."""

    def __init__(self, db: Session):
        self.db = db

    def list_activations(
        self,
        *,
        status: str | None,
        key_like: str | None,
        machine_hash: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Activation], int]:
        query = select(Activation).order_by(Activation.created_at.desc())
        if status:
            query = query.where(Activation.status == status)
        if key_like:
            query = query.where(Activation.key.ilike(f"%{key_like}%"))
        if machine_hash:
            query = query.where(Activation.machine_hash == machine_hash)

        total = (
            self.db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
        )
        rows = self.db.execute(query.limit(limit).offset(offset)).scalars().all()
        return rows, int(total)

    def get_by_key(self, key: str) -> Activation | None:
        return self.db.execute(select(Activation).where(Activation.key == key)).scalars().first()

    def revoke(self, row: Activation) -> Activation:
        row.status = ActivationStatus.REVOKED
        row.updated_at = datetime.utcnow()
        self.db.flush()
        self.db.commit()
        self.db.refresh(row)
        return row

    def extend(self, row: Activation, *, days: int) -> Activation:
        base = row.expiry_date or datetime.utcnow()
        row.expiry_date = base + timedelta(days=days)
        if row.status in (
            ActivationStatus.EXPIRED,
            ActivationStatus.ISSUED,
            ActivationStatus.TRIAL,
        ):
            row.status = ActivationStatus.ACTIVE
        row.updated_at = datetime.utcnow()
        self.db.flush()
        self.db.commit()
        self.db.refresh(row)
        return row

