"""Registrar-issued patient activation tokens (Phase 0, PR-A2).

Staff surface of the activation flow: POST /patients/{patient_id}/activation-token
binds a single-use 72h token to the EXACT (Patient.id, normalized phone)
pair (identity contract v3 — phone is possession, token pins identity).

Deliberately a SEPARATE router file included under the /patients prefix:
parallel queue-track work actively touches patients.py — an isolated file
keeps merge pressure off it (repo convention, cf. #3001).

RBAC: Admin|Registrar only (same trio as patient create/update).
Audit: log_critical_change (critical-table convention) — token plaintext is
NEVER logged (hash-only storage in Redis; response returns it exactly once).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.core.audit import log_critical_change
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.services.patient_activation_service import (
    ActivationError,
    get_patient_activation_service,
)

router = APIRouter()


class PatientActivationTokenResponse(BaseModel):
    activation_token: str
    expires_in_hours: int
    phone_masked: str


@router.post(
    "/{patient_id}/activation-token",
    response_model=PatientActivationTokenResponse,
    status_code=201,
)
@limiter.limit("10/minute")
async def issue_activation_token(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """Выдать одноразовый токен активации портала для карты пациента.

    Токен привязывается к (Patient.id, нормализованный phone) на момент
    выдачи; действует 72 часа; перевыпуск отзывает предыдущий токен.
    Открытый текст токена возвращается ОДИН раз и не попадает в аудит."""
    try:
        result = get_patient_activation_service().issue_activation_token(db, patient_id)
    except ActivationError as err:
        from fastapi import HTTPException

        raise HTTPException(status_code=err.status_code, detail=err.detail) from err

    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        table_name="patients",
        row_id=patient_id,
        old_data={"user_id": None},
        new_data={
            "activation_token_issued": True,
            "phone_masked": result["phone_masked"],
        },
        request=request,
        description=(
            f"Выдан токен активации портала для пациента #{patient_id} "
            f"(телефон {result['phone_masked']})"
        ),
    )
    # Codex P1 (PR #3320 round 1): log_critical_change only db.add()s the
    # audit row and this Redis-only issuance path performs no other DB
    # write, while get_db() closes the session WITHOUT committing — the
    # pending audit row was rolled back. Commit it explicitly: the audit
    # trail must be durable (critical-table convention).
    db.commit()

    return result
