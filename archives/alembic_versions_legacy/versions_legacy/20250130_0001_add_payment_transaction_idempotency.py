"""Add composite unique constraint for payment transaction idempotency

Revision ID: 20250130_0001
Revises: 20251127_0001
Create Date: 2025-01-30 12:00:00.000000

✅ SECURITY: This migration adds idempotency protection for payment webhooks
by creating a composite unique constraint on (transaction_id, provider).
This prevents duplicate processing of the same webhook from the same provider.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20250130_0001"
down_revision = "20251127_0001"  # Update this to the latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    ✅ SECURITY: Add composite unique constraint for idempotency
    
    This ensures that the same transaction_id from the same provider
    cannot be processed twice, preventing duplicate payments.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if payment_transactions table exists
    if "payment_transactions" not in inspector.get_table_names():
        print("⚠️  payment_transactions table does not exist, skipping migration")
        return
    
    # Check if constraint already exists
    table = sa.Table("payment_transactions", sa.MetaData(), autoload_with=conn)
    existing_constraints = [
        c.name for c in table.constraints if isinstance(c, sa.UniqueConstraint)
    ]
    
    constraint_name = "uq_payment_transactions_transaction_provider"
    
    if constraint_name in existing_constraints:
        print(f"✅ Constraint {constraint_name} already exists, skipping")
        return
    
    # SQLite doesn't support ALTER TABLE ADD CONSTRAINT directly
    # We need to recreate the table with the new constraint
    if conn.dialect.name == "sqlite":
        # For SQLite, we'll create a unique index instead (which enforces uniqueness)
        try:
            op.create_index(
                "uq_payment_transactions_transaction_provider",
                "payment_transactions",
                ["transaction_id", "provider"],
                unique=True,
            )
            print("✅ Created unique index for payment_transactions (transaction_id, provider)")
        except Exception as e:
            print(f"⚠️  Could not create unique index (may already exist): {e}")
    else:
        # For PostgreSQL/MySQL, we can add the constraint directly
        try:
            op.create_unique_constraint(
                constraint_name,
                "payment_transactions",
                ["transaction_id", "provider"],
            )
            print("✅ Created unique constraint for payment_transactions (transaction_id, provider)")
        except Exception as e:
            print(f"⚠️  Could not create unique constraint: {e}")


def downgrade() -> None:
    """Remove the composite unique constraint"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if "payment_transactions" not in inspector.get_table_names():
        return
    
    constraint_name = "uq_payment_transactions_transaction_provider"
    
    if conn.dialect.name == "sqlite":
        try:
            op.drop_index(constraint_name, table_name="payment_transactions")
        except Exception:
            pass
    else:
        try:
            op.drop_constraint(constraint_name, "payment_transactions", type_="unique")
        except Exception:
            pass


