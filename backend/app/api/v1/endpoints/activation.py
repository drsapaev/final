# app/api/v1/endpoints/activation.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.activation import activate_key, issue_key, validate_server_activation
from app.models.activation import Activation  # type: ignore[attr-defined]
from app.models.activation import ActivationStatus
from app.schemas.activation import (
    ActivationActivateIn,
    ActivationActivateOut,
    ActivationExtendIn,
    ActivationIssueIn,
    ActivationIssueOut,
    ActivationListOut,
    ActivationListRow,
    ActivationRevokeIn,
    ActivationStatusOut,
)

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
    q = select(Activation).order_by(Activation.created_at.desc())
    if status:
        q = q.where(Activation.status == status)
    if key_like:
        q = q.where(Activation.key.ilike(f"%{key_like}%"))
    if machine_hash:
        q = q.where(Activation.machine_hash == machine_hash)

    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = db.execute(q.limit(limit).offset(offset)).scalars().all()

    items = [
        ActivationListRow(
            key=r.key,
            machine_hash=r.machine_hash,
            expiry_date=r.expiry_date.strftime("%Y-%m-%d") if r.expiry_date else None,
            status=r.status,  # type: ignore[arg-type]
            created_at=(r.created_at or datetime.utcnow()).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            updated_at=(r.updated_at or r.created_at or datetime.utcnow()).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            meta=r.meta,
        )
        for r in rows
    ]
    return ActivationListOut(items=items, total=int(total))


@router.post("/revoke", summary="Отозвать ключ (Admin)")
async def activation_revoke(
    body: ActivationRevokeIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    r: Optional[Activation] = (
        db.execute(select(Activation).where(Activation.key == body.key))
        .scalars()
        .first()
    )
    if not r:
        return {"ok": False, "reason": "KEY_NOT_FOUND"}
    r.status = ActivationStatus.REVOKED
    r.updated_at = datetime.utcnow()
    db.flush()
    db.commit()
    return {"ok": True}


@router.post("/extend", summary="Продлить ключ (Admin)")
async def activation_extend(
    body: ActivationExtendIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    r: Optional[Activation] = (
        db.execute(select(Activation).where(Activation.key == body.key))
        .scalars()
        .first()
    )
    if not r:
        return {"ok": False, "reason": "KEY_NOT_FOUND"}
    base = r.expiry_date or datetime.utcnow()
    r.expiry_date = base + timedelta(days=int(body.days))
    if r.status in (
        ActivationStatus.EXPIRED,
        ActivationStatus.ISSUED,
        ActivationStatus.TRIAL,
    ):
        r.status = ActivationStatus.ACTIVE
    r.updated_at = datetime.utcnow()
    db.flush()
    db.commit()
    return {
        "ok": True,
        "expiry_date": r.expiry_date.strftime("%Y-%m-%d"),
        "status": r.status,
    }
