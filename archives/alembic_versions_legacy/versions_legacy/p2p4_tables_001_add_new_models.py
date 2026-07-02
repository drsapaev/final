"""Add P2-P4 tables: ecg_data, odontogram, salary_history

Revision ID: p2p4_tables_001
Revises: 
Create Date: 2024-12-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'p2p4_tables_001'
down_revision = 'voice_messages_002'  # Depends on voice_messages migration
branch_labels = None
depends_on = None


def upgrade():
    # ECG Data table
    op.create_table(
        'ecg_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_name', sa.String(255), nullable=True),
        sa.Column('file_type', sa.String(50), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        # DICOM metadata
        sa.Column('study_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('study_time', sa.String(20), nullable=True),
        sa.Column('modality', sa.String(20), nullable=True),
        sa.Column('manufacturer', sa.String(100), nullable=True),
        sa.Column('device_model', sa.String(100), nullable=True),
        sa.Column('institution_name', sa.String(200), nullable=True),
        # ECG parameters
        sa.Column('heart_rate', sa.Integer(), nullable=True),
        sa.Column('rr_interval', sa.Numeric(8, 2), nullable=True),
        sa.Column('pr_interval', sa.Numeric(8, 2), nullable=True),
        sa.Column('qrs_duration', sa.Numeric(8, 2), nullable=True),
        sa.Column('qt_interval', sa.Numeric(8, 2), nullable=True),
        sa.Column('qtc_interval', sa.Numeric(8, 2), nullable=True),
        sa.Column('p_axis', sa.Integer(), nullable=True),
        sa.Column('qrs_axis', sa.Integer(), nullable=True),
        sa.Column('t_axis', sa.Integer(), nullable=True),
        # Waveform data
        sa.Column('waveform_data', sa.JSON(), nullable=True),
        sa.Column('leads_count', sa.Integer(), nullable=True),
        sa.Column('sampling_frequency', sa.Integer(), nullable=True),
        # Interpretation
        sa.Column('auto_interpretation', sa.Text(), nullable=True),
        sa.Column('ai_interpretation', sa.JSON(), nullable=True),
        sa.Column('doctor_conclusion', sa.Text(), nullable=True),
        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('is_reviewed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ecg_data_patient_id', 'ecg_data', ['patient_id'])
    op.create_index('ix_ecg_data_study_date', 'ecg_data', ['study_date'])
    op.create_index('ix_ecg_data_status', 'ecg_data', ['status'])
    
    # Odontogram table
    op.create_table(
        'odontograms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=True),
        sa.Column('teeth_data', sa.JSON(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_odontograms_patient_id', 'odontograms', ['patient_id'])
    
    # Tooth History table
    op.create_table(
        'tooth_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('odontogram_id', sa.Integer(), nullable=False),
        sa.Column('tooth_number', sa.Integer(), nullable=False),
        sa.Column('old_status', sa.JSON(), nullable=True),
        sa.Column('new_status', sa.JSON(), nullable=False),
        sa.Column('change_reason', sa.String(200), nullable=True),
        sa.Column('doctor_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['odontogram_id'], ['odontograms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tooth_history_odontogram_id', 'tooth_history', ['odontogram_id'])
    
    # Salary History table
    op.create_table(
        'salary_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('old_salary', sa.Numeric(12, 2), nullable=True),
        sa.Column('new_salary', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='UZS'),
        sa.Column('change_type', sa.String(50), nullable=False, server_default='adjustment'),
        sa.Column('change_percentage', sa.Numeric(6, 2), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('changed_by_id', sa.Integer(), nullable=True),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['confirmed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_salary_history_user_id', 'salary_history', ['user_id'])
    op.create_index('ix_salary_history_effective_date', 'salary_history', ['effective_date'])
    
    # Salary Payments table
    op.create_table(
        'salary_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('base_salary', sa.Numeric(12, 2), nullable=False),
        sa.Column('bonuses', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('deductions', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('taxes', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('net_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='UZS'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_salary_payments_user_id', 'salary_payments', ['user_id'])
    op.create_index('ix_salary_payments_period', 'salary_payments', ['period_start', 'period_end'])


def downgrade():
    op.drop_table('salary_payments')
    op.drop_table('salary_history')
    op.drop_table('tooth_history')
    op.drop_table('odontograms')
    op.drop_table('ecg_data')
