#!/usr/bin/env python3
"""Manual Payme provider secret update helper."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _require_update_payme_provider_confirmation() -> None:
    if os.getenv("CONFIRM_UPDATE_PAYME_PROVIDER") != "1":
        raise SystemExit(
            "Set CONFIRM_UPDATE_PAYME_PROVIDER=1 before updating Payme provider settings."
        )


def _required_payme_secret_key() -> str:
    secret_key = os.getenv("PAYME_SECRET_KEY", "").strip()
    if not secret_key:
        raise SystemExit("Set PAYME_SECRET_KEY before updating the Payme provider secret.")
    return secret_key


def update_payme_provider() -> None:
    _require_update_payme_provider_confirmation()

    from app.crud.payment_webhook import get_provider_by_code, update_provider
    from app.db.session import get_db
    from app.schemas.payment_webhook import PaymentProviderUpdate

    db = next(get_db())
    try:
        provider = get_provider_by_code(db, code="payme")
        if not provider:
            print("Payme provider was not found.")
            return

        print(f"Found Payme provider id={provider.id} name={provider.name}.")
        print(
            "Current Payme provider secret key is "
            + ("set." if provider.secret_key else "not set.")
        )

        update_data = PaymentProviderUpdate(secret_key=_required_payme_secret_key())
        updated_provider = update_provider(db, provider.id, update_data)
        if updated_provider:
            print("Payme provider secret key updated; value is not printed.")
        else:
            print("Payme provider update returned no updated row.")
    finally:
        db.close()


if __name__ == "__main__":
    update_payme_provider()
