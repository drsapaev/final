"""Enable QR codes in ticket print settings by default.

Revision ID: 0023_ticket_print_qr_default
Revises: 0022_service_audit_log
Create Date: 2026-05-15 15:20:00.000000
"""

from alembic import op


revision = "0023_ticket_print_qr_default"
down_revision = "0022_service_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO clinic_settings (key, value, category, description, updated_at, created_at)
        VALUES (
            'ticket_print_show_qr_code',
            'true'::json,
            'print',
            'Show QR code on queue tickets by default',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (key) DO UPDATE
        SET value = 'true'::json,
            category = 'print',
            updated_at = CURRENT_TIMESTAMP
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE clinic_settings
        SET value = 'false'::json,
            updated_at = CURRENT_TIMESTAMP
        WHERE key = 'ticket_print_show_qr_code'
        """
    )
