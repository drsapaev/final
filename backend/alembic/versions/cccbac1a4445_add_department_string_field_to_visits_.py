"""Add department string field to visits table

Revision ID: cccbac1a4445
Revises: a47243be82f0
Create Date: 2025-11-27 22:30:49.949819

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cccbac1a4445'
down_revision = 'a47243be82f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add department string field to visits table
    op.add_column('visits', sa.Column('department', sa.String(64), nullable=True))


def downgrade() -> None:
    # Remove department string field from visits table
    op.drop_column('visits', 'department')

