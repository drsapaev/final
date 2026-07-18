"""
Admin Security Endpoints — M5.6/M5.8/M5.9/M5.10 integration.

4 admin-facing endpoints:
- GET  /admin/security/dashboard — aggregated security view
- GET  /admin/compliance/report — automated compliance checklist
- GET  /admin/secrets/status — secrets rotation status
- POST /admin/backup/verify — record backup verification
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.authorization.staff import staff_authorization_service

router = APIRouter(prefix="/admin/security", tags=["admin-security"])


def _require_security_admin(current_user: User = Depends(deps.get_current_user)) -> User:
    """Require security:dashboard permission (admin only)."""
    if not staff_authorization_service.can_view_security_dashboard(current_user):
        raise HTTPException(status_code=403, detail={"reason": "access_denied"})
    return current_user


@router.get("/dashboard", operation_id="admin_security_dashboard")
def security_dashboard(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_require_security_admin),
):
    """M5.6: Security dashboard — recent logins, downloads, suspicious IPs."""
    from app.services.security_dashboard import get_security_dashboard
    return get_security_dashboard(db, hours=24)


@router.get("/compliance/report", operation_id="admin_compliance_report")
def compliance_report(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_require_security_admin),
):
    """M5.10: Automated compliance report — 8 checks."""
    from app.services.compliance_report import get_compliance_report
    return get_compliance_report(db)


@router.get("/secrets/status", operation_id="admin_secrets_status")
def secrets_status(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_require_security_admin),
):
    """M5.8: Secrets rotation status."""
    from app.services.secrets_rotation import get_secrets_rotation_status
    return get_secrets_rotation_status(db)


@router.post("/backup/verify", operation_id="admin_backup_verify")
def backup_verify(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_require_security_admin),
):
    """M5.9: Record a backup verification event."""
    from app.services.backup_audit import record_backup_event
    try:
        body = request.json()
    except Exception:
        body = {}
    backup_status = body.get("status", "verified") if isinstance(body, dict) else "verified"
    notes = body.get("notes") if isinstance(body, dict) else None

    record_backup_event(
        db=db,
        status=backup_status,
        performed_by=current_user.id,
        notes=notes,
    )
    return {"recorded": True, "status": backup_status}


@router.get("/backup/status", operation_id="admin_backup_status")
def backup_status(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(_require_security_admin),
):
    """M5.9: Check backup status."""
    from app.services.backup_audit import get_backup_status
    return get_backup_status(db)
