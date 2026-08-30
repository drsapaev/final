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
    uq_doctors_user_id UNIQUE constraint exists on doctors.user_id.

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

    inspector = Inspector.from_engine(conn)
    existing = {
        uq["name"]
        for uq in inspector.get_unique_constraints("doctors")
        if uq.get("name")
    }
    if CONSTRAINT_NAME in existing:
        return  # already applied (idempotent re-run safety)

    # SQLite (dev/test) does not support ADD CONSTRAINT; batch mode handles it
    # by table rebuild. PostgreSQL (production) uses a plain ALTER TABLE.
    with op.batch_alter_table("doctors") as batch_op:
        batch_op.create_unique_constraint(CONSTRAINT_NAME, ["user_id"])

    # ---- postcondition ------------------------------------------------------
    inspector = Inspector.from_engine(conn)
    names = {
        uq["name"]
        for uq in inspector.get_unique_constraints("doctors")
        if uq.get("name")
    }
    if CONSTRAINT_NAME not in names:
        raise RuntimeError(
            f"MIGRATION POSTCONDITION FAILED: constraint {CONSTRAINT_NAME} "
            "was not created (check DB permissions / dialect support)."
        )


def downgrade() -> None:
    # Rollback is data-safe: dropping the constraint never deletes rows.
    inspector = Inspector.from_engine(op.get_bind())
    names = {
        uq["name"]
        for uq in inspector.get_unique_constraints("doctors")
        if uq.get("name")
    }
    if CONSTRAINT_NAME in names:
        with op.batch_alter_table("doctors") as batch_op:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
