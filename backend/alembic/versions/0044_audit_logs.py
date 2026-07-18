"""M5.1 + M5.5: Extend audit_logs table + add immutability trigger.

Revision ID: 0044_audit_logs
Revises: 0043_emergency_tokens
Create Date: 2026-07-15

Extends existing audit_logs table (from models/audit.py) with new columns
for unified audit (M5.1) and adds immutability trigger (M5.5).
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_audit_logs"
down_revision = "0043_emergency_tokens"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # M5.1: Add new columns to existing audit_logs table
    op.add_column("audit_logs", sa.Column("event_type", sa.String(80), nullable=True, index=True))
    op.add_column("audit_logs", sa.Column("actor_patient_id", sa.Integer(), nullable=True, index=True))
    op.add_column("audit_logs", sa.Column("actor_role", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_type", sa.String(20), nullable=False, server_default="staff"))
    op.add_column("audit_logs", sa.Column("subject_patient_id", sa.Integer(), nullable=True, index=True))
    op.add_column("audit_logs", sa.Column("resource_type", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_id", sa.String(100), nullable=True))
    op.add_column("audit_logs", sa.Column("outcome", sa.String(20), nullable=False, server_default="success"))
    op.add_column("audit_logs", sa.Column("reason_code", sa.JSON(), nullable=True))
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(512), nullable=True))
    op.add_column("audit_logs", sa.Column("session_id", sa.String(128), nullable=True))

    # M5.1: Add composite indexes for common audit queries
    op.create_index("ix_audit_event_created", "audit_logs", ["event_type", "created_at"])
    op.create_index("ix_audit_actor_created", "audit_logs", ["actor_user_id", "created_at"])
    op.create_index("ix_audit_subject_created", "audit_logs", ["subject_patient_id", "created_at"])
    op.create_index("ix_audit_outcome_created", "audit_logs", ["outcome", "created_at"])

    # M5.5: Immutability trigger — prevent UPDATE and DELETE
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is immutable: UPDATE and DELETE are not allowed';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();

        CREATE TRIGGER audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
    """)

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification()")
    op.drop_index("ix_audit_outcome_created", table_name="audit_logs")
    op.drop_index("ix_audit_subject_created", table_name="audit_logs")
    op.drop_index("ix_audit_actor_created", table_name="audit_logs")
    op.drop_index("ix_audit_event_created", table_name="audit_logs")
    op.drop_column("audit_logs", "session_id")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip_address")
    op.drop_column("audit_logs", "reason_code")
    op.drop_column("audit_logs", "outcome")
    op.drop_column("audit_logs", "resource_id")
    op.drop_column("audit_logs", "resource_type")
    op.drop_column("audit_logs", "subject_patient_id")
    op.drop_column("audit_logs", "actor_type")
    op.drop_column("audit_logs", "actor_role")
    op.drop_column("audit_logs", "actor_patient_id")
    op.drop_column("audit_logs", "event_type")
