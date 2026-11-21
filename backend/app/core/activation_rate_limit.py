"""Shared, fail-closed admission budget for public activation attempts."""
from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta
from ipaddress import ip_address

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limiter import get_client_ip

_WINDOW_SECONDS = 60
_CLIENT_LIMIT = 5
_GLOBAL_LIMIT = 100
_ADVISORY_LOCK = int.from_bytes(
    hashlib.sha256(b"activation-admission-budget-v1").digest()[:8], "big", signed=True
)


def _testing_bypass() -> bool:
    # Unrelated tests use SQLite and do not share a process-wide quota. The
    # security suite disables this seam and exercises a real PostgreSQL store.
    return bool(settings.TESTING and not settings.is_production)


def _consume_budget(db: Session, client_scope: str) -> bool:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL activation admission storage required")
    # This is a separate, short transaction, committed before setup writes.
    # Its counters are therefore shared across workers and never refunded by
    # rollback of the caller's SQLAlchemy transaction. The global advisory lock
    # serializes the check and both counter updates on every worker.
    with bind.engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK})
        now = conn.execute(text("SELECT clock_timestamp()")).scalar_one()
        conn.execute(text("DELETE FROM activation_rate_budgets WHERE expires_at <= :now"), {"now": now})
        rows = conn.execute(
            text("SELECT scope, attempts FROM activation_rate_budgets WHERE scope IN (:global_scope, :client_scope)"),
            {"global_scope": "global", "client_scope": client_scope},
        )
        counts = {row.scope: row.attempts for row in rows}
        if counts.get("global", 0) >= _GLOBAL_LIMIT or counts.get(client_scope, 0) >= _CLIENT_LIMIT:
            return False
        for scope in ("global", client_scope):
            conn.execute(
                text("INSERT INTO activation_rate_budgets (scope, attempts, expires_at) "
                     "VALUES (:scope, 1, :expires_at) ON CONFLICT (scope) DO UPDATE "
                     "SET attempts = activation_rate_budgets.attempts + 1"),
                {"scope": scope, "expires_at": now + timedelta(seconds=_WINDOW_SECONDS)},
            )
        return True


def enforce_activation_budget(request: Request, db: Session) -> None:
    if _testing_bypass():
        return

    try:
        address = get_client_ip(request)
        # Canonicalize equivalent IPv6 spellings before applying the budget.
        try:
            address = str(ip_address(address))
        except ValueError:
            address = "unknown"
        digest = hmac.new(
            settings.SECRET_KEY.encode(), address.encode(), hashlib.sha256
        ).hexdigest()
        allowed = _consume_budget(db, "client:" + digest)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Activation temporarily unavailable") from exc

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many activation attempts",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )
