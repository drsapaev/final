from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.setting import Setting  # type: ignore[attr-defined]


@dataclass
class LicenseStatus:
    ok: bool
    reason: Optional[str] = None
    key: Optional[str] = None
    valid_until: Optional[str] = None  # YYYY-MM-DD


def _load_license_rows(db: Session) -> dict:
    """Считать все настройки категории 'license' в dict."""
    rows = (
        db.execute(select(Setting).where(Setting.category == "license")).scalars().all()
    )
    out: dict[str, str] = {}
    for r in rows:
        k = (r.key or "").strip()
        if not k:
            continue
        out[k] = r.value or ""
    return out


def validate_license(db: Session) -> LicenseStatus:
    data = _load_license_rows(db)
    key = (data.get("key") or "").strip()

    if not key:
        return LicenseStatus(ok=False, reason="NO_KEY")

    # Простейшая офлайн-валидация: длина ключа + неистёкшая дата (если задана)
    if len(key) < 16:
        return LicenseStatus(ok=False, reason="KEY_TOO_SHORT", key=key)

    vu = (data.get("valid_until") or "").strip()
    if vu:
        try:
            dt = datetime.strptime(vu, "%Y-%m-%d").date()
            if datetime.utcnow().date() > dt:
                return LicenseStatus(
                    ok=False, reason="EXPIRED", key=key, valid_until=vu
                )
        except Exception:
            return LicenseStatus(ok=False, reason="BAD_DATE", key=key, valid_until=vu)

    return LicenseStatus(ok=True, key=key, valid_until=vu or None)
