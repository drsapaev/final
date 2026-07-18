"""PR-1: Add Patient medical-domain fields.

Revision ID: 0037_patient_medical_fields
Revises: 0036_chat_encryption
Create Date: 2026-07-10

Adds three new columns to the ``patients`` table to back the
mobile_api_extended.py profile endpoints:

- ``emergency_contact`` (String(64)) — phone number for the patient's
  emergency contact (medical domain).
- ``allergies`` (Text) — free-form list of patient allergies.
- ``chronic_conditions`` (Text) — free-form list of chronic conditions.

These columns were identified as missing in the PR-1 audit
(AUDIT_PR1_MOBILE_EXTENDED.md, endpoint E11 update_profile).
"""
from alembic import op
import sqlalchemy as sa


revision = "0037_patient_medical_fields"
down_revision = "0036_chat_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("emergency_contact", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "patients",
        sa.Column("allergies", sa.Text(), nullable=True),
    )
    op.add_column(
        "patients",
        sa.Column("chronic_conditions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patients", "chronic_conditions")
    op.drop_column("patients", "allergies")
    op.drop_column("patients", "emergency_contact")
