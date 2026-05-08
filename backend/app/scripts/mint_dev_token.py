from __future__ import annotations

import os


def _require_mint_dev_token_confirmation() -> None:
    if os.getenv("CONFIRM_MINT_DEV_TOKEN") != "1":
        raise SystemExit(
            "Refusing to mint and print a dev token without CONFIRM_MINT_DEV_TOKEN=1."
        )


if __name__ == "__main__":
    _require_mint_dev_token_confirmation()

    from app.api.deps import create_access_token  # type: ignore

    print(create_access_token("admin"))
