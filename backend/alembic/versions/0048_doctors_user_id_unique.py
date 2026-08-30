"""INVARIANT: UNIQUE on doctors.user_id (1 physical doctor = 1 User + 1 Doctor).

Enforces the business invariant
    1 physical doctor = 1 User account + 1 Doctor profile
at the database level, so the identity chain

    username/password -> JWT -> User.id -> Doctor.user_id (UNIQUE) -> Doctor.id

always resolves to exactly one Doctor.

PRECONDITION (hard stop)
------------------------
Before applying the constraint this migration checks for existing duplicate
links (the same users.id referenced by more than one doctors row). If any are
found, the migration REFUSES to run and prints the offending user_id values.
Duplicates must be resolved manually by the clinic operator (medical data
safety: this migration never deletes or merges anything automatically).

PostgreSQL semantics: a UNIQUE constraint on a nullable column allows any
number of NULLs, so userless Doctor rows (doctors.user_id IS NULL, historical
data) remain legal.

POSTCONDITION
-------------
    uq_doctors_user_id UNIQUE constraint exists on doctors.user_id
    AND is verified to cover exactly the user_id column.

SCHEMA-DRIFT GUARD
------------------
A drifted database can already contain a constraint named
``uq_doctors_user_id`` on DIFFERENT columns. Accepting it by name only would
stamp this revision while ``doctors.user_id`` stays non-unique, silently
re-enabling duplicate doctor identities. Therefore an existing constraint is
accepted ONLY when its reflected definition is exactly
``UNIQUE(user_id)`` (name match + column_names == ['user_id']). Any other
definition — or an unreflectable one — aborts the migration with a loud
RuntimeError and no rows modified.

ROLLBACK / RECOVERY
-------------------
Downgrade simply drops the constraint; it never touches data. Application
level duplicate checks (admin_doctors create/update) remain in place either
way, so dropping the constraint does not enable silent duplication - it only
removes the DB-level backstop.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op

# Revision identifiers — chained after 0047_user_sessions_kind.
revision = "0048_doctors_user_id_unique"
down_revision = "0047_user_sessions_kind"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_doctors_user_id"


def _duplicate_user_ids(conn: sa.Connection) -> list[tuple[int | None, int]]:
    """Return [(user_id, link_count)] for user_ids linked by >1 doctor rows."""
    rows = conn.execute(
        sa.text(
            "SELECT user_id, COUNT(*) AS cnt "
            "FROM doctors "
            "WHERE user_id IS NOT NULL "
            "GROUP BY user_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _find_named_unique_constraint(inspector: Inspector, table: str, name: str):
    """Return the reflected UNIQUE-constraint dict with ``name``, else None."""
    for uq in inspector.get_unique_constraints(table):
        if uq.get("name") == name:
            return uq
    return None


def _assert_valid_user_id_constraint(uq: dict | None, phase: str) -> None:
    """Accept ``uq_doctors_user_id`` ONLY as UNIQUE(doctors.user_id).

    Schema drift can present a constraint with the expected name but on
    different columns; silently accepting it would stamp the revision while
    ``doctors.user_id`` stays non-unique. Refuse loudly instead: abort the
    migration, leave every row untouched. An unreflectable definition
    (missing column_names) is treated as drift too — fail closed.
    """
    if uq is None:
        return
    columns = list(uq.get("column_names") or [])
    if columns != ["user_id"]:
        raise RuntimeError(
            f"MIGRATION ABORTED ({phase}): constraint {CONSTRAINT_NAME} "
            f"already exists on table `doctors` but covers columns "
            f"{columns!r}, expected exactly UNIQUE(user_id). This is schema "
            "drift: stamping revision "
            f"{revision!r} now would leave doctors.user_id non-unique and "
            "re-enable duplicate doctor identities. Rename/drop the drifted "
            "constraint manually (or recreate it correctly) and re-run "
            "`alembic upgrade head`. No rows were modified by this run."
        )


def upgrade() -> None:
    conn = op.get_bind()

    # ---- precondition: hard stop on duplicate User<->Doctor links ----------
    duplicates = _duplicate_user_ids(conn)
    if duplicates:
        details = ", ".join(
            f"user_id={user_id} ({cnt} doctor rows)" for user_id, cnt in duplicates
        )
        # Medical data safety: never delete / merge / reassign automatically.
        raise RuntimeError(
            "MIGRATION ABORTED: found duplicate User<->Doctor links; "
            f"doctors.user_id must be unique but {len(duplicates)} user_id "
            f"value(s) are linked to multiple doctors: {details}. "
            "Resolve the duplicates manually (decide which doctors.user_id "
            "is correct, set the wrong rows to NULL) and re-run "
            "`alembic upgrade head`. No rows were modified by this run."
        )

    # sa.inspect() is the SQLAlchemy 2.0 way to obtain an Inspector
    # (Inspector.from_engine() is deprecated and slated for removal).
    inspector = sa.inspect(conn)
    existing = _find_named_unique_constraint(inspector, "doctors", CONSTRAINT_NAME)
    if existing is not None:
        # Idempotent re-run: accept the pre-existing constraint ONLY when its
        # definition really is UNIQUE(user_id) — a same-name/different-columns
        # constraint is schema drift and must abort, not be silently stamped.
        _assert_valid_user_id_constraint(existing, "precondition")
        return

    # SQLite (dev/test) does not support ADD CONSTRAINT; batch mode handles it
    # by table rebuild. PostgreSQL (production) uses a plain ALTER TABLE.
    with op.batch_alter_table("doctors") as batch_op:
        batch_op.create_unique_constraint(CONSTRAINT_NAME, ["user_id"])

    # ---- postcondition ------------------------------------------------------
    # Same strictness as the precondition: the constraint must exist AND cover
    # exactly doctors.user_id (name-only acceptance would tolerate drift).
    inspector = sa.inspect(conn)
    created = _find_named_unique_constraint(inspector, "doctors", CONSTRAINT_NAME)
    if created is None:
        raise RuntimeError(
            f"MIGRATION POSTCONDITION FAILED: constraint {CONSTRAINT_NAME} "
            "was not created (check DB permissions / dialect support)."
        )
    _assert_valid_user_id_constraint(created, "postcondition")


def downgrade() -> None:
    # Rollback is data-safe: dropping the constraint never deletes rows.
    inspector = sa.inspect(op.get_bind())
    names = {
        uq["name"]
        for uq in inspector.get_unique_constraints("doctors")
        if uq.get("name")
    }
    if CONSTRAINT_NAME in names:
        with op.batch_alter_table("doctors") as batch_op:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
