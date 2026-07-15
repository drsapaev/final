"""
WebAuthn/Passkey API Endpoints — M4-P1-4 (Epic M4).

Endpoints for passkey registration, authentication, and management.
Returns 503 when webauthn library is not installed.

All endpoints require existing patient authentication (Telegram initData)
to bootstrap — passkey is registered as an alternative to Telegram.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.telegram_webhook._helpers import get_db, logger, Request

router = APIRouter(prefix="/webauthn", tags=["webauthn"])


def _check_webauthn_available():
    """Raise 503 if webauthn library is not installed."""
    from app.services.webauthn_service import is_webauthn_available
    if not is_webauthn_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "webauthn_not_configured", "message": "WebAuthn library is not installed. Contact administrator."},
        )


@router.post("/register/begin", operation_id="webauthn_register_begin")
def webauthn_register_begin(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Begin passkey registration (M4-P1-4).

    Requires existing patient authentication (initData in body).
    Returns WebAuthn registration options for navigator.credentials.create().
    """
    _check_webauthn_available()

    from app.services.webauthn_service import begin_passkey_registration
    from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
        _resolve_mini_app_patient_scope_from_auth,
    )

    try:
        body = request.json()
    except Exception:
        body = {}

    init_data = body.get("init_data") if isinstance(body, dict) else None
    if not init_data:
        raise HTTPException(status_code=400, detail={"reason": "init_data_required"})

    try:
        scope, _ = _resolve_mini_app_patient_scope_from_auth(
            db, init_data_payload=init_data, entry_token=None, expected_section="cabinet",
        )
    except Exception as exc:
        reason = getattr(exc, "reason", "auth_failed")
        raise HTTPException(status_code=403, detail={"reason": reason}) from exc

    rp_id = body.get("rp_id", "localhost")
    rp_name = body.get("rp_name", "Medical Clinic")
    credential_name = body.get("credential_name")

    try:
        options = begin_passkey_registration(
            db, scope.patient_id, rp_id=rp_id, rp_name=rp_name, credential_name=credential_name,
        )
        return {"options": options}
    except Exception as exc:
        logger.error("WebAuthn registration begin failed: %s", exc)
        raise HTTPException(status_code=500, detail={"reason": "registration_begin_failed"}) from exc


@router.post("/register/finish", operation_id="webauthn_register_finish")
def webauthn_register_finish(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Finish passkey registration (M4-P1-4).

    Verifies browser response and stores credential.
    """
    _check_webauthn_available()

    from app.services.webauthn_service import finish_passkey_registration
    from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
        _resolve_mini_app_patient_scope_from_auth,
    )

    try:
        body = request.json()
    except Exception:
        body = {}

    init_data = body.get("init_data")
    if not init_data:
        raise HTTPException(status_code=400, detail={"reason": "init_data_required"})

    try:
        scope, _ = _resolve_mini_app_patient_scope_from_auth(
            db, init_data_payload=init_data, entry_token=None, expected_section="cabinet",
        )
    except Exception as exc:
        raise HTTPException(status_code=403, detail={"reason": getattr(exc, "reason", "auth_failed")}) from exc

    credential_response = body.get("credential_response")
    if not credential_response:
        raise HTTPException(status_code=400, detail={"reason": "credential_response_required"})

    rp_id = body.get("rp_id", "localhost")
    origin = body.get("origin", "http://localhost:3000")
    credential_name = body.get("credential_name")

    try:
        credential = finish_passkey_registration(
            db, scope.patient_id,
            credential_response=credential_response,
            rp_id=rp_id, origin=origin,
            credential_name=credential_name,
        )
        return {
            "registered": True,
            "credential_id": credential.id,
            "name": credential.name,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"reason": str(exc)}) from exc
    except Exception as exc:
        logger.error("WebAuthn registration finish failed: %s", exc)
        raise HTTPException(status_code=500, detail={"reason": "registration_finish_failed"}) from exc


@router.post("/login/begin", operation_id="webauthn_login_begin")
def webauthn_login_begin(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Begin passkey authentication (M4-P1-4).

    Returns WebAuthn authentication options for navigator.credentials.get().
    """
    _check_webauthn_available()

    from app.services.webauthn_service import begin_passkey_authentication

    try:
        body = request.json()
    except Exception:
        body = {}

    patient_id = body.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=400, detail={"reason": "patient_id_required"})

    rp_id = body.get("rp_id", "localhost")

    try:
        options = begin_passkey_authentication(db, int(patient_id), rp_id=rp_id)
        return {"options": options}
    except Exception as exc:
        logger.error("WebAuthn auth begin failed: %s", exc)
        raise HTTPException(status_code=500, detail={"reason": "auth_begin_failed"}) from exc


