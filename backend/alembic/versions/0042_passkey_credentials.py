"""M4-P1-4: Create passkey_credentials table for WebAuthn.

Revision ID: 0042_passkey_credentials
Revises: 0041_patient_relationships
Create Date: 2026-07-15

Epic M4 — Backend Security & Compliance:
WebAuthn/Passkey support for alternative patient authentication.
Phishing-resistant by design. Patients can register passkeys
(TouchID, FaceID, YubiKey) as an alternative to Telegram Mini App.
"""
from alembic import op
import sqlalchemy as sa


revision = "0042_passkey_credentials"
down_revision = "0041_patient_relationships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Patient who owns this passkey",
        ),
        sa.Column(
            "credential_id",
            sa.String(length=512),
            nullable=False,
            unique=True,
            index=True,
            comment="WebAuthn credential ID (base64url encoded)",
        ),
        sa.Column(
            "public_key",
            sa.Text(),
            nullable=False,
            comment="COSE-encoded public key (base64url)",
        ),
        sa.Column(
            "sign_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Replay protection counter",
        ),
        sa.Column("transports", sa.String(length=256), nullable=True),
        sa.Column("device_type", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_passkey_credentials_patient_active",
        "passkey_credentials",
        ["patient_id", "active"],
    )


def downgrade() -> None:
    op.drop_index("ix_passkey_credentials_patient_active", table_name="passkey_credentials")
    op.drop_table("passkey_credentials")
