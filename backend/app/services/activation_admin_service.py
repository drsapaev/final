"""Service layer for activation admin endpoints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.activation_admin_repository import ActivationAdminRepository
from app.schemas.activation import ActivationListRow


class ActivationAdminService:
    """Orchestrates activation list/revoke/extend operations."""

    def __init__(
        self,
        db: Session,
        repository: ActivationAdminRepository | None = None,
    ):
        self.repository = repository or ActivationAdminRepository(db)

    @staticmethod
    def _to_list_row(row) -> ActivationListRow:  # type: ignore[no-untyped-def]
        return ActivationListRow(
            key=row.key,
            machine_hash=row.machine_hash,
            expiry_date=row.expiry_date.strftime("%Y-%m-%d") if row.expiry_date else None,
            status=row.status,
            created_at=(row.created_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S"),
            updated_at=(row.updated_at or row.created_at or datetime.utcnow()).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            meta=row.meta,
        )

    def list_activations(
        self,
        *,
        status: str | None,
        key_like: str | None,
        machine_hash: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ActivationListRow], int]:
        rows, total = self.repository.list_activations(
            status=status,
            key_like=key_like,
            machine_hash=machine_hash,
            limit=limit,
            offset=offset,
        )
        return [self._to_list_row(row) for row in rows], total

    def revoke(self, *, key: str) -> bool:
        row = self.repository.get_by_key(key)
        if not row:
            return False
        self.repository.revoke(row)
        return True

    def extend(self, *, key: str, days: int):
        row = self.repository.get_by_key(key)
        if not row:
            return None
        return self.repository.extend(row, days=days)

