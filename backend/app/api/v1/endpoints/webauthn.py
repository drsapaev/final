"""
WebAuthn/Passkey API Endpoints — M4-P1-4 (Epic M4).

Endpoints for passkey registration, authentication, and management.
Returns 503 when webauthn library is not installed.

Management requires a linked active Patient User; mutations additionally
require a fresh, single-use patient OTP grant.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, oauth2_scheme
from app.api.v1.endpoints.telegram_webhook._helpers import get_db, logger
from app.core.config import settings
from app.models.patient import Patient
from app.models.user import User

router = APIRouter(prefix="/webauthn", tags=["webauthn"])

# WEBAUTHN-BE-002 (#4063): the login plane is unauthenticated — IP-throttle it
from app.core.rate_limiter import get_client_ip, limiter  # noqa: E402

_STEP_UP_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["phone", "verification_grant"],
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Verified phone of the authenticated patient",
                        },
                        "verification_grant": {
                            "type": "string",
                            "description": "Single-use patient OTP grant",
                        },
                    },
                }
            }
        },
    }
}
_REGISTRATION_FINISH_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["ceremony_id", "credential_response"],
                    "properties": {
                        "ceremony_id": {"type": "string"},
                        "credential_response": {
                            "type": "object",
                            "additionalProperties": True,
                            "required": ["id", "rawId", "type", "response"],
                            "properties": {
                                "id": {"type": "string"},
                                "rawId": {"type": "string"},
                                "type": {"type": "string"},
                                "response": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "required": ["attestationObject", "clientDataJSON"],
                                    "properties": {
                                        "attestationObject": {"type": "string"},
                                        "clientDataJSON": {"type": "string"},
                                    },
                                },
                            },
                        },
                        "credential_name": {
                            "type": ["string", "null"],
                            "maxLength": 100,
                        },
                    },
                }
            }
        },
    }
}
_AUTH_RESPONSES = {
    401: {"description": "Authentication required or invalid session"},
    403: {"description": "Patient identity or step-up rejected"},
}
_MUTATION_RESPONSES = {
    **_AUTH_RESPONSES,
    400: {"description": "Invalid or missing request data"},
    429: {"description": "Too many requests"},
    503: {"description": "Authentication service temporarily unavailable"},
}
_REGISTRATION_BEGIN_RESPONSE = {
    "description": "Registration ceremony options",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["options"],
                "properties": {
                    "options": {
                        "type": "object",
                        "required": ["challenge", "ceremony_id", "rp", "user"],
                        "properties": {
                            "challenge": {"type": "string"},
                            "ceremony_id": {"type": "string"},
                            "rp": {
                                "type": "object",
                                "required": ["id", "name"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                            "user": {
                                "type": "object",
                                "required": ["id", "name", "displayName"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "displayName": {"type": "string"},
                                },
                            },
                        },
                    }
                },
            }
        }
    },
}
_REGISTRATION_FINISH_RESPONSE = {
    "description": "Registered credential",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["registered", "credential_id", "name"],
                "properties": {
                    "registered": {"type": "boolean"},
                    "credential_id": {"type": "integer"},
                    "name": {"type": ["string", "null"]},
                },
            }
        }
    },
}
_LIST_RESPONSE = {
    "description": "Active credentials for the current patient",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["credentials", "total"],
                "properties": {
                    "credentials": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "id",
                                "name",
                                "device_type",
                                "created_at",
                                "last_used_at",
                            ],
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": ["string", "null"]},
                                "device_type": {"type": ["string", "null"]},
                                "created_at": {"type": ["string", "null"]},
                                "last_used_at": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "total": {"type": "integer"},
                },
            }
        }
    },
}
_DEACTIVATE_RESPONSE = {
    "description": "Credential deactivated",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["deactivated", "credential_id"],
                "properties": {
                    "deactivated": {"type": "boolean"},
                    "credential_id": {"type": "integer"},
                },
            }
        }
    },
}

_DISCOVERABLE_BEGIN_BODY = {
    "requestBody": {
        "required": False,
        "content": {
            "application/json": {
                "schema": {"type": "object", "additionalProperties": False}
            }
        },
    }
}
_DISCOVERABLE_FINISH_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["ceremony_id", "assertion_response"],
                    "properties": {
                        "ceremony_id": {"type": "string"},
                        "assertion_response": {
                            "type": "object",
                            "additionalProperties": True,
                            "required": ["id", "rawId", "type", "response"],
                            "properties": {
                                "id": {"type": "string"},
                                "rawId": {"type": "string"},
                                "type": {"type": "string"},
                                "response": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "required": [
                                        "authenticatorData",
                                        "clientDataJSON",
                                        "signature",
                                    ],
                                    "properties": {
                                        "authenticatorData": {"type": "string"},
                                        "clientDataJSON": {"type": "string"},
                                        "signature": {"type": "string"},
                                        "userHandle": {"type": ["string", "null"]},
                                    },
                                },
                            },
                        },
                    },
                }
            }
        },
    }
}
_DISCOVERABLE_ERRORS = {
    code: {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["detail"],
                    "properties": {
                        "detail": {
                            "type": "object",
                            "required": ["reason"],
                            "properties": {"reason": {"type": "string"}},
                            "additionalProperties": True,
                        }
                    },
                }
            }
        },
    }
    for code, description in {
        403: "Authentication rejected",
        429: "Too many attempts",
        503: "Authentication service unavailable",
    }.items()
}
_DISCOVERABLE_BEGIN_RESPONSE = {
    "description": "Discoverable login options",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["options"],
                "properties": {
                    "options": {
                        "type": "object",
                        "required": [
                            "challenge",
                            "ceremony_id",
                            "rpId",
                            "timeout",
                            "userVerification",
                        ],
                        "properties": {
                            "challenge": {"type": "string"},
                            "ceremony_id": {"type": "string"},
                            "rpId": {"type": "string"},
                            "timeout": {"type": "integer"},
                            "userVerification": {"type": "string"},
                        },
                    }
                },
            }
        }
    },
}
_DISCOVERABLE_NEXT_RESPONSE = {
    "description": "Second user-verified assertion required",
    "headers": {
        "Cache-Control": {
            "required": True,
            "schema": {"type": "string", "const": "no-store"},
        }
    },
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["next_options"],
                "properties": {
                    "next_options": {
                        "type": "object",
                        "required": [
                            "challenge",
                            "ceremony_id",
                            "rpId",
                            "timeout",
                            "userVerification",
                            "allowCredentials",
                        ],
                        "properties": {
                            "challenge": {"type": "string"},
                            "ceremony_id": {"type": "string"},
                            "rpId": {"type": "string"},
                            "timeout": {"type": "integer"},
                            "userVerification": {"type": "string", "const": "required"},
                            "allowCredentials": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 1,
                                "items": {
                                    "type": "object",
                                    "required": ["type", "id"],
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "const": "public-key",
                                        },
                                        "id": {"type": "string"},
                                    },
                                },
                            },
                        },
                    }
                },
            }
        }
    },
}


_DISCOVERABLE_FINISH_RESPONSE = {
    "description": "Patient access session",
    "headers": {
        "Cache-Control": {
            "required": True,
            "schema": {"type": "string", "const": "no-store"},
        }
    },
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["access_token", "token_type", "user"],
                "additionalProperties": False,
                "properties": {
                    "access_token": {"type": "string"},
                    "token_type": {"type": "string"},
                    "user": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": [
                            "id",
                            "username",
                            "role",
                            "is_active",
                            "is_superuser",
                        ],
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                            "role": {"type": "string"},
                            "is_active": {"type": "boolean"},
                            "is_superuser": {"type": "boolean"},
                        },
                    },
                },
            }
        }
    },
}


# Final assertions can yield an access session or a restricted 2FA challenge.
# No bearer or refresh token is issued until the challenge succeeds.
_patient_access_schema = _DISCOVERABLE_FINISH_RESPONSE["content"]["application/json"][
    "schema"
]
_patient_2fa_schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["requires_2fa", "two_factor_method", "pending_2fa_token", "user"],
    "properties": {
        "requires_2fa": {"type": "boolean", "const": True},
        "two_factor_method": {"type": "string", "const": "totp"},
        "pending_2fa_token": {"type": "string"},
        "user": _patient_access_schema["properties"]["user"],
    },
}
_DISCOVERABLE_FINISH_RESPONSE["description"] = (
    "Patient access session or second-factor challenge"
)
_DISCOVERABLE_FINISH_RESPONSE["content"]["application/json"]["schema"] = {
    "oneOf": [_patient_access_schema, _patient_2fa_schema]
}


def _check_webauthn_available():
    """Raise 503 if webauthn library is not installed."""
    from app.services.webauthn_service import is_webauthn_available

    if not is_webauthn_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "reason": "webauthn_not_configured",
                "message": "WebAuthn library is not installed. Contact administrator.",
            },
        )


def _management_identity(
    db: Session, current_user: User, token: str
) -> tuple[int, int]:
    """Resolve the live card within the bearer token's patient scope."""
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401, detail={"reason": "invalid_session"}
        ) from exc
    scoped_id = (
        claims.get("patient_id") if claims.get("scope") == "patient_portal" else None
    )
    if claims.get("scope") == "patient_portal" and (
        isinstance(scoped_id, bool) or not isinstance(scoped_id, int) or scoped_id <= 0
    ):
        raise HTTPException(status_code=401, detail={"reason": "invalid_session"})
    query = (
        db.query(User.id, Patient.id)
        .join(Patient, Patient.user_id == User.id)
        .filter(
            User.id == current_user.id,
            User.role == "Patient",
            User.is_active.is_(True),
            User.is_superuser.is_(False),
            Patient.is_deleted.is_not(True),
        )
    )
    if scoped_id is not None:
        query = query.filter(Patient.id == scoped_id)
    row = query.first()
    if row is None:
        raise HTTPException(
            status_code=403, detail={"reason": "patient_access_required"}
        )
    return row[0], row[1]


