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


if __name__ == "__main__":
    _require_mint_dev_token_confirmation()
    subject = _required_subject()
    expires_delta = _token_expires_delta()

    from app.api.deps import create_access_token  # type: ignore

    print(create_access_token({"sub": subject}, expires_delta=expires_delta))
