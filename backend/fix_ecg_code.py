"""Inspect or repair legacy ECG service codes in the configured database."""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text

ECG_NAME = "\u042d\u041a\u0413"
ECHO_NAME = "\u042d\u0445\u043e\u041a\u0413"


def _is_sqlite_url(url: str) -> bool:
    return url.lower().startswith(("sqlite://", "sqlite+"))


def _allow_sqlite_database_url() -> bool:
    raw = os.getenv("ALLOW_SQLITE_DATABASE_URL", "")
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}


def _required_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    if _is_sqlite_url(url) and not _allow_sqlite_database_url():
        raise SystemExit(
            "SQLite DATABASE_URL is disabled for fix_ecg_code.py. "
            "Use PostgreSQL as the schema source of truth, or set "
            "ALLOW_SQLITE_DATABASE_URL=1 only for explicit legacy tools/tests."
        )
    return url


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect ECG/EchoCG service-code drift. By default this is read-only."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply repair updates. Requires CONFIRM_FIX_ECG_CODE_APPLY=1."
        ),
    )
    return parser.parse_args()


def _require_apply_confirmation() -> None:
    if os.getenv("CONFIRM_FIX_ECG_CODE_APPLY") != "1":
        raise SystemExit(
            "Refusing to update services. Set CONFIRM_FIX_ECG_CODE_APPLY=1 "
            "and pass --apply only after a read-only inspection."
        )


def _print_candidate_rows(conn) -> None:
    rows = conn.execute(
        text(
            """
            SELECT id, name, code, service_code, category_code
            FROM services
            WHERE service_code IN ('K10', 'K11', 'K002', 'K003', 'ECG01', 'CARD_ECG')
               OR name LIKE :ecg_pattern
               OR name LIKE :echo_pattern
            ORDER BY id
            """
        ),
        {"ecg_pattern": f"%{ECG_NAME}%", "echo_pattern": f"%{ECHO_NAME}%"},
    )
    print("\nServices with ECG/EchoCG candidates:")
    for row in rows:
        print(
            "  ID={0}, name={1}, code={2}, service_code={3}, category_code={4}".format(
                row[0], row[1], row[2], row[3], row[4]
            )
        )


def main() -> int:
    args = _parse_args()
    try:
        database_url = _required_database_url()
        if args.apply:
            _require_apply_confirmation()
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    engine = create_engine(database_url, future=True)
    if not args.apply:
        with engine.connect() as conn:
            _print_candidate_rows(conn)
        print("\nRead-only inspection complete. No rows were updated.")
        return 0

    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE services
                SET service_code='K10', category_code='K'
                WHERE name=:ecg_name OR service_code='ECG01'
                """
            ),
            {"ecg_name": ECG_NAME},
        )
        print(f"Updated {result.rowcount} rows")
        _print_candidate_rows(conn)

    print("\nDone!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