def _bearer_context(token: str, user_id: int) -> dict:
    from app.core.user_token_claims import is_user_access_claims, parse_user_auth_epoch

    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti, exp = claims.get("jti"), claims.get("exp")
        if (
            not is_user_access_claims(claims)
            or int(claims["sub"]) != user_id
            or not isinstance(jti, str)
            or not 1 <= len(jti) <= 128
            or type(exp) is not int
            or exp <= time.time()
        ):
            raise ValueError("invalid session")
        return {
            "expected_auth_epoch": parse_user_auth_epoch(claims),
            "expected_jti": jti,
            "expected_exp": exp,
            "scoped_id": claims.get("patient_id")
            if claims.get("scope") == "patient_portal"
            else None,
        }
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(
            status_code=401, detail={"reason": "invalid_session"}
        ) from exc


def _bearer_args(context: dict) -> dict:
    return {
        key: context[key]
        for key in ("expected_auth_epoch", "expected_jti", "expected_exp")
    }


def _validate_step_up(body: Any) -> None:
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("phone"), str)
        or not isinstance(body.get("verification_grant"), str)
    ):
        raise HTTPException(status_code=400, detail={"reason": "step_up_required"})


def _consume_patient_step_up(db: Session, user_id: int, body: Any) -> None:
    """Consume a one-use OTP grant and bind its verified phone to the caller."""
    from app.services.patient_otp_service import (
        PatientOtpError,
        get_patient_otp_service,
        normalize_phone,
    )

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"reason": "step_up_required"})
    phone, grant = body.get("phone"), body.get("verification_grant")
    if not isinstance(phone, str) or not isinstance(grant, str):
        raise HTTPException(status_code=400, detail={"reason": "step_up_required"})
    normalized = normalize_phone(phone)
    try:
        service = get_patient_otp_service()
        valid = normalized and service.consume_bound_grant(
            db, user_id, normalized, grant
        )
    except PatientOtpError as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "step_up_unavailable"}
        ) from exc
    if not valid:
        raise HTTPException(status_code=403, detail={"reason": "step_up_failed"})


