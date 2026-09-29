#!/usr/bin/env python3
"""Runbook-команда: пересчёт derma_history_entries из источников.

Единственный класс записей, который after_flush listener не видит — правки
источников мимо ORM (Core DML, data-миграции, raw SQL, внешние скрипты).
Известные производственные Core-записи (reschedule-пути) досинхронизируются
сами (resync_derma_history_for_visits в той же транзакции); эта команда —
для всего остального.

Два режима:

- полный (по умолчанию): DELETE всех строк + пакетная keyset-репроекция,
  ОДНОЙ транзакцией. ОПАСНО под живым трафиком (owner fact-check
  5625c8f1b, P2-3): транзакция держит блокировки строк до коммита —
  параллельный listener сохранения ЭМК врача упирается в блокировку и
  ждёт, а его INSERT после коммита пересчёта может нарушить
  uq_derma_history_entry_identity и уронить сохранение ЭМК. Запускать
  только в окне обслуживания с остановленной записью.
- хирургический (--visit-ids 12,34): пересчёт строк только ЭМК указанных
  визитов (resync_derma_history_for_visits), БЕЗ глобального DELETE —
  блокируется лишь диапазон затронутых визитов, годится под трафиком.

Запуск (от корня репо):
    python backend/scripts/resync_derma_history.py --database-url <url>
    CONFIRM_DERMA_HISTORY_RESYNC=1 python backend/scripts/resync_derma_history.py <url>
    python backend/scripts/resync_derma_history.py --database-url <url> --visit-ids 12,34

Аргументы понимает argparse (P2-2, owner fact-check 5625c8f1b: прежний
ручной парсер молча игнорировал задокументированные формы «--database-url
<url>» и позиционный «<url>», тихо подменяя цель из DATABASE_URL окружения
— пересчёт staging вместо prod с сообщением об успехе). Цель (хост/БД/режим)
печатается ПЕРЕД стартом: пересчёт не той БД — самый дорогой сценарий
молчаливой порчи.
"""

from __future__ import annotations

import argparse
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resync_derma_history.py",
        description=(
            "Пересчёт derma_history_entries из источников "
            "(полный — только в окне обслуживания; --visit-ids — "
            "хирургический, без глобального DELETE)."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="целевая БД (именно она будет ПЕРЕЗАПИСАНА); перекрывает "
        "позиционный url и DATABASE_URL окружения",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="позиционная форма целевой БД (не совмещать с --database-url)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="размер keyset-батча полного пересчёта "
        "(по умолчанию DEFAULT_REBUILD_BATCH_SIZE)",
    )
    parser.add_argument(
        "--visit-ids",
        default=None,
        help="список id визитов через запятую (12,34) — scoped-пересчёт "
        "без глобального DELETE; пустой список запрещён",
    )
    return parser


def resolve_database_url(args: argparse.Namespace, env: dict[str, str]) -> str:
    """--database-url > позиционный url > DATABASE_URL; конфликт — отказ."""
    from_flag = args.database_url
    from_positional = args.url
    if from_flag is not None and from_positional is not None:
        raise SystemExit(
            "error: переданы и --database-url, и позиционный url — "
            "укажите ровно один"
        )
    if from_flag is not None:
        return from_flag
    if from_positional is not None:
        return from_positional
    from_env = env.get("DATABASE_URL")
    if from_env:
        return from_env
    raise SystemExit(
        "error: DATABASE_URL is required (--database-url <url>, "
        "позиционный <url> или переменная окружения)"
    )


def parse_visit_ids(raw: str | None) -> list[int] | None:
    """'12,34' → [12, 34]; None → полный режим; мусор/пусто — отказ."""
    if raw is None:
        return None
    parts = [part.strip() for part in raw.split(",")]
    if not parts or any(not part for part in parts):
        raise SystemExit(f"error: invalid --visit-ids: {raw!r}")
    try:
        ids = [int(part) for part in parts]
    except ValueError:
        raise SystemExit(f"error: invalid --visit-ids: {raw!r}") from None
    return ids


def describe_target(database_url: str) -> str:
    """Человекочитаемая цель без секретов (пароль не печатается)."""
    from sqlalchemy.engine import make_url

    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        return f"sqlite database={url.database or ':memory:'}"
    return (
        f"{url.drivername} host={url.host} port={url.port} " f"database={url.database}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    database_url = resolve_database_url(args, dict(os.environ))
    visit_ids = parse_visit_ids(args.visit_ids)
    batch_size = args.batch_size

    require_confirmation()

    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.services.derma_history_projection import (
        DEFAULT_REBUILD_BATCH_SIZE,
        rebuild_derma_history_entries,
        resync_derma_history_for_visits,
    )

    if batch_size is not None and batch_size <= 0:
        print(f"invalid --batch-size: {batch_size}", file=sys.stderr)
        return 2

    # Цель — до любой записи (P2-1): пересчёт не той БД обязан быть
    # заметен ДО того, как DELETE уже прошёл по staging вместо prod.
    print(f"derma history resync target: {describe_target(database_url)}")
    if visit_ids is None:
        print(
            "mode: FULL rebuild — требует остановленной записи "
            "(runbook: окно обслуживания; под трафиком — --visit-ids)"
        )
    else:
        print(
            f"mode: scoped, visit_ids={visit_ids} "
            "(без глобального DELETE, безопасно под трафиком)"
        )

    engine = create_engine(database_url)
    if visit_ids is None:
        with engine.begin() as connection:
            counts = rebuild_derma_history_entries(
                connection,
                batch_size=batch_size or DEFAULT_REBUILD_BATCH_SIZE,
            )
    else:
        with Session(engine) as session:
            counts = resync_derma_history_for_visits(session, visit_ids)
            session.commit()
    print("derma_history_entries resync complete:")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
