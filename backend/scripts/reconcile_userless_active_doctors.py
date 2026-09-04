#!/usr/bin/env python3
"""Blocking pre-deploy reconciliation: Doctor linkage violations.

Lifecycle linkage contract (decision #13; Codex round-7/round-8 P2): a
NORMAL active system Doctor must have a live, doctor-role User account.
The API validators enforce this for every NEW/CHANGED doctor row, but rows
that already existed on deployments predating the invariant are never
re-validated by the API. Two violation classes among existing data:

- userless            — Doctor(active=True, user_id=NULL);
- legacy ghost owner  — Doctor(active=True) whose linked User is missing,
                        deactivated (deactivation predates lifecycle
                        mirroring), or carries a non-doctor role.

Such rows stay visible through active-doctor selectors and pass booking
eligibility guards (the eligibility runtime now rejects them too — see
app/services/appointment_eligibility.py — but a deployment must not even
start in that state). This script is the referenced production pre-check
(see the comment on _validate_active_doctor_has_user) and BLOCKS the
deploy: ops/backend.entrypoint.sh runs it after `alembic upgrade head`
and refuses to serve while violations exist.

Resolution (no deletion, no auto-link, mirroring the API contract): link a
live doctor-role User via AdminDoctors -> "Add doctor", or deactivate the
Doctor profile.

Exit codes:
    0 — clean: no linkage violations among active Doctor rows;
    1 — blocked: at least one violating row exists;
    2 — operational failure (missing DATABASE_URL, connection error).

Usage:
    DATABASE_URL=postgresql+psycopg://... python scripts/reconcile_userless_active_doctors.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def find_active_doctor_linkage_violations(db) -> list[tuple[object, str]]:
    """Return (doctor, reason) pairs for active Doctor rows violating the
    linkage contract.

    Reasons:
        userless               — active Doctor with no linked User;
        owner_missing          — user_id points to a row that is gone;
        owner_inactive         — linked User account is deactivated;
        owner_not_doctor_role  — linked User role is not doctor-family.
    """
    from sqlalchemy import and_

    from app.core.roles import is_doctor_role_spelling
    from app.models.clinic import Doctor
    from app.models.user import User

    rows = db.query(Doctor).filter(Doctor.active.is_(True)).all()
    # Single query for all candidate owners, then classify in Python.
    user_ids = {row.user_id for row in rows if row.user_id is not None}
    owners = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    violations: list[tuple[object, str]] = []
    for row in rows:
        if row.user_id is None:
            violations.append((row, "userless"))
            continue
        owner = owners.get(row.user_id)
        if owner is None:
            violations.append((row, "owner_missing"))
        elif not owner.is_active:
            violations.append((row, "owner_inactive"))
        elif not is_doctor_role_spelling(owner.role):
            violations.append((row, "owner_not_doctor_role"))
    return violations


def build_inventory(violations) -> list[dict]:
    """Build the operator-facing inventory for violating rows (no PII —
    Doctor/User rows carry clinical/username data only)."""
    return [
        {
            "doctor_id": row.id,
            "specialty": row.specialty,
            "cabinet": row.cabinet,
            "active": bool(row.active),
            "reason": reason,
        }
        for row, reason in violations
    ]


def _open_session():
    """Open a session using the app's DATABASE_URL resolution.

    Imported lazily so `--help` works without a configured environment.
    """
    from app.db.session import SessionLocal

    return SessionLocal()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Blocking pre-deploy check: Doctor linkage violations."
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
        violations = find_active_doctor_linkage_violations(db)
    except Exception as exc:
        print(f"Inventory query failed: {exc}", file=sys.stderr)
        return 2
    finally:
        try:
            db.close()
        except Exception:
            pass

    if not violations:
        print(
            "OK: no active Doctor rows violate the linkage contract — "
            "decision #13 invariant holds for existing data."
        )
        return 0

    inventory = build_inventory(violations)
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        print(
            f"BLOCKED: {len(violations)} active Doctor row(s) violate the "
            "linkage contract (decision #13 among existing data):"
        )
        for item in inventory:
            print(
                f"  - doctor_id={item['doctor_id']} "
                f"specialty={item['specialty']!r} "
                f"reason={item['reason']}"
            )
        print(
            "Resolve before deploying: link a live doctor-role User via "
            "AdminDoctors -> 'Add doctor', or deactivate the Doctor "
            "profile. No deletion, no auto-link."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
