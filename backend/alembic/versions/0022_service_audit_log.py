"""Add service audit log table

Revision ID: 0022_service_audit_log
Revises: 0021_printing_tables
Create Date: 2026-04-13 18:27:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0022_service_audit_log'
down_revision = '0021_printing_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create service_audit_logs table for tracking service changes."""
    op.create_table(
        'service_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('changes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('old_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )

    # Create indexes for better query performance
    op.create_index(
        'ix_service_audit_logs_service_id',
        'service_audit_logs',
        ['service_id']
    )
    op.create_index(
        'ix_service_audit_logs_user_id',
        'service_audit_logs',
        ['user_id']
    )
    op.create_index(
        'ix_service_audit_logs_action',
        'service_audit_logs',
        ['action']
    )
    op.create_index(
        'ix_service_audit_logs_created_at',
        'service_audit_logs',
        ['created_at']
    )


def downgrade():
    """Drop service_audit_logs table."""
    op.drop_index('ix_service_audit_logs_created_at', table_name='service_audit_logs')
    op.drop_index('ix_service_audit_logs_action', table_name='service_audit_logs')
    op.drop_index('ix_service_audit_logs_user_id', table_name='service_audit_logs')
    op.drop_index('ix_service_audit_logs_service_id', table_name='service_audit_logs')
    op.drop_table('service_audit_logs')
