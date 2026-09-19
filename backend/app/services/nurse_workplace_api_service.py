"""NURSE-V2 N2-2 — NurseWorkplaceAssignment admin API service.

Boundary validations (the assignment boundary of the track):
- the target user EXISTS, is ACTIVE and carries the canonical role
  'Nurse' (the user-management write vocabulary admits the spelling
  since N2-2 — anything else is not a Nurse account);
- the target QueueResource EXISTS and is ACTIVE (an inactive resource
  must not receive new assignments);
- at most ONE ACTIVE assignment per (user_id, queue_resource_id) pair
  (D2 FINAL) — a duplicate active pair is a 409 conflict; the DB-level
  guarantee is the migration-0071 partial unique index (PG), this check
  gives the API its deterministic, user-readable error.

Deactivation keeps the row (inactive assignments are historical
records, not drift); a NEW active row for the same pair may be created
afterwards — exactly what the partial (WHERE is_active) uniqueness
permits.

Error mapping: 404 = referenced entity not found; 400 = entity fails the
boundary validation (not a Nurse / deactivated user / inactive resource);
409 = conflict with the current state (duplicate active pair, assignment
already inactive).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.roles import normalize_role_value
from app.models.nurse_workplace import NurseWorkplaceAssignment
from app.models.online_queue import QueueResource
from app.models.user import User

NURSE_ROLE_NORMALIZED = "nurse"


class NurseWorkplaceApiDomainError(Exception):
    """Domain error carrying an HTTP status and a user-readable detail."""

    status_code: int
    detail: str

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class NurseWorkplaceApiService:
    """Create/read/deactivate Nurse workplace assignments (admin contract)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------- helpers ----------------

    def _get_user_or_error(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise NurseWorkplaceApiDomainError(
                404, f"Пользователь id={user_id} не найден"
            )
        return user

    def _get_resource_or_error(self, queue_resource_id: int) -> QueueResource:
        resource = self.db.get(QueueResource, queue_resource_id)
        if resource is None:
            raise NurseWorkplaceApiDomainError(
                404, f"QueueResource id={queue_resource_id} не найден"
            )
        return resource

    def _enrich(self, rows: list[NurseWorkplaceAssignment]) -> list[dict[str, Any]]:
        """Build response-ready dicts with user/resource mirror fields."""
        user_ids = {row.user_id for row in rows}
        resource_ids = {row.queue_resource_id for row in rows}
        users: dict[int, User] = {}
        resources: dict[int, QueueResource] = {}
        if user_ids:
            users = {u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids))}
        if resource_ids:
            resources = {
                r.id: r
                for r in self.db.query(QueueResource).filter(
                    QueueResource.id.in_(resource_ids)
                )
            }
        items: list[dict[str, Any]] = []
        for row in rows:
            user = users.get(row.user_id)
            resource = resources.get(row.queue_resource_id)
            default_cabinet = resource.default_cabinet if resource is not None else None
            items.append(
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "queue_resource_id": row.queue_resource_id,
                    "cabinet_override": row.cabinet_override,
                    "is_active": row.is_active,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "user_username": user.username if user else None,
                    "user_full_name": user.full_name if user else None,
                    "resource_code": resource.code if resource else None,
                    "resource_display_name": (
                        resource.display_name if resource else None
                    ),
                    "resource_queue_tag": (resource.queue_tag if resource else None),
                    "resource_default_cabinet": default_cabinet,
                    "effective_cabinet": row.cabinet_override or default_cabinet,
                }
            )
        return items

    # ---------------- operations ----------------

    def create_assignment(
        self,
        *,
        user_id: int,
        queue_resource_id: int,
        cabinet_override: str | None,
    ) -> dict[str, Any]:
        user = self._get_user_or_error(user_id)
        if not bool(getattr(user, "is_active", False)):
            raise NurseWorkplaceApiDomainError(
                400, f"Пользователь id={user_id} деактивирован"
            )
        if normalize_role_value(getattr(user, "role", None)) != NURSE_ROLE_NORMALIZED:
            raise NurseWorkplaceApiDomainError(
                400,
                f"Пользователь id={user_id} не имеет роли Nurse "
                f"(role={getattr(user, 'role', None)!r})",
            )

        resource = self._get_resource_or_error(queue_resource_id)
        if not bool(getattr(resource, "active", False)):
            raise NurseWorkplaceApiDomainError(
                400, f"QueueResource id={queue_resource_id} неактивен"
            )

        duplicate = (
            self.db.query(NurseWorkplaceAssignment)
            .filter(
                NurseWorkplaceAssignment.user_id == user_id,
                NurseWorkplaceAssignment.queue_resource_id == queue_resource_id,
                NurseWorkplaceAssignment.is_active.is_(True),
            )
            .first()
        )
        if duplicate is not None:
            raise NurseWorkplaceApiDomainError(
                409,
                f"Активное назначение пары (user_id={user_id}, "
                f"queue_resource_id={queue_resource_id}) уже существует "
                f"(id={duplicate.id})",
            )

        assignment = NurseWorkplaceAssignment(
            user_id=user_id,
            queue_resource_id=queue_resource_id,
            cabinet_override=cabinet_override,
            is_active=True,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return self._enrich([assignment])[0]

    def list_assignments(
        self,
        *,
        user_id: int | None = None,
        queue_resource_id: int | None = None,
        active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        query = self.db.query(NurseWorkplaceAssignment)
        if user_id is not None:
            query = query.filter(NurseWorkplaceAssignment.user_id == user_id)
        if queue_resource_id is not None:
            query = query.filter(
                NurseWorkplaceAssignment.queue_resource_id == queue_resource_id
            )
        if active is not None:
            query = query.filter(NurseWorkplaceAssignment.is_active.is_(active))
        total = query.count()
        rows = (
            query.order_by(
                NurseWorkplaceAssignment.is_active.desc(),
                NurseWorkplaceAssignment.id.desc(),
            )
            .limit(limit)
            .offset(offset)
            .all()
        )
        return self._enrich(rows), total

    def get_assignment(self, assignment_id: int) -> dict[str, Any]:
        row = self.db.get(NurseWorkplaceAssignment, assignment_id)
        if row is None:
            raise NurseWorkplaceApiDomainError(
                404, f"Назначение id={assignment_id} не найдено"
            )
        return self._enrich([row])[0]

    def deactivate_assignment(self, assignment_id: int) -> dict[str, Any]:
        row = self.db.get(NurseWorkplaceAssignment, assignment_id)
        if row is None:
            raise NurseWorkplaceApiDomainError(
                404, f"Назначение id={assignment_id} не найдено"
            )
        if not row.is_active:
            raise NurseWorkplaceApiDomainError(
                409, f"Назначение id={assignment_id} уже неактивно"
            )
        row.is_active = False
        self.db.commit()
        self.db.refresh(row)
        return self._enrich([row])[0]
