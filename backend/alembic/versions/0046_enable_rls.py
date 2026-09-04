"""Enable Row Level Security on every table in the public schema.

Production hardening (Supabase). The production PostgreSQL project is
exposed through the Supabase Data API (PostgREST) under the ``anon`` /
``authenticated`` roles, and the ``anon`` key is public by design.
Without RLS, any holder of that key can read and write every table in
``public`` — unacceptable for a medical records database.

Design decisions:

- RLS is enabled with **no policies** → deny-all for roles that do not
  bypass RLS (``anon``, ``authenticated``). Supabase's
  ``service_role`` has BYPASSRLS; its key must never leave the
  dashboard/secret storage.
- The application connects as the table owner (``postgres`` role via
  the Supabase session pooler). Table owners bypass RLS unless FORCE
  ROW LEVEL SECURITY is set, so the backend and the arq worker are
  unaffected. Verified live on 2026-08-18: owner-role queries succeed
  and ``SET ROLE anon → SELECT patients`` returns 0 rows.
- Object-level isolation between doctors/users (per-specialty access,
  BOLA/IDOR protection) is enforced at the application layer
  (``require_roles`` + specialty filters); the application never uses
  the Supabase API roles, so no RLS policies are needed for it.
- Idempotent: ``ENABLE ROW LEVEL SECURITY`` on an already-enabled
  table is a no-op. This revision therefore runs cleanly both on a
  fresh database (CI postgres service, new environments) and on the
  current production database (where RLS was first enabled manually
  on 2026-08-18; this revision makes that state reproducible from
  migration history instead of tribal knowledge).
- Future migrations that create new tables must enable RLS for their
  own tables, or a later revision must sweep again.

Downgrade disables RLS symmetrically. That re-exposes every table to
the Supabase API roles — only run it during a deliberate rollback
with the Data API exposure considered.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0045_payments_lock.
revision = "0046_enable_rls"
down_revision = "0045_payments_lock"
branch_labels = None
depends_on = None

_ENABLE_RLS = sa.text(
    """
    DO $$
    DECLARE r record;
    BEGIN
        FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
        END LOOP;
    END $$
    """
)

_DISABLE_RLS = sa.text(
    """
    DO $$
    DECLARE r record;
    BEGIN
        FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
            EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', r.tablename);
        END LOOP;
    END $$
    """
)


def upgrade() -> None:
    op.execute(_ENABLE_RLS)


def downgrade() -> None:
    op.execute(_DISABLE_RLS)
