"""Add refund requests and patient deposits tables

Revision ID: 20251214_0001
Revises: 
Create Date: 2025-12-14 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251214_0001_refund_deposits'
down_revision: Union[str, None] = '20251211_0001'  # Last migration in chain
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Refund Requests table
    op.create_table(
        'refund_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=True),
        sa.Column('original_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('refund_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('commission_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('refund_type', sa.String(length=20), nullable=False, server_default='deposit'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_automatic', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('bank_card_number', sa.String(length=20), nullable=True),
        sa.Column('bank_name', sa.String(length=100), nullable=True),
        sa.Column('card_holder_name', sa.String(length=200), nullable=True),
        sa.Column('processed_by', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('manager_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['processed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_refund_requests_id', 'refund_requests', ['id'])
    op.create_index('ix_refund_requests_patient_id', 'refund_requests', ['patient_id'])
    op.create_index('ix_refund_requests_payment_id', 'refund_requests', ['payment_id'])
    op.create_index('ix_refund_requests_status', 'refund_requests', ['status'])
    op.create_index('ix_refund_requests_visit_id', 'refund_requests', ['visit_id'])

    # Patient Deposits table
    op.create_table(
        'patient_deposits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('balance', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='UZS'),
        sa.Column('max_balance', sa.Numeric(precision=12, scale=2), nullable=False, server_default='10000000'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('patient_id')
    )
    op.create_index('ix_patient_deposits_id', 'patient_deposits', ['id'])
    op.create_index('ix_patient_deposits_patient_id', 'patient_deposits', ['patient_id'])

    # Deposit Transactions table
    op.create_table(
        'deposit_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deposit_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('refund_request_id', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('visit_id', sa.Integer(), nullable=True),
        sa.Column('performed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['deposit_id'], ['patient_deposits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['refund_request_id'], ['refund_requests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['performed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deposit_transactions_id', 'deposit_transactions', ['id'])
    op.create_index('ix_deposit_transactions_deposit_id', 'deposit_transactions', ['deposit_id'])


def downgrade() -> None:
    op.drop_table('deposit_transactions')
    op.drop_table('patient_deposits')
    op.drop_table('refund_requests')
