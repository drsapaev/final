# app/api/v1/endpoints/activation.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.activation import activate_key, issue_key, validate_server_activation
from app.models.activation import ActivationStatus
from app.schemas.activation import (
    ActivationActivateIn,
    ActivationActivateOut,
    ActivationExtendIn,
    ActivationIssueIn,
    ActivationIssueOut,
    ActivationListOut,
    ActivationRevokeIn,
    ActivationStatusOut,
)
from app.services.activation_admin_service import ActivationAdminService

router = APIRouter(prefix="/activation", tags=["activation"])


@router.post(
    "/issue", response_model=ActivationIssueOut, summary="Выдать новый ключ (Admin)"
)
async def activation_issue(
    body: ActivationIssueIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    res = issue_key(
        db,
        days=body.days,
        status=body.status or ActivationStatus.ACTIVE,
        meta=body.meta,
    )
    return ActivationIssueOut(key=res.key, expiry_date=res.expiry_date, status=res.status)  # type: ignore[arg-type]


@router.post(
    "/activate",
    response_model=ActivationActivateOut,
    summary="Активировать ключ на этом сервере",
)
async def activation_activate(
    body: ActivationActivateIn,
    db: Session = Depends(get_db),
):
    # Разрешаем без токена, чтобы сервер можно было активировать «с нуля».
    res = activate_key(db, key=body.key)
    return ActivationActivateOut(
        ok=res.ok,
        reason=res.reason,
        token=res.token,
        key=res.key,
        machine_hash=res.machine_hash,
        expiry_date=res.expiry_date,
        status=res.status,  # type: ignore[arg-type]
    )


@router.get(
    "/status", response_model=ActivationStatusOut, summary="Статус активации сервера"
)
async def activation_status(
    db: Session = Depends(get_db),
):
    st = validate_server_activation(db)
    return ActivationStatusOut(
        ok=st.ok,
        reason=st.reason,
        key=st.key,
        expiry_date=st.expiry_date,
        status=st.status,  # type: ignore[arg-type]
        machine_hash=st.machine_hash,
    )


# -------- Admin management: list / revoke / extend --------


@router.get(
    "/list", response_model=ActivationListOut, summary="Список выданных ключей (Admin)"
)
async def activation_list(
    status: Optional[str] = Query(
        None, description="issued|trial|active|expired|revoked"
    ),
    key_like: Optional[str] = Query(None, description="подстрока ключа"),
    machine_hash: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    items, total = ActivationAdminService(db).list_activations(
        status=status,
        key_like=key_like,
        machine_hash=machine_hash,
        limit=limit,
        offset=offset,
    )
    return ActivationListOut(items=items, total=total)


@router.post("/revoke", summary="Отозвать ключ (Admin)")
async def activation_revoke(
    body: ActivationRevokeIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    if not ActivationAdminService(db).revoke(key=body.key):
        return {"ok": False, "reason": "KEY_NOT_FOUND"}
    return {"ok": True}


@router.post("/extend", summary="Продлить ключ (Admin)")
async def activation_extend(
    body: ActivationExtendIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    row = ActivationAdminService(db).extend(key=body.key, days=int(body.days))
    if not row:
        return {"ok": False, "reason": "KEY_NOT_FOUND"}
    return {
        "ok": True,
        "expiry_date": row.expiry_date.strftime("%Y-%m-%d"),
        "status": row.status,
    }
