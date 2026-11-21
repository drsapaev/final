"""Internal Registrar tab registry endpoints (separate from queue commands)."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.schemas.registrar_tabs import (
    AdminRegistrarTabsOut,
    RegistrarTabsErrorResponse,
    RegistrarTabsOut,
    RegistrarTabsUpdate,
    RegistrarTabsValidationResponse,
)
from app.services.registrar_tabs import RegistrarTabsError, RegistrarTabsService

from ._helpers import router

logger = logging.getLogger(__name__)
_ERROR_RESPONSES = {code: {"model": RegistrarTabsErrorResponse} for code in (409, 503)}
_ERROR_RESPONSES[422] = {"model": RegistrarTabsValidationResponse}


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RegistrarTabsError):
        logger.warning("Registrar tab operation refused code=%s", exc.code)
        return HTTPException(status_code=exc.status_code, detail={"code": exc.code})
    logger.error("Registrar tab operation failed error_type=%s", type(exc).__name__)
    return HTTPException(
        status_code=500, detail={"code": "registrar_tabs_internal_error"}
    )


@router.get(
    "/registrar/tabs", response_model=RegistrarTabsOut, responses=_ERROR_RESPONSES
)
def get_registrar_tabs(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Doctor", "Cashier", "Lab")
    ),
) -> RegistrarTabsOut:
    try:
        return RegistrarTabsService(db).read()
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.get(
    "/admin/registrar-tabs",
    response_model=AdminRegistrarTabsOut,
    responses=_ERROR_RESPONSES,
)
def get_admin_registrar_tabs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> AdminRegistrarTabsOut:
    try:
        return AdminRegistrarTabsOut.model_validate(
            RegistrarTabsService(db).read(admin=True)
        )
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.put(
    "/admin/registrar-tabs",
    response_model=AdminRegistrarTabsOut,
    responses=_ERROR_RESPONSES,
)
def update_admin_registrar_tabs(
    update: RegistrarTabsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> AdminRegistrarTabsOut:
    # Middleware creates a UUID; never copy arbitrary headers or query data
    # to the mandatory audit payload.
    try:
        request_id = str(UUID(str(getattr(request.state, "request_id", ""))))
    except (ValueError, TypeError, AttributeError):
        request_id = str(uuid4())
    try:
        return RegistrarTabsService(db).update(
            update,
            actor_user_id=current_user.id,
            actor_role=str(current_user.role),
            request_id=request_id,
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
