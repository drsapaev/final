"""merge multiple heads

Revision ID: 0e315951c2f5
Revises: 20250130_0002, cccbac1a4445
Create Date: 2025-12-02 22:43:50.506918

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e315951c2f5'
down_revision = ('20250130_0002', 'cccbac1a4445')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

