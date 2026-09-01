"""Re-sweep ENABLE ROW LEVEL SECURITY across all public tables (salary drift).

Supabase Advisor raised ``rls_disabled_in_public`` (P1): production had two
public tables without RLS — ``salary_history`` and ``salary_payments``.
Both are owned by ``backend/app/models/salary_history.py`` but were created
in production out-of-band: no Alembic revision creates them, so the
``0046_enable_rls`` sweep of 2026-08-18 never covered them (verified live
2026-09-02: 171/173 public tables had RLS on; only these two were off).

This revision repeats the 0046 sweep with identical semantics:

- Idempotent ``ENABLE ROW LEVEL SECURITY`` for every table in ``public``.
- No policies → deny-all for roles that do not bypass RLS. The Supabase
  Data API (PostgREST) roles ``anon`` / ``authenticated`` therefore get
  nothing, which is the intended boundary for this deployment.
- The application connects as the table owner (``postgres`` role via the
  session pooler); owners bypass RLS without FORCE, so the backend, the
  arq worker and this migration itself are unaffected. ``FORCE ROW LEVEL
  SECURITY`` is deliberately NOT set (it would break the owner-role app).
- Out-of-band table creation is the drift class this sweep exists for:
  any future table that escapes Alembic is caught by the next sweep.
  The durable fix for the salary tables is to give them a creating
  revision; this sweep closes the security gap now.

Downgrade disables RLS on every public table, which re-exposes them to
the Data API roles. Only run it during a deliberate rollback with that
exposure in mind (same warning as 0046).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0049_dental_specialty_canonical.
revision = "0050_enable_rls_sweep"
down_revision = "0049_dental_specialty_canonical"
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
