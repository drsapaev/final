"""UNIQUE index on users.email (invariant formalization).

users.email has been treated as unique by application logic (login by
email, admin user management) since inception, but the database never
enforced it. Verified on production 2026-09-03: zero duplicate non-null
emails and zero empty-string emails — the invariant holds in data, this
revision makes it hold in schema.

- Guard: the upgrade FAILS LOUDLY if duplicates (or empty-string emails,
  which are de-facto duplicates waiting to happen) exist — it never
  silently drops or rewrites data. Deduplication is a human decision.
- The index is partial (email IS NOT NULL): multiple NULL emails remain
  allowed (User.email is nullable; NULL never conflicts).
- Chained after 0051_medical_specialty_catalog (the medical-specialty
catalog adopted its own revision id under the 0051_ filename).

Downgrade drops the index; the column returns to unenforced uniqueness.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0051_salary_tables_adoption.
revision = "0053_users_email_unique"
down_revision = "0052_merge_0051_branches"
branch_labels = None
depends_on = None

_GUARD = sa.text(
    """
    DO $$
    DECLARE
        dup_count integer;
    BEGIN
        SELECT count(*) INTO dup_count FROM (
            SELECT email FROM users
            WHERE email IS NOT NULL AND email <> ''
            GROUP BY email HAVING count(*) > 1
        ) d;
        IF dup_count > 0 THEN
            RAISE EXCEPTION 'users.email has % duplicate group(s); deduplicate before 0053_users_email_unique', dup_count;
        END IF;

        SELECT count(*) INTO dup_count FROM users WHERE email = '';
        IF dup_count > 0 THEN
            RAISE EXCEPTION 'users.email has % empty-string value(s); fix them to NULL before 0053_users_email_unique', dup_count;
        END IF;
    END $$
    """
)


def upgrade() -> None:
    op.execute(_GUARD)
    op.create_index(
        "uq_users_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_email", table_name="users")
