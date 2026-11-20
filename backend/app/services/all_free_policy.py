"""Transaction-scoped coordination of the all-free auto-approval policy.

Every writer of the setting must acquire the same lock before observing or
changing it. Request creation acquires it before Visit and financial locks.
The lock covers an absent row as well as an existing one; this module never
commits or contacts external services.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings

ALL_FREE_AUTO_APPROVE_KEY = "all_free_auto_approve"
# Dedicated signed bigint namespace for pg_advisory_xact_lock.
_ALL_FREE_POLICY_LOCK = 0x414C4C4652454531


def lock_all_free_policy(db: Session) -> None:
    """Serialize policy readers/writers for the entire database transaction.

    A PostgreSQL repeatable-read snapshot taken before waiting cannot be
    refreshed by a second SELECT. Fail closed instead of approving under a
    stale policy. SQLite reserves its database writer lock even when the row
    is absent; a contention/busy error is likewise propagated to the caller.
    """
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        isolation = db.execute(text("SHOW transaction_isolation")).scalar_one()
        if isolation not in {"read committed", "read uncommitted"}:
            raise RuntimeError("All-free policy requires read committed isolation")
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ALL_FREE_POLICY_LOCK})
    elif dialect == "sqlite":
        db.execute(text("UPDATE clinic_settings SET id=id WHERE 0"))
    else:
        raise RuntimeError("Unsupported database for all-free policy locking")


def load_all_free_auto_approve(db: Session) -> bool:
    """Return the fresh canonical policy as bool while retaining its lock."""
    lock_all_free_policy(db)
    row = (
        db.query(ClinicSettings)
        .filter(ClinicSettings.key == ALL_FREE_AUTO_APPROVE_KEY)
        .populate_existing()
        .first()
    )
    return row is not None and str(row.value).strip().lower() in {"1", "true", "yes", "on"}