@router.post("/login/finish", operation_id="webauthn_login_finish")
def webauthn_login_finish(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Finish passkey authentication (M4-P1-4).

    Verifies assertion and issues JWT.
    """
    _check_webauthn_available()

    from app.services.webauthn_service import finish_passkey_authentication

    try:
        body = request.json()
    except Exception:
        body = {}

    patient_id = body.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=400, detail={"reason": "patient_id_required"})

    assertion_response = body.get("assertion_response")
    if not assertion_response:
        raise HTTPException(status_code=400, detail={"reason": "assertion_response_required"})

    rp_id = body.get("rp_id", "localhost")
    origin = body.get("origin", "http://localhost:3000")

    try:
        result = finish_passkey_authentication(
            db, int(patient_id),
            assertion_response=assertion_response,
            rp_id=rp_id, origin=origin,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=403, detail={"reason": str(exc)}) from exc
    except Exception as exc:
        logger.error("WebAuthn auth finish failed: %s", exc)
        raise HTTPException(status_code=500, detail={"reason": "auth_finish_failed"}) from exc


@router.post("/credentials/list", operation_id="webauthn_list_credentials")
def webauthn_list_credentials(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List active passkeys for the authenticated patient (M4-P1-4)."""
    from app.services.webauthn_service import list_patient_passkeys
    from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
        _resolve_mini_app_patient_scope_from_auth,
    )

    try:
        body = request.json()
    except Exception:
        body = {}

    init_data = body.get("init_data")
    if not init_data:
        raise HTTPException(status_code=400, detail={"reason": "init_data_required"})

    try:
        scope, _ = _resolve_mini_app_patient_scope_from_auth(
            db, init_data_payload=init_data, entry_token=None, expected_section="cabinet",
        )
    except Exception as exc:
        raise HTTPException(status_code=403, detail={"reason": getattr(exc, "reason", "auth_failed")}) from exc

    passkeys = list_patient_passkeys(db, scope.patient_id)
    return {
        "credentials": [
            {
                "id": p.id,
                "name": p.name,
                "device_type": p.device_type,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
            }
            for p in passkeys
        ],
        "total": len(passkeys),
    }


@router.post("/credentials/{credential_id}/deactivate", operation_id="webauthn_deactivate_credential")
def webauthn_deactivate_credential(
    credential_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Deactivate a passkey (M4-P1-4)."""
    from app.services.webauthn_service import deactivate_passkey
    from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
        _resolve_mini_app_patient_scope_from_auth,
    )

    try:
        body = request.json()
    except Exception:
        body = {}

    init_data = body.get("init_data")
    if not init_data:
        raise HTTPException(status_code=400, detail={"reason": "init_data_required"})

    try:
        scope, _ = _resolve_mini_app_patient_scope_from_auth(
            db, init_data_payload=init_data, entry_token=None, expected_section="cabinet",
        )
    except Exception as exc:
        raise HTTPException(status_code=403, detail={"reason": getattr(exc, "reason", "auth_failed")}) from exc

    success = deactivate_passkey(db, scope.patient_id, credential_id)
    if not success:
        raise HTTPException(status_code=404, detail={"reason": "credential_not_found"})

    return {"deactivated": True, "credential_id": credential_id}
