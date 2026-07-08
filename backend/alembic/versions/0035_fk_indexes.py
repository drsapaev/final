"""add indexes on foreign key columns (DB-AUDIT)

Revision ID: 0035_fk_indexes
Revises: 0034_bot_token_encrypted
Create Date: 2026-07-07

PostgreSQL does not auto-create indexes on foreign key columns.
Missing indexes cause slow JOINs and DELETE CASCADE operations.
This migration adds indexes on FK columns that are missing them.
"""
from alembic import op

revision = "0035_fk_indexes"
down_revision = "0034_bot_token_encrypted"
branch_labels = None
depends_on = None


# FK columns that need indexes (table, column)
INDEXES = [
    # appointment
    ("appointments", "patient_id"),
    ("appointments", "doctor_id"),
    ("appointments", "department_id"),
    # family_relation
    ("family_relations", "patient_id"),
    ("family_relations", "related_patient_id"),
    ("family_relations", "created_by"),
    # notification_delivery
    ("notification_deliveries", "event_id"),
    # refund_deposit
    ("refund_requests", "patient_id"),
    ("refund_requests", "payment_id"),
    ("refund_requests", "visit_id"),
    ("refund_requests", "processed_by"),
    ("patient_deposits", "patient_id"),
    ("deposit_transactions", "deposit_id"),
    ("deposit_transactions", "created_by"),
    # telegram
    ("telegram_users", "patient_id"),
    ("telegram_users", "user_id"),
    ("telegram_messages", "telegram_user_id"),
    ("telegram_messages", "patient_id"),
    ("telegram_staff_confirmation_tokens", "staff_user_id"),
    ("telegram_staff_link_tokens", "user_id"),
    # doctor_phrase_history
    ("doctor_phrase_history", "user_id"),
    # global_search_audit
    ("global_search_audit", "user_id"),
]


def upgrade():
    for table, column in INDEXES:
        index_name = f"ix_{table}_{column}"
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"
        )


def downgrade():
    for table, column in INDEXES:
        index_name = f"ix_{table}_{column}"
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