def _patient_id_from_body(body: Any) -> int | None:
    if not isinstance(body, dict):
        return None
    value = body.get("patient_id")
    if isinstance(value, bool):
        return None
    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and len(value) <= 10
    ):
        value = int(value)
    if not isinstance(value, int) or not 0 < value <= 2147483647:
        return None
    return value


@router.post(
    "/register/begin",
    operation_id="webauthn_register_begin",
    openapi_extra=_STEP_UP_BODY,
    responses={**_MUTATION_RESPONSES, 200: _REGISTRATION_BEGIN_RESPONSE},
)
@limiter.limit("5/minute")
async def webauthn_register_begin(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """Begin registration after a one-use patient OTP step-up."""
    _check_webauthn_available()

    from app.services.webauthn_service import (
        WebAuthnBearerInvalid,
        WebAuthnStoreUnavailable,
        begin_passkey_registration,
    )

    try:
        body = await request.json()
    except Exception:
        body = {}

    _validate_step_up(body)
    user_id, patient_id = await run_in_threadpool(
        _management_identity, db, current_user, token
    )
    context = _bearer_context(token, user_id)
    session_jti = context["expected_jti"]

    try:
        options = await run_in_threadpool(
            begin_passkey_registration,
            db,
            patient_id,
            user_id=user_id,
            session_jti=session_jti,
            rp_name="Medical Clinic",
            step_up=lambda: _consume_patient_step_up(db, user_id, body),
            **_bearer_args(context),
        )
        return {"options": options}
    except WebAuthnBearerInvalid as exc:
        raise HTTPException(
            status_code=401, detail={"reason": "invalid_session"}
        ) from exc
    except HTTPException:
        raise
    except WebAuthnStoreUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc
    except Exception as exc:
        logger.error("WebAuthn registration begin failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500, detail={"reason": "registration_begin_failed"}
        ) from exc


@router.post(
    "/register/finish",
    operation_id="webauthn_register_finish",
    openapi_extra=_REGISTRATION_FINISH_BODY,
    responses={**_MUTATION_RESPONSES, 200: _REGISTRATION_FINISH_RESPONSE},
)
@limiter.limit("10/minute")
async def webauthn_register_finish(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """Finish passkey registration (M4-P1-4).

    Verifies browser response and stores credential.
    """
    _check_webauthn_available()

    from app.services.webauthn_service import (
        WebAuthnBearerInvalid,
        WebAuthnStoreUnavailable,
        finish_passkey_registration,
    )

    try:
        body = await request.json()
    except Exception:
        body = {}

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400, detail={"reason": "credential_response_required"}
        )
    credential_response = body.get("credential_response")
    ceremony_id = body.get("ceremony_id")
    if not isinstance(credential_response, dict) or not credential_response:
        raise HTTPException(
            status_code=400, detail={"reason": "credential_response_required"}
        )
    if not isinstance(ceremony_id, str) or not ceremony_id:
        raise HTTPException(status_code=400, detail={"reason": "ceremony_id_required"})
    user_id, patient_id = await run_in_threadpool(
        _management_identity, db, current_user, token
    )
    context = _bearer_context(token, user_id)
    session_jti = context["expected_jti"]
    credential_name = body.get("credential_name")
    if credential_name is not None and (
        not isinstance(credential_name, str) or len(credential_name) > 100
    ):
        raise HTTPException(
            status_code=400, detail={"reason": "invalid_credential_name"}
        )

    try:
        credential = await run_in_threadpool(
            finish_passkey_registration,
            db,
            patient_id,
            user_id=user_id,
            session_jti=session_jti,
            ceremony_id=ceremony_id,
            credential_response=credential_response,
            credential_name=credential_name,
            **_bearer_args(context),
        )
        return {
            "registered": True,
            "credential_id": credential.id,
            "name": credential.name,
        }
    except WebAuthnBearerInvalid as exc:
        raise HTTPException(
            status_code=401, detail={"reason": "invalid_session"}
        ) from exc
    except WebAuthnStoreUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"reason": "registration_failed"}
        ) from exc
    except Exception as exc:
        logger.error("WebAuthn registration finish failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500, detail={"reason": "registration_finish_failed"}
        ) from exc


