#!/usr/bin/env python3
"""Blocking pre-deploy reconciliation: active userless Doctor rows.

Lifecycle invariant (decision #13, Codex round-7 P2): a NORMAL active
system Doctor must have a linked User account. The API validators enforce
this for every NEW/CHANGED doctor row, but rows that already existed on
deployments predating the invariant (the old API permitted
``Doctor(active=True, user_id=NULL)``) are never re-validated by the API —
they stay visible through active-doctor selectors and pass
``ensure_doctor_eligible_for_appointment``, leaving the declared invariant
unenforced for existing data.

This script is the referenced production pre-check (see the comment on
``_validate_active_doctor_has_user``). It performs an inventory of
violating rows and BLOCKS (exit code 1) when any exist, so the deployment
pipeline stops until an operator resolves them (link a User via
AdminDoctors -> "Add doctor", or deactivate the profile — no deletion, no
auto-link, mirroring the API contract).

Exit codes:
    0 — clean: no active userless Doctor rows;
    1 — blocked: at least one active userless Doctor row exists;
    2 — operational failure (missing DATABASE_URL, connection error).

Usage:
    DATABASE_URL=postgresql+psycopg://... python backend/scripts/reconcile_userless_active_doctors.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def find_userless_active_doctors(db) -> list:
    """Return Doctor rows with active=True and user_id NULL (decision #13
    violations among existing data)."""
    from sqlalchemy import and_

    from app.models.clinic import Doctor

    return (
        db.query(Doctor)
        .filter(
            and_(
                Doctor.active.is_(True),
                Doctor.user_id.is_(None),
            )
        )
        .all()
    )


def build_inventory(rows) -> list[dict]:
    """Build the operator-facing inventory for violating rows (no PII —
    Doctor rows carry specialty/cabinet/price data only)."""
    return [
        {
            "doctor_id": row.id,
            "specialty": row.specialty,
            "cabinet": row.cabinet,
            "active": bool(row.active),
        }
        for row in rows
    ]


def _open_session():
    """Open a session using the app's DATABASE_URL resolution.

    Imported lazily so `--help` works without a configured environment.
    """
    from app.db.session import SessionLocal

    return SessionLocal()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Blocking pre-deploy check: active userless Doctor rows."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the machine-readable inventory instead of a table.",
    )
    args = parser.parse_args(argv)

    if not (os.getenv("DATABASE_URL") or "").strip():
        print(
            "DATABASE_URL is not set — refusing to run against an unknown "
            "database.",
            file=sys.stderr,
        )
        return 2

    try:
        db = _open_session()
    except Exception as exc:
        print(f"Cannot open a database session: {exc}", file=sys.stderr)
        return 2

    try:
        rows = find_userless_active_doctors(db)
    except Exception as exc:
        print(f"Inventory query failed: {exc}", file=sys.stderr)
        return 2
    finally:
        try:
            db.close()
        except Exception:
            pass

    if not rows:
        print(
            "OK: no active userless Doctor rows — decision #13 invariant "
            "holds for existing data."
        )
        return 0

    inventory = build_inventory(rows)
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        print(
            f"BLOCKED: {len(rows)} active Doctor row(s) without a linked "
            "User account (decision #13 violation among existing data):"
        )
        for item in inventory:
            print(
                f"  - doctor_id={item['doctor_id']} "
                f"specialty={item['specialty']!r} cabinet={item['cabinet']!r}"
            )
        print(
            "Resolve before deploying: link a User via AdminDoctors -> "
            "'Add doctor', or deactivate the profile. No deletion, no "
            "auto-link."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
