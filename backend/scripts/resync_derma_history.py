#!/usr/bin/env python3
"""Runbook-команда: полный пересчёт derma_history_entries из источников.

Единственный класс записей, который after_flush listener не видит — правки
источников мимо ORM (Core DML, data-миграции, raw SQL, внешние скрипты).
Эта команда — детерминированный полный рефреш read model (delete + пакетная
keyset-репроекция, память O(batch)) для любых таких случаев; её же
использует backfill миграции 0075.

Запуск (от корня репо):
    python backend/scripts/resync_derma_history.py --database-url <url>
    CONFIRM_DERMA_HISTORY_RESYNC=1 python backend/scripts/resync_derma_history.py <url>

Требует явного подтверждения (пересчёт перезаписывает производную таблицу —
при живом трафике это окно рассинхронизации GET /derma/* ответов).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def require_confirmation() -> None:
    if os.getenv("CONFIRM_DERMA_HISTORY_RESYNC") == "1":
        return
    raise RuntimeError(
        "Refusing to resync derma history read model. "
        "Set CONFIRM_DERMA_HISTORY_RESYNC=1 for an explicit resync run "
        "(the rebuild rewrites derma_history_entries in one transaction)."
    )


def main() -> int:
    require_confirmation()
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from sqlalchemy import create_engine

    from app.services.derma_history_projection import (
        DEFAULT_REBUILD_BATCH_SIZE,
        rebuild_derma_history_entries,
    )

    database_url = None
    for arg in sys.argv[1:]:
        if arg.startswith("--database-url="):
            database_url = arg.split("=", 1)[1]
        elif arg.startswith("--batch-size="):
            continue  # parsed below
    if database_url is None:
        database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required (--database-url=... or env)", file=sys.stderr)
        return 2

    batch_size = DEFAULT_REBUILD_BATCH_SIZE
    for arg in sys.argv[1:]:
        if arg.startswith("--batch-size="):
            try:
                batch_size = int(arg.split("=", 1)[1])
            except ValueError:
                print(f"invalid --batch-size: {arg}", file=sys.stderr)
                return 2

    engine = create_engine(database_url)
    with engine.begin() as connection:
        counts = rebuild_derma_history_entries(connection, batch_size=batch_size)
    print("derma_history_entries resync complete:")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
