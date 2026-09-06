"""Lab resource internal role — lab_resource 'Lab' → 'Resource' sentinel.

QD-1.2 of the desk-queue-join track (operator decision, 2026-09-06,
final ruling D1). 0055_queue_resource_provisioning seeded three
doctorless-queue resource accounts; 0056 (QD-1.1) moved
ecg_resource/general_resource off the retired 'Nurse' spelling to the
internal-only 'Resource' sentinel, deliberately leaving lab_resource
on role='Lab' — "whether that account is a human Lab login or should
become a Resource row is a separate inventory decision (QD-1.2)".

That inventory is closed: lab_resource is NOT a human login. It is the
same synthetic queue-machinery row as its two siblings (unusable
'!disabled:' seed password, no email, owns the 'lab' doctorless
queue through a linked Doctor row), but carrying a REAL product role
exposed it through every human surface the QD-1.1 role guards
protect for the other two sentinels:

- user-management listing shows it and by-ID mutations accept it
  (the Lab grants behind the role are real: queue-ops read/write,
  EMR lab integration, audit, global search, AI) — a set-password
  there would turn a queue sentinel into a privileged login;
- its Doctor row is visible and mutable in /admin/doctors —
  deactivation would silently break the lab doctorless-queue
  resolution and is irreversible (the ghost-state guard rejects
  reactivation for a non-doctor-family owner);
- booking doctor selectors (mobile list/search, registrar) offer
  the resource row — picking it fails booking eligibility with a
  guaranteed 409.

The fix reuses the 0056 mechanism UNCHANGED: the exact synthetic row
moves to the internal-only 'Resource' sentinel spelling
(core/roles.py INTERNAL_ONLY_ROLE_SPELLINGS SSOT), and every
role-based guard — auth-layer login block on all credential and
token surfaces, user-management listing/mutation freeze, admin
doctor read-only surface, booking-selector exclusion — starts
applying automatically. No username-based exceptions are added and
no existing Resource guard is weakened; 'Lab' remains a fully
legitimate product role for humans (enum, STAFF_ROLES, hierarchy,
roles catalog/options — all untouched).

Migration contract (operator decision D1, strict):

- upgrade A — exactly one user row with username='lab_resource' in
  role='Lab' plus exactly one linked Doctor row
  (doctors.user_id = user.id, doctors.specialty='lab')
  → UPDATE that row only: role='Resource';
- upgrade B — the same state with role='Resource' already
  → idempotent no-op (protects incident-drifted environments that
  applied the fix by hand);
- anything else — missing user, duplicate username rows, unexpected
  role spelling, missing Doctor linkage, duplicate linkage, wrong
  specialty → RuntimeError, ABORT with no rows changed;
- never a broad ``UPDATE users WHERE role='Lab'`` — human Lab staff
  are untouched by construction (exact-username targeting).

Lifecycle invariant (operator decision): the migration touches ONLY
users.role — User.is_active, hashed_password, Doctor.active,
Doctor.specialty and Doctor.user_id stay exactly as seeded. Live
queue resolvers (wizard/morning-assignment prepare, batch create,
visit confirmation) resolve username + is_active → User → Doctor,
so the sentinel must remain an active, linked row; non-login is
enforced by the auth-layer role guard, not by deactivation
(the same ruling 0056 applied to its two rows).

Downgrade is strict and symmetric: the exact username row must
currently be role='Resource' with the same valid Doctor linkage,
otherwise it aborts. It restores role='Lab' — which ALSO restores
the historical security exposure documented above; it exists for
reversibility of the schema history, not as a routine production
operation.

The upgrade/downgrade logic lives in module-level functions so tests
can run them against a scratch SQLite connection without an alembic
context.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0056_queue_resource_role_cleanup.
revision = "0057_lab_resource_internal_role"
down_revision = "0056_queue_resource_role_cleanup"
branch_labels = None
depends_on = None

_SENTINEL_USERNAME = "lab_resource"
_EXPECTED_SPECIALTY = "lab"

_FETCH_STATE = sa.text(
    """
    SELECT
        u.id AS user_id,
        u.role AS role,
        (SELECT COUNT(*) FROM doctors d WHERE d.user_id = u.id) AS linked_doctor_rows,
        (SELECT COUNT(*) FROM doctors d
            WHERE d.user_id = u.id AND d.specialty = :expected_specialty
        ) AS matching_doctor_rows
    FROM users u
    WHERE u.username = :expected_username
    """
)

_MOVE_TO_SENTINEL = sa.text(
    """
    UPDATE users SET role = 'Resource'
    WHERE id = :user_id
    """
)

_RESTORE_LAB_ROLE = sa.text(
    """
    UPDATE users SET role = 'Lab'
    WHERE id = :user_id
    """
)

_MIGRATION_NAME = "0057_lab_resource_internal_role"


def _fetch_expected_state(conn) -> tuple[int, str]:
    """Validate the exact lab_resource row + Doctor linkage state.

    Returns (user_id, role) when the row matches the contract:
    exactly one username row, role in ('Lab', 'Resource'), exactly
    one linked Doctor row carrying the expected 'lab' specialty.
    Anything else raises RuntimeError BEFORE any row is changed.
    """
    rows = conn.execute(
        _FETCH_STATE,
        {
            "expected_username": _SENTINEL_USERNAME,
            "expected_specialty": _EXPECTED_SPECIALTY,
        },
    ).fetchall()

    if len(rows) != 1:
        raise RuntimeError(
            f"{_MIGRATION_NAME} precondition failed: expected exactly one "
            f"user row with username={_SENTINEL_USERNAME!r}, found "
            f"{len(rows)}; aborting with no rows changed"
        )

    user_id, role, linked_doctor_rows, matching_doctor_rows = rows[0]

    if role not in ("Lab", "Resource"):
        raise RuntimeError(
            f"{_MIGRATION_NAME} precondition failed: unexpected role "
            f"{role!r} for username={_SENTINEL_USERNAME!r} (expected "
            "'Lab' or the already-migrated 'Resource'); aborting with "
            "no rows changed"
        )

    if linked_doctor_rows == 0:
        raise RuntimeError(
            f"{_MIGRATION_NAME} precondition failed: username="
            f"{_SENTINEL_USERNAME!r} has no linked Doctor row "
            f"(expected doctors.user_id linkage with specialty="
            f"{_EXPECTED_SPECIALTY!r}); aborting with no rows changed"
        )
    if linked_doctor_rows > 1:
        raise RuntimeError(
            f"{_MIGRATION_NAME} precondition failed: duplicate Doctor "
            f"linkage for username={_SENTINEL_USERNAME!r} "
            f"({linked_doctor_rows} rows); aborting with no rows changed"
        )
    if matching_doctor_rows != 1:
        raise RuntimeError(
            f"{_MIGRATION_NAME} precondition failed: the linked Doctor "
            f"row for username={_SENTINEL_USERNAME!r} does not carry the "
            f"expected specialty {_EXPECTED_SPECIALTY!r}; aborting with "
            "no rows changed"
        )

    return int(user_id), str(role)


def _apply_lab_resource_internal_role(conn) -> None:
    """Move the lab_resource row to the 'Resource' sentinel (upgrade).

    State A ('Lab' + valid linkage) converts; state B (already
    'Resource') is an idempotent no-op. Any drift aborts with no rows
    changed. Only users.role is written — the lifecycle invariant
    (is_active, password, Doctor linkage/active/specialty) is
    preserved by construction and re-verified post-update.
    """
    user_id, role = _fetch_expected_state(conn)

    if role == "Resource":
        # Already migrated (e.g. hand-applied during an incident):
        # accept as a no-op instead of blocking the deploy.
        return

    conn.execute(_MOVE_TO_SENTINEL, {"user_id": user_id})

    # Postcondition: same row, sentinel spelling, linkage intact.
    after_user_id, after_role = _fetch_expected_state(conn)
    if after_user_id != user_id or after_role != "Resource":
        raise RuntimeError(
            f"{_MIGRATION_NAME} postcondition failed: expected "
            f"(user_id={user_id}, role='Resource') after the update, "
            f"found (user_id={after_user_id}, role={after_role!r})"
        )


def _restore_lab_resource_role(conn) -> None:
    """Downgrade core: return the exact row to the 0055 'Lab' spelling.

    Strict symmetric precondition — the row must currently be
    role='Resource' with the valid Doctor linkage; anything else
    aborts. Restoring 'Lab' re-opens the human-surface exposure this
    migration closed (see the module docstring); this exists for
    schema-history reversibility, not as a routine production
    operation.
    """
    user_id, role = _fetch_expected_state(conn)

    if role != "Resource":
        raise RuntimeError(
            f"{_MIGRATION_NAME} downgrade failed: expected role="
            f"'Resource' for username={_SENTINEL_USERNAME!r}, found "
            f"{role!r}; aborting with no rows changed"
        )

    conn.execute(_RESTORE_LAB_ROLE, {"user_id": user_id})

    after_user_id, after_role = _fetch_expected_state(conn)
    if after_user_id != user_id or after_role != "Lab":
        raise RuntimeError(
            f"{_MIGRATION_NAME} downgrade postcondition failed: expected "
            f"(user_id={user_id}, role='Lab') after the downgrade, found "
            f"(user_id={after_user_id}, role={after_role!r})"
        )


def upgrade() -> None:
    _apply_lab_resource_internal_role(op.get_bind())


def downgrade() -> None:
    _restore_lab_resource_role(op.get_bind())
