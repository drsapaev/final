"""Adopt salary_history / salary_payments into the Alembic chain.

Follow-up to 0050_enable_rls_sweep (Supabase rls_disabled_in_public, P1):
``salary_history`` and ``salary_payments`` exist in production but were
created out-of-band (ad-hoc ``Base.metadata`` DDL run against prod after
the 0046 sweep of 2026-08-18 — relfrozenxid era 1374 vs the Aug-18 cluster
at 1177), so no Alembic revision owns them. 0050 closed the security gap
(RLS); this revision closes the ownership gap so a fresh install produces
the same schema production has.

Adoption pattern (fresh-install safe AND production safe):

- Inspect ``public`` for each table.  When it already exists (current
  production), creation is skipped entirely — no ``CREATE TABLE`` is ever
  issued against a table that already has data.
- When it is missing (fresh install / CI), it is created with DDL that
  mirrors the live production schema 1:1, which itself matches
  ``backend/app/models/salary_history.py`` exactly: column types and
  nullability, FK actions (``user_id`` ON DELETE CASCADE;
  ``changed_by_id`` / ``confirmed_by_id`` ON DELETE SET NULL), constraint
  names, and the redundant ``ix_<table>_id`` indexes that SQLAlchemy
  emits for ``index=True`` primary keys. Verified against production
  information_schema / pg_constraint / pg_indexes on 2026-09-02.
- Finally ``ENABLE ROW LEVEL SECURITY`` for both tables, idempotently —
  on production this is a no-op (0050 already enabled it); on fresh
  installs it guarantees the RLS invariant holds at every chain position
  (0050 sweeps only what exists when it runs, and these tables are
  created here, after it).

Downgrade drops both tables (guarded by existence) — on production this
would destroy salary data; only run with that explicitly in mind.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from sqlalchemy import inspect

# Revision identifiers — chained after 0050_enable_rls_sweep.
revision = "0051_salary_tables_adoption"
down_revision = "0050_enable_rls_sweep"
branch_labels = None
depends_on = None


def _public_tables(bind) -> set[str]:
    return set(inspect(bind).get_table_names(schema="public"))


def _create_salary_history() -> None:
    op.create_table(
        "salary_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("old_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("change_percentage", sa.Numeric(6, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="salary_history_user_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["users.id"], ondelete="SET NULL",
            name="salary_history_changed_by_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_id"], ["users.id"], ondelete="SET NULL",
            name="salary_history_confirmed_by_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="salary_history_pkey"),
    )
    op.create_index(
        "ix_salary_history_id", "salary_history", ["id"], unique=False
    )
    op.create_index(
        "ix_salary_history_user_id", "salary_history", ["user_id"], unique=False
    )


def _create_salary_payments() -> None:
    op.create_table(
        "salary_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("bonuses", sa.Numeric(12, 2), nullable=False),
        sa.Column("deductions", sa.Numeric(12, 2), nullable=False),
        sa.Column("taxes", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="salary_payments_user_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="salary_payments_pkey"),
    )
    op.create_index(
        "ix_salary_payments_id", "salary_payments", ["id"], unique=False
    )
    op.create_index(
        "ix_salary_payments_user_id", "salary_payments", ["user_id"], unique=False
    )


def upgrade() -> None:
    bind = op.get_bind()
    existing = _public_tables(bind)

    if "salary_history" in existing:
        print("0051 adoption: public.salary_history already exists — skipping CREATE")
    else:
        _create_salary_history()

    if "salary_payments" in existing:
        print("0051 adoption: public.salary_payments already exists — skipping CREATE")
    else:
        _create_salary_payments()

    op.execute(
        sa.text("ALTER TABLE public.salary_history ENABLE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text("ALTER TABLE public.salary_payments ENABLE ROW LEVEL SECURITY")
    )


def downgrade() -> None:
    bind = op.get_bind()
    existing = _public_tables(bind)

    # Destroys salary data on databases where the tables hold rows.
    if "salary_history" in existing:
        op.drop_index("ix_salary_history_user_id", table_name="salary_history")
        op.drop_index("ix_salary_history_id", table_name="salary_history")
        op.drop_table("salary_history")
    if "salary_payments" in existing:
        op.drop_index("ix_salary_payments_user_id", table_name="salary_payments")
        op.drop_index("ix_salary_payments_id", table_name="salary_payments")
        op.drop_table("salary_payments")
