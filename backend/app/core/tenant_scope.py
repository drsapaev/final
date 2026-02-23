from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TENANT_BRANCH_HEADER = "X-Branch-ID"


@dataclass(frozen=True)
class TenantScope:
    branch_id: int | None
    source: str


def parse_branch_id(raw_value: str | None) -> int | None:
    logger.debug(
        "tenant_scope.parse_branch_id.entry raw_value=%r",
        raw_value,
    )
    if raw_value is None:
        logger.debug("tenant_scope.parse_branch_id.exit branch_id=None source=missing")
        return None

    normalized = raw_value.strip()
    if not normalized:
        logger.debug("tenant_scope.parse_branch_id.exit branch_id=None source=empty")
        return None

    if not normalized.isdigit():
        logger.error(
            "tenant_scope.parse_branch_id.invalid_format raw_value=%r",
            raw_value,
        )
        raise ValueError("Branch ID must be a positive integer")

    branch_id = int(normalized)
    if branch_id <= 0:
        logger.error(
            "tenant_scope.parse_branch_id.invalid_range raw_value=%r",
            raw_value,
        )
        raise ValueError("Branch ID must be a positive integer")

    logger.debug(
        "tenant_scope.parse_branch_id.exit branch_id=%s source=header",
        branch_id,
    )
    return branch_id


def resolve_tenant_scope(
    header_branch_id: str | None = None,
    query_branch_id: int | None = None,
    user_branch_id: int | None = None,
) -> TenantScope:
    logger.debug(
        "tenant_scope.resolve_tenant_scope.entry header_branch_id=%r query_branch_id=%r user_branch_id=%r",
        header_branch_id,
        query_branch_id,
        user_branch_id,
    )
    header_scope = parse_branch_id(header_branch_id)
    if header_scope is not None:
        scope = TenantScope(branch_id=header_scope, source="header")
        logger.debug(
            "tenant_scope.resolve_tenant_scope.exit branch_id=%s source=%s",
            scope.branch_id,
            scope.source,
        )
        return scope

    if query_branch_id is not None:
        if query_branch_id <= 0:
            logger.error(
                "tenant_scope.resolve_tenant_scope.invalid_query_branch query_branch_id=%r",
                query_branch_id,
            )
            raise ValueError("Query branch_id must be a positive integer")
        scope = TenantScope(branch_id=query_branch_id, source="query")
        logger.debug(
            "tenant_scope.resolve_tenant_scope.exit branch_id=%s source=%s",
            scope.branch_id,
            scope.source,
        )
        return scope

    if user_branch_id is not None:
        if user_branch_id <= 0:
            logger.error(
                "tenant_scope.resolve_tenant_scope.invalid_user_branch user_branch_id=%r",
                user_branch_id,
            )
            raise ValueError("User branch_id must be a positive integer")
        scope = TenantScope(branch_id=user_branch_id, source="user")
        logger.debug(
            "tenant_scope.resolve_tenant_scope.exit branch_id=%s source=%s",
            scope.branch_id,
            scope.source,
        )
        return scope

    scope = TenantScope(branch_id=None, source="unset")
    logger.debug(
        "tenant_scope.resolve_tenant_scope.exit branch_id=%s source=%s",
        scope.branch_id,
        scope.source,
    )
    return scope


def require_branch_scope(scope: TenantScope) -> int:
    logger.debug(
        "tenant_scope.require_branch_scope.entry branch_id=%r source=%s",
        scope.branch_id,
        scope.source,
    )
    if scope.branch_id is None:
        logger.error(
            "tenant_scope.require_branch_scope.missing source=%s",
            scope.source,
        )
        raise ValueError("Branch scope is required for this operation")

    logger.debug(
        "tenant_scope.require_branch_scope.exit branch_id=%s",
        scope.branch_id,
    )
    return scope.branch_id
