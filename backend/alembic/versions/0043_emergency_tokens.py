"""M4-P2-1: Create emergency_access_tokens table."""
from alembic import op
import sqlalchemy as sa

revision = "0043_emergency_tokens"
down_revision = "0042_passkey_credentials"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "emergency_access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False, server_default="all"),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false(), index=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("verification_method", sa.String(50), nullable=False),
        sa.Column("verification_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_emergency_tokens_patient_unused", "emergency_access_tokens", ["patient_id", "used"])

def downgrade() -> None:
    op.drop_index("ix_emergency_tokens_patient_unused", table_name="emergency_access_tokens")
    op.drop_table("emergency_access_tokens")