@router.post(
    "/login/discoverable/begin",
    operation_id="webauthn_discoverable_begin",
    openapi_extra=_DISCOVERABLE_BEGIN_BODY,
    responses={**_DISCOVERABLE_ERRORS, 200: _DISCOVERABLE_BEGIN_RESPONSE},
)
@limiter.limit("30/minute")
async def webauthn_discoverable_begin(request: Request) -> dict[str, Any]:
    """Begin anonymous passkey login under shared distributed quotas."""
    _check_webauthn_available()
    from app.services.webauthn_service import (
        WebAuthnQuotaExceeded,
        WebAuthnStoreUnavailable,
        begin_discoverable_authentication,
    )

    try:
        options = await run_in_threadpool(
            begin_discoverable_authentication, get_client_ip(request)
        )
        return {"options": options}
    except WebAuthnQuotaExceeded as exc:
        raise HTTPException(
            status_code=429, detail={"reason": "auth_rate_limited"}
        ) from exc
    except WebAuthnStoreUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc
    except Exception as exc:
        logger.error("Discoverable authentication begin failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc


@router.post(
    "/login/discoverable/finish",
    operation_id="webauthn_discoverable_finish",
    openapi_extra=_DISCOVERABLE_FINISH_BODY,
    responses={**_DISCOVERABLE_ERRORS, 200: _DISCOVERABLE_NEXT_RESPONSE},
)
@limiter.limit("30/minute")
async def webauthn_discoverable_finish(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Verify the first assertion and request a fresh bound assertion."""
    _check_webauthn_available()
    from app.services.webauthn_service import (
        WebAuthnQuotaExceeded,
        WebAuthnStoreUnavailable,
        finish_discoverable_authentication,
    )

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        result = await run_in_threadpool(
            finish_discoverable_authentication,
            db,
            client_ip=get_client_ip(request),
            ceremony_id=body.get("ceremony_id"),
            assertion_response=body.get("assertion_response"),
        )
        response.headers["Cache-Control"] = "no-store"
        return result
    except WebAuthnQuotaExceeded as exc:
        raise HTTPException(
            status_code=429, detail={"reason": "auth_rate_limited"}
        ) from exc
    except WebAuthnStoreUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc
    except Exception as exc:
        logger.info("Discoverable authentication rejected: %s", type(exc).__name__)
        raise HTTPException(
            status_code=403, detail={"reason": "auth_finish_failed"}
        ) from exc


@router.post(
    "/login/discoverable/complete",
    operation_id="webauthn_discoverable_complete",
    openapi_extra=_DISCOVERABLE_FINISH_BODY,
    responses={**_DISCOVERABLE_ERRORS, 200: _DISCOVERABLE_FINISH_RESPONSE},
)
@limiter.limit("30/minute")
async def webauthn_discoverable_complete(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Verify a second, epoch-bound assertion before issuing a session."""
    _check_webauthn_available()
    from app.services.webauthn_service import (
        WebAuthnQuotaExceeded,
        WebAuthnStoreUnavailable,
        complete_discoverable_authentication,
    )

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        result = await run_in_threadpool(
            complete_discoverable_authentication,
            db,
            client_ip=get_client_ip(request),
            ceremony_id=body.get("ceremony_id"),
            assertion_response=body.get("assertion_response"),
        )
        response.headers["Cache-Control"] = "no-store"
        return result
    except WebAuthnQuotaExceeded as exc:
        raise HTTPException(
            status_code=429, detail={"reason": "auth_rate_limited"}
        ) from exc
    except WebAuthnStoreUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc
    except Exception as exc:
        logger.info("Discoverable authentication rejected: %s", type(exc).__name__)
        raise HTTPException(
            status_code=403, detail={"reason": "auth_finish_failed"}
        ) from exc


@router.post("/login/begin", operation_id="webauthn_login_begin")
@limiter.limit("10/minute")  # WEBAUTHN-BE-002: anonymous challenge-issuer throttle
async def webauthn_login_begin(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Begin passkey authentication (M4-P1-4).

    Returns WebAuthn authentication options for navigator.credentials.get().
    """
    _check_webauthn_available()

    from app.services.webauthn_service import (
        WebAuthnStoreUnavailable,
        begin_passkey_authentication,
    )

    try:
        body = await request.json()
    except Exception:
        body = {}

    patient_id = _patient_id_from_body(body)
    if patient_id is None:
        raise HTTPException(status_code=400, detail={"reason": "patient_id_required"})

    try:
        # WEBAUTHN-BE-001 (#4063): RP ID is server-pinned, body value ignored.
        options = await run_in_threadpool(
            begin_passkey_authentication,
            db,
            patient_id,
            client_ip=get_client_ip(request),
        )
        return {"options": options}
    except WebAuthnStoreUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc
    except Exception as exc:
        logger.error("WebAuthn auth begin failed: %s", exc)
        raise HTTPException(
            status_code=500, detail={"reason": "auth_begin_failed"}
        ) from exc


@router.post(
    "/login/finish",
    operation_id="webauthn_login_finish",
    responses={**_DISCOVERABLE_ERRORS, 200: _DISCOVERABLE_FINISH_RESPONSE},
)
@limiter.limit("5/minute")  # WEBAUTHN-BE-002: unauthenticated assertion throttle
async def webauthn_login_finish(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Finish passkey authentication (M4-P1-4).

    Verifies assertion and issues a session or a second-factor challenge.
    """
    _check_webauthn_available()

    from app.services.webauthn_service import (
        WebAuthnStoreUnavailable,
        finish_passkey_authentication,
    )

    try:
        body = await request.json()
    except Exception:
        body = {}

    patient_id = _patient_id_from_body(body)
    if patient_id is None:
        raise HTTPException(status_code=403, detail={"reason": "auth_finish_failed"})

    assertion_response = body.get("assertion_response")
    ceremony_id = body.get("ceremony_id")
    if not isinstance(assertion_response, dict) or not assertion_response:
        raise HTTPException(
            status_code=400, detail={"reason": "assertion_response_required"}
        )
    if not isinstance(ceremony_id, str) or not ceremony_id:
        raise HTTPException(status_code=400, detail={"reason": "ceremony_id_required"})

    try:
        # WEBAUTHN-BE-001 (#4063): expected RP ID/origin are server-pinned —
        # never taken from the request body (anti-phishing origin binding).
        result = await run_in_threadpool(
            finish_passkey_authentication,
            db,
            patient_id,
            assertion_response=assertion_response,
            ceremony_id=ceremony_id,
            client_ip=get_client_ip(request),
        )
        response.headers["Cache-Control"] = "no-store"
        return result
    except WebAuthnStoreUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"reason": "auth_temporarily_unavailable"}
        ) from exc
    except ValueError as exc:
        # WEBAUTHN-BE-002: every pre-verification failure (non-numeric id,
        # unknown patient, no challenge, no active credential) shares ONE
        # opaque 403 — the raw message was an enumeration oracle. Details go
        # to the server log only.
        logger.info("WebAuthn auth finish rejected: %s", exc)
        raise HTTPException(
            status_code=403, detail={"reason": "auth_finish_failed"}
        ) from exc
    except Exception as exc:
        logger.error("WebAuthn auth finish failed: %s", exc)
        # Uniform with the ValueError branch: infra failures on this
        # anonymous plane must not be distinguishable from rejections.
        raise HTTPException(
            status_code=403, detail={"reason": "auth_finish_failed"}
        ) from exc


@router.post(
    "/credentials/list",
    operation_id="webauthn_list_credentials",
    responses={**_AUTH_RESPONSES, 200: _LIST_RESPONSE},
)
async def webauthn_list_credentials(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """List active passkeys for the authenticated patient (M4-P1-4)."""
    from sqlalchemy import and_, select

    from app.models.authentication import TokenBlacklist
    from app.models.passkey_credential import PasskeyCredential

    user_id = current_user.id
    context = _bearer_context(token, user_id)

    def _list():
        revoked = (
            select(TokenBlacklist.id)
            .where(TokenBlacklist.jti == context["expected_jti"])
            .exists()
        )
        legacy = (
            select(TokenBlacklist.id)
            .where(
                TokenBlacklist.user_id == User.id,
                TokenBlacklist.reason.like("all_user_tokens:%"),
                TokenBlacklist.expires_at > datetime.now(UTC),
            )
            .exists()
        )
        query = (
            db.query(PasskeyCredential)
            .select_from(User)
            .join(Patient, Patient.user_id == User.id)
            .outerjoin(
                PasskeyCredential,
                and_(
                    PasskeyCredential.patient_id == Patient.id,
                    PasskeyCredential.owner_user_id == User.id,
                    PasskeyCredential.active.is_(True),
                ),
            )
            .filter(
                User.id == user_id,
                User.role == "Patient",
                User.is_active.is_(True),
                User.is_superuser.is_(False),
                User.auth_epoch == context["expected_auth_epoch"],
                Patient.is_deleted.is_not(True),
                ~revoked,
            )
        )
        if context["expected_auth_epoch"] == 0:
            query = query.filter(~legacy)
        if context["scoped_id"] is not None:
            query = query.filter(Patient.id == context["scoped_id"])
        rows = query.order_by(PasskeyCredential.created_at.desc()).all()
        if not rows or time.time() >= context["expected_exp"]:
            raise HTTPException(status_code=401, detail={"reason": "invalid_session"})
        return [row for row in rows if row is not None]

    passkeys = await run_in_threadpool(_list)
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


@router.post(
    "/credentials/{credential_id}/deactivate",
    operation_id="webauthn_deactivate_credential",
    openapi_extra=_STEP_UP_BODY,
    responses={
        **_MUTATION_RESPONSES,
        200: _DEACTIVATE_RESPONSE,
        404: {"description": "Credential not found"},
        409: {"description": "Cannot deactivate last active credential"},
    },
)
@limiter.limit("5/minute")
async def webauthn_deactivate_credential(
    credential_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    """Deactivate a passkey (M4-P1-4)."""
    from app.services.webauthn_service import WebAuthnBearerInvalid, deactivate_passkey

    try:
        body = await request.json()
    except Exception:
        body = {}

    _validate_step_up(body)
    user_id, patient_id = await run_in_threadpool(
        _management_identity, db, current_user, token
    )
    context = _bearer_context(token, user_id)

    try:
        success = await run_in_threadpool(
            deactivate_passkey,
            db,
            patient_id,
            credential_id,
            user_id=user_id,
            step_up=lambda: _consume_patient_step_up(db, user_id, body),
            **_bearer_args(context),
        )
    except WebAuthnBearerInvalid as exc:
        raise HTTPException(
            status_code=401, detail={"reason": "invalid_session"}
        ) from exc
    except ValueError as exc:
        # WEBAUTHN-BE-003: the patient's LAST active passkey is protected —
        # removing it would lock them out of passkey login entirely.
        raise HTTPException(
            status_code=409, detail={"reason": "last_active_credential"}
        ) from exc
    if not success:
        raise HTTPException(status_code=404, detail={"reason": "credential_not_found"})

    return {"deactivated": True, "credential_id": credential_id}
