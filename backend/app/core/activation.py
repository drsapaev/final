from __future__ import annotations

import base64
import os
import platform
import re
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

from jose import jwt
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activation import Activation, ActivationStatus  # type: ignore[attr-defined]
from app.models.setting import Setting  # type: ignore[attr-defined]
import hashlib


# ---------- Машинный идентификатор (серверный) ----------

def _collect_fingerprints() -> str:
    parts = []
    try:
        parts.append(platform.system())
        parts.append(platform.machine())
        parts.append(platform.processor())
    except Exception:
        pass
    try:
        parts.append(socket.gethostname())
    except Exception:
        pass
    try:
        parts.append(str(uuid.getnode()))
    except Exception:
        pass
    try:
        # Linux CPU info
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "rb") as f:
                parts.append(f.read(4096).decode("utf-8", "ignore"))
    except Exception:
        pass
    return "||".join(p for p in parts if p)


def server_machine_hash() -> str:
    """
    Стабильный хэш сервера (не зависит от перезапусков).
    """
    raw = _collect_fingerprints().encode("utf-8", "ignore")
    h = hashlib.sha256(raw).hexdigest().upper()
    # Компактная форма: базовый32 без паддинга
    return base64.b32encode(bytes.fromhex(h)).decode().rstrip("=")


# ---------- Генерация человекочитаемых ключей ----------

def generate_key(prefix: str = "CQ") -> str:
    """
    Ключ вида CQ-YYYYMMDD-XXXXX-XXXXX-XXXXX (только A-Z0-9).
    """
    rnd = base64.b32encode(os.urandom(10)).decode().rstrip("=")  # ~16 симв.
    rnd = re.sub(r"[^A-Z0-9]", "", rnd)
    today = datetime.utcnow().strftime("%Y%m%d")
    chunks = [rnd[i:i+5] for i in range(0, min(len(rnd), 15), 5)]
    while len(chunks) < 3:
        chunks.append("X" * 5)
    return f"{prefix}-{today}-{chunks[0]}-{chunks[1]}-{chunks[2]}"


# ---------- БД-операции для ключей/активаций ----------

@dataclass
class IssueResult:
    key: str
    expiry_date: Optional[str]
    status: str


def issue_key(
    db: Session,
    *,
    days: int = 365,
    status: str = ActivationStatus.ACTIVE,
    meta: Optional[str] = None,
) -> IssueResult:
    key = generate_key()
    exp = datetime.utcnow() + timedelta(days=int(days))
    row = Activation(
        key=key,
        machine_hash=None,
        expiry_date=exp,
        status=status if status in {
            ActivationStatus.ACTIVE, ActivationStatus.TRIAL, ActivationStatus.ISSUED
        } else ActivationStatus.ACTIVE,
        meta=meta,
    )
    db.add(row)
    db.flush()
    return IssueResult(key=key, expiry_date=exp.strftime("%Y-%m-%d"), status=row.status)


@dataclass
class ActivateResult:
    ok: bool
    reason: Optional[str] = None
    token: Optional[str] = None
    key: Optional[str] = None
    machine_hash: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None


def activate_key(db: Session, *, key: str) -> ActivateResult:
    key = (key or "").strip()
    if not key:
        return ActivateResult(ok=False, reason="EMPTY_KEY")

    row: Optional[Activation] = (
        db.execute(select(Activation).where(Activation.key == key)).scalars().first()
    )
    if not row:
        return ActivateResult(ok=False, reason="KEY_NOT_FOUND", key=key)

    if row.status == ActivationStatus.REVOKED:
        return ActivateResult(ok=False, reason="REVOKED", key=key)

    mh = server_machine_hash()

    # Если ключ уже привязан к другому устройству — запрет
    if row.machine_hash and row.machine_hash != mh:
        return ActivateResult(ok=False, reason="KEY_IN_USE", key=key, machine_hash=row.machine_hash)

    # Проверим срок
    if row.expiry_date and datetime.utcnow() > row.expiry_date:
        row.status = ActivationStatus.EXPIRED
        db.flush()
        return ActivateResult(ok=False, reason="EXPIRED", key=key)

    # Привязываем к текущей машине при необходимости
    changed = False
    if not row.machine_hash:
        row.machine_hash = mh
        changed = True
    if row.status in (ActivationStatus.ISSUED, ActivationStatus.TRIAL):
        row.status = ActivationStatus.ACTIVE
        changed = True
    if changed:
        db.flush()
        db.commit()

    # Генерируем оффлайн-токен (JWT)
    claims = {
        "k": row.key,
        "mh": row.machine_hash,
        "st": row.status,
    }
    # exp в JWT — в секундах; берём min(срок лицензии, +400 дней)
    exp_dt = row.expiry_date or (datetime.utcnow() + timedelta(days=400))
    claims["exp"] = int(exp_dt.timestamp())

    token = jwt.encode(claims, settings.AUTH_SECRET, algorithm=settings.AUTH_ALGORITHM)
    return ActivateResult(
        ok=True,
        token=token,
        key=row.key,
        machine_hash=row.machine_hash,
        expiry_date=exp_dt.strftime("%Y-%m-%d"),
        status=row.status,
    )


@dataclass
class Status:
    ok: bool
    reason: Optional[str] = None
    key: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    machine_hash: Optional[str] = None


def validate_server_activation(db: Session) -> Status:
    """Проверка сервера: есть ли активная неистёкшая привязка к текущей машине."""
    mh = server_machine_hash()
    row: Optional[Activation] = (
        db.execute(
            select(Activation).where(
                and_(
                    Activation.machine_hash == mh,
                    Activation.status.in_([ActivationStatus.ACTIVE, ActivationStatus.TRIAL]),
                )
            )
        )
        .scalars()
        .first()
    )
    if not row:
        return Status(ok=False, reason="NO_ACTIVATION", machine_hash=mh)

    if row.status == ActivationStatus.REVOKED:
        return Status(ok=False, reason="REVOKED", key=row.key, machine_hash=mh)

    if row.expiry_date and datetime.utcnow() > row.expiry_date:
        row.status = ActivationStatus.EXPIRED
        db.flush()
        db.commit()
        return Status(ok=False, reason="EXPIRED", key=row.key, machine_hash=mh)

    return Status(
        ok=True,
        key=row.key,
        expiry_date=row.expiry_date.strftime("%Y-%m-%d") if row.expiry_date else None,
        status=row.status,
        machine_hash=mh,
    )