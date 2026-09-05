"""Queue resource role cleanup — Nurse seed → internal 'Resource' sentinel.

QD-1.1 of the desk-queue-join track (follow-up to 0055 QD-0, operator
decision variant b, 2026-09-06). 0055_queue_resource_provisioning
seeded the doctorless-queue resource accounts with role='Nurse'
('ecg_resource', 'general_resource') — a spelling N-3 (#3054) had
retired from the RBAC vocabulary the same day under the verified
premise "0 stored rows". The seed broke that invariant: two synthetic
rows now carry the retired spelling in stored production data
(functionally inert — zero grants, unusable password — but the
vocabulary boundary is the product contract).

This migration restores the Nurse stored-count invariant by moving the
two synthetic rows to the internal-only 'Resource' sentinel spelling:

- 'Resource' is NOT a human/product role: absent from the Roles enum,
  the user-management write vocabulary, the roles catalog/options
  boundary and every grant list (guards in core/roles.py, QD-1.1);
- logins for the sentinel are rejected at the auth layer (structural
  non-login — the '!disabled:' password hash is not the defense, the
  role check is);
- QD-0 queue resolution is deliberately role-agnostic (username +
  is_active lookups in the wizard / morning-assignment / batch /
  visit-confirmation paths), so the queue machinery is unaffected.

Deliberately narrow (operator decision):

- ONLY the two known usernames, ONLY from the 'Nurse' spelling;
- strict precondition — exactly 2 matching rows, otherwise the
  migration ABORTS with no rows changed (never a broad rewrite of
  unexpected 'Nurse' data; unrelated 'Nurse' rows are never touched);
- already-migrated state (0 Nurse + 2 'Resource') passes as an
  idempotent no-op (protects incident-drifted environments that
  already applied the fix by hand);
- lab_resource KEEPS role='Lab' — a real product role; whether that
  account is a human Lab login or should become a Resource row is a
  separate inventory decision (QD-1.2), deliberately not made here;
- is_active is NOT touched: QD-0 lookups require is_active=true to
  resolve doctorless queues (proven by the wizard / morning-assignment
  filters), so the non-login invariant is enforced by the auth-layer
  role guard, not by deactivation.

The upgrade/downgrade logic lives in module-level functions so tests
can run them against a scratch SQLite connection without an alembic
context.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0055_queue_resource_provisioning.
revision = "0056_queue_resource_role_cleanup"
down_revision = "0055_queue_resource_provisioning"
branch_labels = None
depends_on = None

_COUNT_SEED_ROLE = sa.text(
    """
    SELECT COUNT(*) FROM users
    WHERE username IN ('ecg_resource', 'general_resource')
      AND role = 'Nurse'
    """
)

_COUNT_SENTINEL_ROLE = sa.text(
    """
    SELECT COUNT(*) FROM users
    WHERE username IN ('ecg_resource', 'general_resource')
      AND role = 'Resource'
    """
)

_MOVE_TO_SENTINEL = sa.text(
    """
    UPDATE users SET role = 'Resource'
    WHERE username IN ('ecg_resource', 'general_resource')
      AND role = 'Nurse'
    """
)

_RESTORE_SEED_ROLE = sa.text(
    """
    UPDATE users SET role = 'Nurse'
    WHERE username IN ('ecg_resource', 'general_resource')
      AND role = 'Resource'
    """
)


def _apply_resource_role_cleanup(conn) -> None:
    """Move the two seeded resource accounts to the 'Resource' sentinel.

    Precondition: exactly 2 rows carry role='Nurse' for the known
    resource usernames. An already-migrated database (2 rows already on
    'Resource') is an idempotent pass. Anything else aborts with no
    rows changed.
    """
    seed_rows = conn.execute(_COUNT_SEED_ROLE).scalar() or 0
    sentinel_rows = conn.execute(_COUNT_SENTINEL_ROLE).scalar() or 0

    if seed_rows == 2:
        conn.execute(_MOVE_TO_SENTINEL)
    elif seed_rows == 0 and sentinel_rows == 2:
        # Already migrated (e.g. hand-applied during an incident):
        # accept as a no-op instead of blocking the deploy.
        return
    else:
        raise RuntimeError(
            "0056_queue_resource_role_cleanup precondition failed: "
            "expected exactly 2 'Nurse' resource rows (or the "
            "already-migrated 2x'Resource' state), found "
            f"Nurse={seed_rows}, Resource={sentinel_rows}; "
            "aborting with no rows changed"
        )

    remaining_seed = conn.execute(_COUNT_SEED_ROLE).scalar() or 0
    final_sentinel = conn.execute(_COUNT_SENTINEL_ROLE).scalar() or 0
    if remaining_seed != 0 or final_sentinel != 2:
        raise RuntimeError(
            "0056_queue_resource_role_cleanup postcondition failed: "
            f"Nurse={remaining_seed}, Resource={final_sentinel} "
            "after the update"
        )


def _restore_resource_seed_roles(conn) -> None:
    """Downgrade core: return the two rows to the 0055 seed spelling."""
    conn.execute(_RESTORE_SEED_ROLE)


def upgrade() -> None:
    _apply_resource_role_cleanup(op.get_bind())


def downgrade() -> None:
    _restore_resource_seed_roles(op.get_bind())
