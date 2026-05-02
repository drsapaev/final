from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _configure_path() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run EMR v2 hard-cutover verification and backfill operations."
    )
    parser.add_argument(
        "mode",
        choices=("verify", "dry-run", "live"),
        help="Operation mode: verify invariants, preview backfill, or run live backfill.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for one backfill batch.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.mode == "live":
        os.environ["EMR_LEGACY_WRITE_FREEZE"] = "1"

    _configure_path()

    from app.db.session import SessionLocal
    from app.services.emr_cutover_service import EMRCutoverService

    db = SessionLocal()
    try:
        service = EMRCutoverService(db)
        if args.mode == "verify":
            result = service.verify_cutover()
        elif args.mode == "dry-run":
            result = service.migrate_legacy_emrs(
                dry_run=True,
                limit=args.limit,
            )
        else:
            result = service.migrate_legacy_emrs(
                dry_run=False,
                limit=args.limit,
            )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                sort_keys=True,
                default=str,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
