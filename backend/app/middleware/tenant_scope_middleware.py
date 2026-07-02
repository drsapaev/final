from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.tenant_scope import (
    TENANT_BRANCH_HEADER,
    require_branch_scope,
    resolve_tenant_scope,
)

logger = logging.getLogger(__name__)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class TenantScopeMiddleware(BaseHTTPMiddleware):
    """
    Enforce branch scope on high-risk write routes during multi-clinic rollout.

    Guard is feature-flagged with `TENANT_SCOPE_ENFORCE_WRITES` and is no-op by default.
    """

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.enabled = settings.TENANT_SCOPE_ENFORCE_WRITES
        self.protected_prefixes = _parse_prefixes(settings.TENANT_SCOPE_WRITE_PREFIXES)

        logger.info(
            "tenant_scope_middleware.init enabled=%s prefixes=%s",
            self.enabled,
            self.protected_prefixes,
        )

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if not self.enabled:
            return await call_next(request)

        method = request.method.upper()
        path = request.url.path
        if method not in WRITE_METHODS or not _is_protected_path(
            path=path,
            prefixes=self.protected_prefixes,
        ):
            return await call_next(request)

        query_branch_id: int | None
        raw_query_branch_id = request.query_params.get("branch_id")
        if raw_query_branch_id is None:
            query_branch_id = None
        else:
            try:
                query_branch_id = int(raw_query_branch_id)
            except ValueError:
                logger.warning(
                    "tenant_scope_middleware.invalid_query_branch path=%s method=%s branch_id=%r",
                    path,
                    method,
                    raw_query_branch_id,
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Query branch_id must be a positive integer"},
                )

        user_branch_id = _extract_user_branch_id(request)
        try:
            scope = resolve_tenant_scope(
                header_branch_id=request.headers.get(TENANT_BRANCH_HEADER),
                query_branch_id=query_branch_id,
                user_branch_id=user_branch_id,
            )
            resolved_branch_id = require_branch_scope(scope)
        except ValueError as error:
            logger.warning(
                "tenant_scope_middleware.scope_rejected path=%s method=%s detail=%s",
                path,
                method,
                str(error),
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": str(error)},
            )

        request.state.tenant_scope = scope
        request.state.branch_id = resolved_branch_id
        logger.info(
            "tenant_scope_middleware.scope_applied path=%s method=%s branch_id=%s source=%s",
            path,
            method,
            resolved_branch_id,
            scope.source,
        )
        return await call_next(request)


def _parse_prefixes(raw_prefixes: str) -> tuple[str, ...]:
    prefixes = []
    for raw_prefix in raw_prefixes.split(","):
        prefix = raw_prefix.strip()
        if not prefix:
            continue
        normalized = prefix.rstrip("/") or "/"
        prefixes.append(normalized)

    # Keep order deterministic and remove duplicates.
    return tuple(dict.fromkeys(prefixes))


def _is_protected_path(path: str, prefixes: tuple[str, ...]) -> bool:
    for prefix in prefixes:
        if path == prefix or path.startswith(f"{prefix}/"):
            return True
    return False


def _extract_user_branch_id(request: Request) -> int | None:
    user_branch_id = getattr(request.state, "user_branch_id", None)
    if isinstance(user_branch_id, int):
        return user_branch_id

    branch_id = getattr(request.state, "branch_id", None)
    if isinstance(branch_id, int):
        return branch_id

    # Potential future fallback when authentication middleware attaches user object.
    user = getattr(request.state, "user", None)
    if user is not None:
        maybe_branch_id = getattr(user, "branch_id", None)
        if isinstance(maybe_branch_id, int):
            return maybe_branch_id

    return None
