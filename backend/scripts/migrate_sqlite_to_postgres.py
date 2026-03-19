from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.scripts.migrate_sqlite_to_postgres import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
