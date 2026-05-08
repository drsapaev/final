#!/usr/bin/env python3
"""Manual JWT minting helper."""

from __future__ import annotations

import os


def _require_mint_token_confirmation() -> None:
    if os.getenv("CONFIRM_MINT_TOKEN") != "1":
        raise SystemExit("Set CONFIRM_MINT_TOKEN=1 before minting and printing a JWT.")


def _token_subject() -> str:
    subject = os.getenv("MINT_TOKEN_SUBJECT", "admin").strip()
    if not subject:
        raise SystemExit("MINT_TOKEN_SUBJECT must not be empty.")
    return subject


def main() -> int:
    _require_mint_token_confirmation()

    from app.api.deps import create_access_token

    print(create_access_token(_token_subject()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
