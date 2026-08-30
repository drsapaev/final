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

  1b. Existing uq_doctors_user_id definition (schema drift). The migration
     accepts the constraint ONLY as UNIQUE(user_id): a same-name constraint
     on DIFFERENT columns makes upgrade() HARD-STOP, so this checker applies
     the SAME definition validation (single source of truth: the migration's
     own _assert_valid_user_id_constraint) and never reports a false green.

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
    2 — migration will hard-stop: duplicate links found AND/OR a drifted
        uq_doctors_user_id constraint exists; resolve manually.
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

        # ---- Section 1b: schema-drift of uq_doctors_user_id -----------------
        # The migration accepts an existing uq_doctors_user_id ONLY when its
        # reflected definition is exactly UNIQUE(user_id) — a same-name/
        # different-columns constraint is drift and upgrade() HARD-STOPS on
        # it. Report the SAME condition here so the prescribed rollout check
        # never gives operators a false green result.
        print("\n=== 1b. Existing uq_doctors_user_id definition (drift check) ===")
        inspector = sa.inspect(conn)
        existing_uq = checker._find_named_unique_constraint(
            inspector, "doctors", checker.CONSTRAINT_NAME
        )
        if existing_uq is None:
            print(
                "  RESULT: OK — no existing uq_doctors_user_id; "
                "migration 0048 will create it."
            )
            drift_fail = False
        else:
            try:
                checker._assert_valid_user_id_constraint(
                    existing_uq, "pre-check"
                )
            except RuntimeError as exc:
                print(f"  RESULT: FAIL — {exc}")
                drift_fail = True
            else:
                print(
                    "  RESULT: OK — uq_doctors_user_id already exists as "
                    "UNIQUE(user_id); upgrade() is a no-op (idempotent)."
                )
                drift_fail = False

        # Name-namespace check: a unique INDEX named uq_doctors_user_id (any
        # columns) is not reflected as a constraint but STILL collides with
        # the constraint name on PostgreSQL (constraints and indexes share
        # one namespace) — upgrade() would die on a raw duplicate-name error.
        # Report it here so the rollout check stays ahead of the migration.
        #
        # The scan runs ONLY when no same-named CONSTRAINT exists (Codex
        # round-3 P2): when the constraint is present — valid or drifted,
        # both handled above — any same-name index is the index BACKING that
        # constraint (PostgreSQL auto-creates one; reflection marks it with
        # duplicates_constraint) and must be left alone, not reported as a
        # collision on an idempotent rerun.
        colliding_indexes = []
        if existing_uq is None:
            colliding_indexes = [
                idx
                for idx in inspector.get_indexes("doctors")
                if idx.get("name") == checker.CONSTRAINT_NAME
                and idx.get("duplicates_constraint") != checker.CONSTRAINT_NAME
            ]
        if colliding_indexes:
            print(
                f"  RESULT: FAIL — an INDEX named {checker.CONSTRAINT_NAME!r} "
                f"already exists on `doctors` (columns="
                f"{colliding_indexes[0].get('column_names')!r}, "
                "unique="
                f"{colliding_indexes[0].get('unique')!r}). On PostgreSQL the "
                "constraint name would collide with this index and "
                "upgrade() would abort with a duplicate-name error. Drop or "
                "rename the index manually, then re-run this pre-check."
            )
            drift_fail = True
        elif existing_uq is None and not drift_fail:
            print(
                "  RESULT: OK — no index name collision with "
                f"{checker.CONSTRAINT_NAME!r}."
            )

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

    if dup_fail or drift_fail:
        reasons = []
        if dup_fail:
            reasons.append("resolve duplicates")
        if drift_fail:
            reasons.append("fix the drifted uq_doctors_user_id constraint")
        print(
            "\nPRE-CHECK VERDICT: BLOCKED (exit 2) — "
            + " and ".join(reasons)
            + " before migration."
        )
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
