"""Production pre-check for migration 0048_doctors_user_id_unique (READ-ONLY).

Run this BEFORE applying the migration on production/staging:

    cd backend
    python scripts/precheck_doctors_user_id_unique.py \
        --database-url "postgresql+psycopg://user:pass@host/clinic"

(or export DATABASE_URL and omit --database-url).

The script never writes anything. It reports:

  1. Duplicate User<->Doctor links (same users.id referenced by more than one
     doctors row). If any exist, migration 0048 will HARD-STOP (RuntimeError).
     They must be resolved manually first — the migration never deletes,
     merges or reassigns rows automatically.

  2. Userless Doctor rows (doctors.user_id IS NULL). These stay legal after
     the migration (NULLs are exempt from the UNIQUE constraint), but ACTIVE
     userless doctors are a data-quality finding: per the approved
     architecture decision #13, an active system Doctor requires a linked
     User. If active userless doctors exist, PAUSE the rollout of the
     follow-up hard validation and report the inventory to the architecture
     decision maker. Do NOT delete or auto-link them.

Exit codes:
    0 — clean: safe to run `alembic upgrade head`.
    1 — active userless doctors found: migration itself will pass, but the
        hard-validation rollout must pause and the inventory must be reported.
    2 — duplicate links found: migration will hard-stop; resolve manually.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0048 = (
    BACKEND_ROOT / "alembic" / "versions" / "0048_doctors_user_id_unique.py"
)


def _load_migration_duplicate_checker():
    """Load the migration module so the pre-check uses the EXACT same
    duplicate-detection logic as the migration hard-stop (single source of
    truth — no SQL drift between pre-check and migration)."""
    spec = importlib.util.spec_from_file_location("mig_0048", MIGRATION_0048)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _redact(url: str) -> str:
    try:
        return sa.engine.url.make_url(url).render_as_string(hide_password=True)
    except Exception:  # pragma: no cover - defensive
        return "<unparseable-url>"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only pre-check for migration 0048 (doctors.user_id UNIQUE)."
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL of the target DB. Falls back to DATABASE_URL env.",
    )
    args = parser.parse_args()

    url = args.database_url or os.getenv("DATABASE_URL")
    if not url:
        print(
            "ERROR: no database URL. Pass --database-url or export DATABASE_URL. "
            "Refusing to guess the target DB for a production pre-check."
        )
        return 2

    engine = sa.create_engine(url)
    checker = _load_migration_duplicate_checker()

    with engine.connect() as conn:
        dialect = conn.dialect.name
        print(f"Target DB : {_redact(url)}")
        print(f"Dialect   : {dialect}")
        print(f"Read-only : yes (no statements that modify data are issued)\n")

        total, linked = conn.execute(
            sa.text("SELECT COUNT(*), COUNT(user_id) FROM doctors")
        ).fetchone()
        print(f"doctors rows: total={total}, with user_id linked={linked}, userless={total - linked}")

        # ---- Section 1: duplicate User<->Doctor links (migration hard-stop) --
        duplicates = checker._duplicate_user_ids(conn)
        print("\n=== 1. Duplicate User<->Doctor links (blocks migration 0048) ===")
        if duplicates:
            for user_id, cnt in duplicates:
                doctors = conn.execute(
                    sa.text(
                        "SELECT id, specialty, active FROM doctors "
                        "WHERE user_id = :uid ORDER BY id"
                    ),
                    {"uid": user_id},
                ).fetchall()
                print(f"  user_id={user_id} -> {cnt} doctor rows: {doctors}")
            print(
                "\n  RESULT: FAIL — migration 0048 will HARD-STOP. Resolve the "
                "duplicates manually (keep the correct doctors.user_id, set the "
                "wrong rows to NULL), then re-run this pre-check."
            )
            dup_fail = True
        else:
            print("  RESULT: OK — no duplicate links.")
            dup_fail = False

        # ---- Section 2: userless doctors inventory (decision #13) ------------
        print("\n=== 2. Userless Doctor rows (doctors.user_id IS NULL) ===")
        userless = conn.execute(
            sa.text(
                "SELECT id, specialty, active FROM doctors "
                "WHERE user_id IS NULL ORDER BY active DESC, id"
            )
        ).fetchall()
        active_userless = [row for row in userless if row[2]]
        if not userless:
            print("  RESULT: OK — no userless doctor rows.")
        else:
            print(f"  Found {len(userless)} userless doctor row(s) (legal after migration):")
            for doc_id, specialty, active in userless:
                state = "ACTIVE" if active else "inactive"
                print(f"    doctor_id={doc_id} specialty={specialty!r} [{state}]")
            if active_userless:
                print(
                    f"\n  RESULT: ATTENTION — {len(active_userless)} ACTIVE userless "
                    "doctor(s). Per architecture decision #13 an active system Doctor "
                    "requires a linked User: PAUSE the rollout of the follow-up hard "
                    "validation and report this inventory to the architecture decision "
                    "maker. Do NOT delete or auto-link these rows."
                )
            else:
                print("  RESULT: OK — all userless rows are inactive (historical).")

    engine.dispose()

    if dup_fail:
        print("\nPRE-CHECK VERDICT: BLOCKED (exit 2) — resolve duplicates before migration.")
        return 2
    if active_userless:
        print(
            "\nPRE-CHECK VERDICT: REPORT REQUIRED (exit 1) — migration will pass, "
            "but active userless doctors exist: report inventory before hard-validation rollout."
        )
        return 1
    print("\nPRE-CHECK VERDICT: CLEAN (exit 0) — safe to run `alembic upgrade head`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
