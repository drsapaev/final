"""Exact input and transaction-bound Admin authorization for settings writers."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.deps import get_db, oauth2_scheme, require_active_roles, require_roles
from app.api.trusted_financial_auth import _authenticate
from app.models.user import User
from app.services.all_free_policy import _ALL_FREE_POLICY_LOCK
from app.services.doctor_repeat_discount import RepeatPolicyError, _setting_int
from app.services.money_input import MoneyInputError, parse_exact_json
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
    check_profile_bearer,
)

REPEAT_LIMITS = {"repeat_visit_days": (1, 365), "repeat_visit_discount": (0, 100)}
_MAX_VALUE_DIGITS = 64
_MAX_REPEAT_REQUEST_BYTES = 65536


def validate_repeat_setting(key: str, value: object) -> None:
    """Validate direct and HTTP writers without rounding the submitted value."""
    bounds = REPEAT_LIMITS.get(key)
    if bounds is None:
        return
    # A Python float may already have lost significant source digits. HTTP
    # callers instead pass values decoded from the original JSON as Decimal.
    if isinstance(value, float):
        raise ValueError("Некорректные настройки повторного визита")
    if isinstance(value, str) and len(value) > _MAX_VALUE_DIGITS:
        raise ValueError("Некорректные настройки повторного визита")
    if isinstance(value, Decimal) and len(value.as_tuple().digits) > _MAX_VALUE_DIGITS:
        raise ValueError("Некорректные настройки повторного визита")
    try:
        _setting_int(value, lower=bounds[0], upper=bounds[1])
    except RepeatPolicyError:
        raise ValueError("Некорректные настройки повторного визита") from None


def _submitted_values(request: Request, document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        return {}
    path = request.url.path.rstrip("/")
    if path.endswith("/benefit-settings"):
        return {key: document[key] for key in REPEAT_LIMITS if key in document}
    if path.endswith("/clinic/settings"):
        if request.method == "PUT":
            entries = document.get("settings")
            return {key: entries[key] for key in REPEAT_LIMITS if key in entries} if isinstance(entries, dict) else {}
        key = document.get("key")
        return {key: document.get("value")} if isinstance(key, str) and key in REPEAT_LIMITS else {}
    key = request.path_params.get("key")
    return {key: document["value"]} if key in REPEAT_LIMITS and "value" in document else {}


def _changes_all_free(request: Request, document: object) -> bool:
    if not isinstance(document, dict):
        return False
    if request.url.path.rstrip("/").endswith("/benefit-settings"):
        return True
    if request.url.path.rstrip("/").endswith("/clinic/settings"):
        if request.method == "PUT":
            return isinstance(document.get("settings"), dict) and "all_free_auto_approve" in document["settings"]
        return document.get("key") == "all_free_auto_approve"
    return request.path_params.get("key") == "all_free_auto_approve"


@dataclass(frozen=True)
class RepeatSettingsWriter:
    actor: User
    bearer: ProfileBearerContext
    values: dict[str, object]


async def repeat_settings_writer(
    request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db),
) -> RepeatSettingsWriter:
    """Pin before auth, lock and recheck actor, then validate exact raw JSON.

    The route must use this cached ``get_db`` session and call
    ``finish_repeat_settings_write`` immediately before committing.
    """
    actor = await _authenticate(token, db, ("Admin",))
    try:
        bearer = capture_profile_bearer(request, actor)
        if bearer.patient_id is not None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        if db.get_bind().dialect.name == "sqlite":
            # SQLite ignores FOR UPDATE. Reserve the writer before refreshing
            # actor and blacklist; a stale read-to-write upgrade fails closed.
            db.execute(text("UPDATE users SET id=id WHERE id=:actor_id"), {"actor_id": bearer.user_id})
        actor = (db.query(User).filter(User.id == bearer.user_id)
                 .with_for_update(nowait=True).populate_existing().first())
        if actor is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        check_profile_bearer(db, actor, bearer)
        gated = require_roles("Admin")(current_user=actor, db=db)
        require_active_roles("Admin")(current_user=actor, db=db, _role_gated=gated)
        raw = await request.body()
        document = parse_exact_json(raw)
        values = _submitted_values(request, document)
        if values and len(raw) > _MAX_REPEAT_REQUEST_BYTES:
            raise ValueError("Некорректные настройки повторного визита")
        for key, value in values.items():
            validate_repeat_setting(key, value)
        # Store JSON numeric values as exact whole integers; preserve strings
        # for clients that intentionally submitted a string value.
        values = {key: int(value) if isinstance(value, Decimal) else value
                  for key, value in values.items()}
        # Existing all-free code uses a blocking advisory lock. When an Admin
        # User lock is already held, use NOWAIT first to avoid an ABBA cycle;
        # its later normal acquisition is reentrant in the same transaction.
        if _changes_all_free(request, document) and db.get_bind().dialect.name == "postgresql":
            if not db.execute(text("SELECT pg_catalog.pg_try_advisory_xact_lock(:key)"),
                              {"key": _ALL_FREE_POLICY_LOCK}).scalar_one():
                db.rollback()
                raise HTTPException(status_code=409, detail="Настройки изменяются, повторите запрос")
        return RepeatSettingsWriter(actor=actor, bearer=bearer, values=values)
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сессия недоступна") from None
    except (MoneyInputError, ValueError):
        db.rollback()
        raise HTTPException(status_code=422, detail="Некорректные настройки повторного визита") from None
    except DBAPIError as exc:
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        sqlite_code = getattr(exc.orig, "sqlite_errorcode", None)
        db.rollback()
        if code in {"55P03", "40P01"} or (sqlite_code is not None and sqlite_code & 0xff in {5, 6}):
            raise HTTPException(status_code=409, detail="Настройки изменяются, повторите запрос") from None
        raise


def finish_repeat_settings_write(writer: RepeatSettingsWriter) -> None:
    """Reject an expired bearer before the caller's single transaction commits."""
    try:
        check_bearer_expiry(writer.bearer)
    except ProfileBearerInvalid:
        raise HTTPException(status_code=401, detail="Сессия недоступна") from None
