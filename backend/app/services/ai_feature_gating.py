"""
Feature flag helper for AI endpoints.

Usage in an AI endpoint:

    from app.services.ai_feature_gating import require_ai_feature

    @router.post("/analyze-complaints")
    def analyze_complaints(
        ...,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_ai_permission(AIPermission.DIAGNOSE)),
    ):
        require_ai_feature(db, "ai_complaint_analysis")
        # ... rest of endpoint

If the flag is disabled, this raises HTTPException(503) with a clear message.
This lets admins kill any AI feature instantly without a code deploy —
critical for medical systems where a misbehaving AI must be stoppable.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services.feature_flags import get_feature_flag_service


def is_ai_feature_enabled(db: Session, flag_key: str) -> bool:
    """Check if an AI feature flag is enabled. Returns True if flag is missing
    (fail-open) — feature flags are an explicit disable, not an explicit enable.
    Missing flag = feature is on by default.
    """
    service = get_feature_flag_service(db)
    return service.is_enabled(flag_key)


def require_ai_feature(db: Session, flag_key: str) -> None:
    """Raise HTTPException(503) if the AI feature flag is disabled.

    Use this at the top of any AI endpoint that should be admin-toggleable.

    Fail-open policy: if the flag doesn't exist in the DB (e.g. before
    seed_ai_feature_flags.py has been run), the endpoint proceeds normally.
    This avoids breaking prod on first deploy.
    """
    if not is_ai_feature_enabled(db, flag_key):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "feature_disabled",
                "flag": flag_key,
                "message": (
                    f"AI feature '{flag_key}' is currently disabled by the administrator. "
                    "Contact the clinic admin to re-enable."
                ),
            },
        )


def get_ai_feature_config(db: Session, flag_key: str) -> dict:
    """Get the config dict for an AI feature flag. Empty dict if missing."""
    service = get_feature_flag_service(db)
    return service.get_flag_config(flag_key) or {}
