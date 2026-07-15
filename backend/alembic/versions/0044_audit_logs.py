"""M5.1 + M5.5: Create unified audit_logs table + immutability trigger."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "0044_audit_logs"
down_revision = "0043_emergency_tokens"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(80), nullable=False, index=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("actor_patient_id", sa.Integer(), nullable=True, index=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="staff"),
        sa.Column("subject_patient_id", sa.Integer(), nullable=True, index=True),
        sa.Column("resource_type", sa.String(50), nullable=True, index=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="success"),
        sa.Column("reason_code", JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True, index=True),
        sa.Column("extra_data", JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_event_timestamp", "audit_logs", ["event_type", "timestamp"])
    op.create_index("ix_audit_actor_timestamp", "audit_logs", ["actor_user_id", "timestamp"])
    op.create_index("ix_audit_subject_timestamp", "audit_logs", ["subject_patient_id", "timestamp"])
    op.create_index("ix_audit_resource_action", "audit_logs", ["resource_type", "action"])
    op.create_index("ix_audit_outcome_timestamp", "audit_logs", ["outcome", "timestamp"])

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
    op.drop_index("ix_audit_outcome_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_resource_action", table_name="audit_logs")
    op.drop_index("ix_audit_subject_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_actor_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_event_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")
