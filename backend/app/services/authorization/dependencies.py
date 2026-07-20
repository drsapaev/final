"""
FastAPI dependencies for PHI access authorization (M4-P1-1).

Usage:
    from app.services.authorization.dependencies import require_phi_access

    @router.post("/mini-app/reports/download")
    def download_report(
        request_body: ...,
        request: Request,
        db: Session = Depends(get_db),
    ):
        scope = resolve_scope_from_request(request_body, db)
        # Authorization check:
        require_phi_access(
            resource_type="lab_report",
            action="download",
            subject_patient_id=scope.patient_id,
        )(scope=scope)
        ...
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.authorization import (
    AuthorizationError,
    AuthorizationService,
    authorization_service,
)

if TYPE_CHECKING:
    from app.services.telegram_mini_app_init_data import TelegramMiniAppSessionScope


def check_phi_access(
    scope: "TelegramMiniAppSessionScope",
    *,
    subject_patient_id: int,
    resource_type: str,
    action: str,
    resource_id: str | None = None,
) -> "TelegramMiniAppSessionScope":
    """Check if scope can access PHI, raise AuthorizationError if denied.

    M4-P1-1: Centralized authorization check. Replaces scattered
    require_telegram_mini_app_patient_scope + inline patient_id checks.

    Args:
        scope: TelegramMiniAppSessionScope (patient or staff)
        subject_patient_id: Patient whose PHI is being accessed
        resource_type: One of ResourceType values
        action: One of Action values
        resource_id: Optional specific resource ID

    Returns:
        scope if access is allowed

    Raises:
        AuthorizationError: if access is denied
    """
    return authorization_service.require_phi_access(
        scope,
        subject_patient_id=subject_patient_id,
        resource_type=resource_type,
        action=action,
        resource_id=resource_id,
    )


def can_access_phi(
    scope: "TelegramMiniAppSessionScope",
    *,
    subject_patient_id: int,
    resource_type: str,
    action: str,
    resource_id: str | None = None,
) -> bool:
    """Non-raising version of check_phi_access. Returns True/False."""
    result = authorization_service.can_access_phi(
        scope,
        subject_patient_id=subject_patient_id,
        resource_type=resource_type,
        action=action,
        resource_id=resource_id,
    )
    return result.allowed
