"""PR-2: Add User FCM device metadata columns.

Revision ID: 0038_user_fcm_fields
Revises: 0037_patient_medical_fields
Create Date: 2026-07-10

Adds three new columns to the ``users`` table to back the FCM push
notification endpoints in fcm_notifications.py:

- ``device_type`` (String(20)) — web/android/ios device type
- ``device_info`` (JSON) — arbitrary device metadata dict
- ``push_notifications_enabled`` (Boolean, default False) —
  user-level push opt-in flag

The pre-existing ``device_token`` column already stored the FCM token
itself, but the FCM endpoints also tried to read/write these three
companion fields, causing AttributeError → HTTP 500. This migration
makes the schema match the endpoint contract.
"""
from alembic import op
import sqlalchemy as sa


revision = "0038_user_fcm_fields"
down_revision = "0037_patient_medical_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("device_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("device_info", sa.JSON(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "push_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "push_notifications_enabled")
    op.drop_column("users", "device_info")
    op.drop_column("users", "device_type")
