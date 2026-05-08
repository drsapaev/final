from __future__ import annotations

import os
import sys
from pathlib import Path


def require_live_migration_confirmation() -> None:
    if "--dry-run" in sys.argv:
        return
    if os.getenv("CONFIRM_SQLITE_TO_POSTGRES_MIGRATION") != "1":
        raise RuntimeError(
            "Refusing to run live SQLite-to-PostgreSQL migration. "
            "Pass --dry-run for planning or set CONFIRM_SQLITE_TO_POSTGRES_MIGRATION=1 for an explicit migration run."
        )


def main() -> int:
    require_live_migration_confirmation()
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.scripts.migrate_sqlite_to_postgres import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
