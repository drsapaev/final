"""Bounded, transaction-safe delivery of email-verification links."""
from __future__ import annotations

import ipaddress
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from urllib.parse import quote, urlsplit

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.authentication import EmailVerificationToken
from app.models.user import User
from app.services.auth_svc._auth import _email_verification_mac
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
    check_bearer_expiry,
    check_patient_scope,
    check_profile_bearer,
    lock_profile_users,
)

MAX_REQUESTS_PER_HOUR = 3
TOKEN_LIFETIME = timedelta(hours=24)


class VerificationConfigurationError(ValueError):
    pass


class VerificationRateLimited(ValueError):
    pass


class VerificationExpired(ValueError):
    pass


@dataclass(frozen=True, repr=False)
class VerificationReservation:
    id: int
    token: str
    email: str
    expires_at: datetime


def verification_url(token: str) -> str:
    """Use only a configured origin; never reflect a request-controlled host."""
    origin = str(settings.FRONTEND_URL or "")
    if not origin or any(ord(c) <= 32 or ord(c) >= 127 for c in origin) or "\\" in origin or "%" in origin:
        raise VerificationConfigurationError("Invalid frontend origin")
    try:
        parts = urlsplit(origin)
        host = parts.hostname
        port = parts.port
        if (not host or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment):
            raise ValueError("Invalid origin")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if len(host) > 253 or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part) for part in host.split(".")):
                raise ValueError("Invalid hostname")
        if parts.scheme != "https" and not (
            parts.scheme == "http" and settings.is_development and host in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Insecure frontend origin")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("Invalid port")
    except ValueError as exc:
        raise VerificationConfigurationError("Invalid frontend origin") from exc
    return f"{parts.scheme}://{parts.netloc}/verify-email#token={quote(token, safe='')}"


def _locked_user(db: Session, context: ProfileBearerContext) -> User:
    user, _ = lock_profile_users(db, context.user_id, context.user_id)
    check_profile_bearer(db, user, context)
    check_patient_scope(db, user, context)
    if not user.email:
        raise ProfileBearerInvalid("Bearer session unavailable")
    return user


def reserve_verification(db: Session, context: ProfileBearerContext, ip: str | None, user_agent: str | None) -> VerificationReservation:
    """Commit an unusable reservation before delivery; limit all SMTP attempts."""
    try:
        user = _locked_user(db, context)
        now = datetime.now(UTC)
        older_than = now - timedelta(hours=1)
        # Keep outstanding and recent attempts; remove expired history on the
        # account's next request so repeated use has bounded storage.
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.expires_at <= now,
            EmailVerificationToken.created_at < older_than,
        ).delete(synchronize_session=False)
        count = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.created_at >= older_than,
        ).count()
        if count >= MAX_REQUESTS_PER_HOUR:
            raise VerificationRateLimited("Verification request limit reached")
        nonce = secrets.token_urlsafe(16)
        token = f"v1.{nonce}.{_email_verification_mac(user, nonce)}"
        expires_at = now + TOKEN_LIFETIME
        # verified=True / verified_at=NULL is an unusable pending delivery;
        # confirmed or revoked tokens always have verified_at set.
        reservation = EmailVerificationToken(user_id=user.id, token=token, expires_at=expires_at,
            verified=True, verified_at=None, ip_address=ip, user_agent=user_agent)
        db.add(reservation)
        db.flush()
        result = VerificationReservation(reservation.id, token, user.email, expires_at)
        check_bearer_expiry(context)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def activate_verification(db: Session, context: ProfileBearerContext, reservation: VerificationReservation) -> None:
    """Activate a delivered link only if its original session is still valid."""
    try:
        user = _locked_user(db, context)
        if user.email != reservation.email:
            raise ProfileBearerInvalid("Bearer session unavailable")
        row = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.id == reservation.id,
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.token == reservation.token,
        ).with_for_update().populate_existing().first()
        now = datetime.now(UTC)
        if row is None or row.verified is not True or row.verified_at is not None:
            raise VerificationExpired("Verification link expired")
        row_expiry = row.expires_at
        if row_expiry.tzinfo is None:
            row_expiry = row_expiry.replace(tzinfo=UTC)
        if min(reservation.expires_at, row_expiry) <= now:
            raise VerificationExpired("Verification link expired")
        # A newer successfully delivered link wins even if this SMTP call
        # completed later; preserve the newer link and fail this request.
        newer = db.query(EmailVerificationToken.id).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.id > row.id,
            or_(EmailVerificationToken.verified.is_(False), EmailVerificationToken.verified_at.is_not(None)),
        ).first()
        if newer is not None:
            raise VerificationExpired("Verification link superseded")
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.verified.is_(False),
        ).update({"verified": True, "verified_at": now}, synchronize_session=False)
        row.verified = False
        row.verified_at = None
        db.flush()
        check_bearer_expiry(context)
        if datetime.now(UTC) >= min(reservation.expires_at, row_expiry):
            raise VerificationExpired("Verification link expired")
        db.commit()
    except Exception:
        db.rollback()
        raise


def verification_email(url: str) -> tuple[str, str]:
    """Escape the URL independently for the HTML attribute and text node."""
    href = escape(url, quote=True)
    display = escape(url, quote=False)
    html = f'<p>Подтвердите email:</p><p><a href="{href}">Подтвердить email</a></p><p>{display}</p>'
    plain = f"Подтвердите email, открыв ссылку:\n{url}\n"
    return html, plain
