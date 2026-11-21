from __future__ import annotations

import os
from datetime import timedelta

CONFIRM_ENV = "CONFIRM_MINT_DEV_TOKEN"
SUBJECT_ENV = "MINT_DEV_TOKEN_SUBJECT"
EXPIRES_ENV = "MINT_DEV_TOKEN_EXPIRES_MINUTES"
DEFAULT_EXPIRES_MINUTES = 15
MAX_EXPIRES_MINUTES = 60


def _require_mint_dev_token_confirmation() -> None:
    if os.getenv(CONFIRM_ENV) != "1":
        raise SystemExit(
            f"Refusing to mint and print a dev token without {CONFIRM_ENV}=1."
        )


def _required_subject() -> str:
    subject = os.getenv(SUBJECT_ENV, "").strip()
    if not subject:
        raise SystemExit(
            f"Set {SUBJECT_ENV}=<username-or-id>; refusing implicit admin token minting."
        )
    return subject


def _token_expires_delta() -> timedelta:
    raw_value = os.getenv(EXPIRES_ENV, str(DEFAULT_EXPIRES_MINUTES)).strip()
    try:
        minutes = int(raw_value)
    except ValueError as exc:
        raise SystemExit(f"{EXPIRES_ENV} must be an integer number of minutes.") from exc

    if minutes < 1 or minutes > MAX_EXPIRES_MINUTES:
        raise SystemExit(f"{EXPIRES_ENV} must be between 1 and {MAX_EXPIRES_MINUTES}.")

    return timedelta(minutes=minutes)


def mint_dev_token() -> str:
    """Mint only for a live local development account under its User lock."""
    _require_mint_dev_token_confirmation()
    subject = _required_subject()
    expires_delta = _token_expires_delta()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.api.deps import create_access_token
    from app.core.config import settings
    from app.core.roles import is_login_blocked_role
    from app.core.user_token_claims import is_user_access_claims
    from app.models.user import User
    from app.scripts.reset_dev_db import build_preflight, get_database_url

    database_url = get_database_url()
    preflight = build_preflight(database_url, mode="mint-dev-token")
    allowed_environments = {"dev", "development", "local", "test", "testing"}
    for name in ("ENV", "APP_ENV", "ENVIRONMENT"):
        value = os.getenv(name, "").strip().lower()
        if value and value not in allowed_environments:
            raise SystemExit("Development token minting requires a development environment.")
    if preflight.env_value.strip().lower() not in allowed_environments:
        raise SystemExit("Development token minting requires a development environment.")
    if not settings.is_development:
        raise SystemExit("Development token minting requires development application settings.")

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            lookup = User.id == int(subject) if subject.isascii() and subject.isdecimal() else User.username == subject
            user = db.query(User).filter(lookup).with_for_update(key_share=True).populate_existing().first()
            if user is None or not user.is_active or is_login_blocked_role(user.role):
                raise SystemExit("Development account is missing, inactive, or blocked.")
            claims = {"sub": str(user.id), "auth_epoch": user.auth_epoch}
            if not is_user_access_claims(claims):
                raise SystemExit("Development account has invalid authentication state.")
            return create_access_token(
                claims,
                expires_delta=expires_delta,
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(mint_dev_token())
