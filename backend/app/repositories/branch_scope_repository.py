from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BranchScopeRequiredError(ValueError):
    """Raised when operation requires a branch scope but none was provided."""


class BranchScopeViolationError(PermissionError):
    """Raised when an entity or request branch scope violates isolation rules."""


def require_branch_scope_id(branch_id: int | None, *, source: str) -> int:
    logger.debug(
        "branch_scope_repository.require_branch_scope_id.entry source=%s branch_id=%r",
        source,
        branch_id,
    )
    if branch_id is None:
        logger.error(
            "branch_scope_repository.require_branch_scope_id.missing source=%s",
            source,
        )
        raise BranchScopeRequiredError("Branch scope is required")

    if branch_id <= 0:
        logger.error(
            "branch_scope_repository.require_branch_scope_id.invalid source=%s branch_id=%r",
            source,
            branch_id,
        )
        raise BranchScopeRequiredError("Branch scope must be a positive integer")

    logger.debug(
        "branch_scope_repository.require_branch_scope_id.exit source=%s branch_id=%s",
        source,
        branch_id,
    )
    return branch_id


def resolve_scoped_branch_id(
    *,
    request_branch_id: int | None = None,
    explicit_branch_id: int | None = None,
    require_scope: bool = False,
) -> int | None:
    logger.debug(
        "branch_scope_repository.resolve_scoped_branch_id.entry request_branch_id=%r explicit_branch_id=%r require_scope=%s",
        request_branch_id,
        explicit_branch_id,
        require_scope,
    )

    if request_branch_id is not None and request_branch_id <= 0:
        raise BranchScopeRequiredError("Request branch scope must be a positive integer")
    if explicit_branch_id is not None and explicit_branch_id <= 0:
        raise BranchScopeRequiredError("Explicit branch scope must be a positive integer")

    if (
        request_branch_id is not None
        and explicit_branch_id is not None
        and request_branch_id != explicit_branch_id
    ):
        logger.error(
            "branch_scope_repository.resolve_scoped_branch_id.mismatch request_branch_id=%s explicit_branch_id=%s",
            request_branch_id,
            explicit_branch_id,
        )
        raise BranchScopeViolationError(
            "Explicit branch scope conflicts with request branch scope"
        )

    resolved = explicit_branch_id if explicit_branch_id is not None else request_branch_id
    if require_scope:
        return require_branch_scope_id(resolved, source="resolved-branch-scope")

    logger.debug(
        "branch_scope_repository.resolve_scoped_branch_id.exit resolved=%r",
        resolved,
    )
    return resolved


def ensure_entity_within_branch_scope(
    *,
    entity_branch_id: int | None,
    scoped_branch_id: int,
    entity_name: str,
    entity_id: int | None = None,
) -> None:
    logger.debug(
        "branch_scope_repository.ensure_entity_within_branch_scope.entry entity=%s entity_id=%r entity_branch_id=%r scoped_branch_id=%s",
        entity_name,
        entity_id,
        entity_branch_id,
        scoped_branch_id,
    )
    branch_scope_id = require_branch_scope_id(
        scoped_branch_id,
        source=f"{entity_name}-scope",
    )
    if entity_branch_id is None:
        raise BranchScopeViolationError(
            f"{entity_name} has no branch_id and cannot be checked against scope"
        )
    if entity_branch_id != branch_scope_id:
        raise BranchScopeViolationError(
            f"{entity_name} is outside branch scope (entity_branch_id={entity_branch_id}, scope={branch_scope_id})"
        )

    logger.debug(
        "branch_scope_repository.ensure_entity_within_branch_scope.exit entity=%s entity_id=%r scope=%s",
        entity_name,
        entity_id,
        branch_scope_id,
    )
