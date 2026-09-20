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

Creation serializes against Nurse lifecycle writers on the SAME row
locks (review P2, round 2 — TOCTOU): ``create_assignment`` re-reads the
target User with ``SELECT ... FOR UPDATE`` and then the QueueResource
the same way BEFORE any eligibility decision. ``update_user()`` already
takes the users-row lock via ``lock_user_candidate_state(...)`` before
mutating ``users.role`` / ``users.is_active``; by sharing that lock the
eligibility read and the lifecycle commit become strictly linear —
either the assignment committed first (lifecycle change applies
afterwards to an already-created row) or the lifecycle change committed
first and create re-reads the NEW state and answers 400. A plain
(unlocked) read here used to pass stale eligibility and commit an ACTIVE
assignment for a user who is already a Registrar / deactivated — a state
the 0071 partial UNIQUE knows nothing about. The lock order is the
canonical one (users row first, then queue_resources row — the same
head element as the global order documented in patient_phone_scope) and
both locks are held until the INSERT commits. On SQLite (unit tests)
FOR UPDATE is a dialect no-op; the deterministic re-read
(``populate_existing``) still applies.

Deactivation keeps the row (inactive assignments are historical
records, not drift); a NEW active row for the same pair may be created
afterwards — exactly what the partial (WHERE is_active) uniqueness
permits. The active->inactive transition is a single guarded
``UPDATE ... WHERE is_active`` (review P2-1): two concurrent deactivate
calls cannot both observe ``is_active=True`` and both return 200 —
exactly one request flips the row; the loser gets rowcount=0 and
re-reads to decide 404 (row gone) vs 409 (row exists, already
inactive).

Error mapping: 404 = referenced entity not found; 400 = entity fails the
boundary validation (not a Nurse / deactivated user / inactive resource);
409 = conflict with the current state (duplicate active pair, assignment
already inactive).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import update
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

    def _lock_user_or_error(self, user_id: int) -> User:
        """Row-locked re-read of the target user (review P2, round 2).

        ``with_for_update()`` takes the SAME users-row lock that
        ``update_user()`` acquires via ``lock_user_candidate_state``
        before changing ``role`` / ``is_active`` — the eligibility
        decision computed from the returned instance therefore cannot
        interleave with a concurrent lifecycle commit (see the module
        docstring for the linearization contract).
        ``populate_existing()`` forces a fresh SELECT even when an
        instance for the row is already loaded in this session (and
        possibly stale after a concurrent writer committed first).
        On non-PG dialects (SQLite unit tests) the FOR UPDATE clause is
        a dialect no-op; the deterministic re-read remains.
        """
        user = (
            self.db.query(User)
            .filter(User.id == user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if user is None:
            raise NurseWorkplaceApiDomainError(
                404, f"Пользователь id={user_id} не найден"
            )
        return user

    def _lock_resource_or_error(self, queue_resource_id: int) -> QueueResource:
        """Row-locked re-read of the target QueueResource (review P2,
        round 2).

        Same serialization intent as ``_lock_user_or_error``: an
        in-flight resource deactivation must not be outrun by a stale
        eligibility read. Taken AFTER the users-row lock — the canonical
        order (users row first) shared with the user-management write
        paths; both locks are held until the assignment INSERT commits.
        """
        resource = (
            self.db.query(QueueResource)
            .filter(QueueResource.id == queue_resource_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
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
                    # D2 FINAL (review P2 round 3 — PR #3333): the resolved
                    # cabinet is NULL-coalesced (override ?? default), NOT
                    # truthiness-coalesced. The create schema normalizes ""
                    # to NULL at the write boundary; this explicit
                    # is-not-None check keeps the same D2 semantics for
                    # any hand-applied row so an N2-3 implementation that
                    # is D2-literal can never diverge from this surface.
                    "effective_cabinet": (
                        row.cabinet_override
                        if row.cabinet_override is not None
                        else default_cabinet
                    ),
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
        # Review P2 (round 2 — TOCTOU): every eligibility read below runs
        # UNDER the target row locks (users row, then queue_resources row)
        # and the locks stay held until the INSERT commits — a concurrent
        # Nurse deactivation / demotion via update_user() (which takes the
        # same users-row FOR UPDATE) can only be strictly BEFORE (this
        # request re-reads the new state and answers 400) or strictly AFTER
        # (the lifecycle change applies to an already-committed assignment).
        user = self._lock_user_or_error(user_id)
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

        resource = self._lock_resource_or_error(queue_resource_id)
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

    def _refetch(self, assignment_id: int) -> NurseWorkplaceAssignment | None:
        """Deterministic re-read that bypasses identity-map staleness.

        ``populate_existing()`` forces a fresh SELECT even when an
        instance for the row is already loaded in this session (and
        possibly stale after a concurrent writer committed first).
        """
        return (
            self.db.query(NurseWorkplaceAssignment)
            .filter(NurseWorkplaceAssignment.id == assignment_id)
            .populate_existing()
            .first()
        )

    def get_assignment(self, assignment_id: int) -> dict[str, Any]:
        row = self.db.get(NurseWorkplaceAssignment, assignment_id)
        if row is None:
            raise NurseWorkplaceApiDomainError(
                404, f"Назначение id={assignment_id} не найдено"
            )
        return self._enrich([row])[0]

    def deactivate_assignment(self, assignment_id: int) -> dict[str, Any]:
        # Atomic guarded transition (review P2-1): read-check-write here
        # would let two concurrent requests both observe is_active=True
        # and both return 200, violating the endpoint's 409 contract. A
        # single UPDATE with the is_active guard in the WHERE clause makes
        # the flip atomic at the row level; the loser sees rowcount=0 and
        # re-reads to distinguish 404 (row does not exist) from 409 (row
        # exists, already inactive).
        result = self.db.execute(
            update(NurseWorkplaceAssignment)
            .where(
                NurseWorkplaceAssignment.id == assignment_id,
                NurseWorkplaceAssignment.is_active.is_(True),
            )
            .values(is_active=False)
        )
        if result.rowcount == 0:
            # Nothing was flipped by THIS request: either the row is gone
            # (404) or a concurrent writer already deactivated it (409).
            self.db.rollback()
            row = self._refetch(assignment_id)
            if row is None:
                raise NurseWorkplaceApiDomainError(
                    404, f"Назначение id={assignment_id} не найдено"
                )
            raise NurseWorkplaceApiDomainError(
                409, f"Назначение id={assignment_id} уже неактивно"
            )
        self.db.commit()
        row = self._refetch(assignment_id)
        if row is None:  # pragma: no cover - just flipped by this request
            raise NurseWorkplaceApiDomainError(
                404, f"Назначение id={assignment_id} не найдено"
            )
        return self._enrich([row])[0]
