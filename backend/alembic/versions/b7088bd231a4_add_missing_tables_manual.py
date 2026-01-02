"""Add missing tables manual

Revision ID: b7088bd231a4
Revises: 20260101_0001_role_permissions
Create Date: 2026-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from app.db.base import Base

# revision identifiers, used by Alembic.
revision = 'b7088bd231a4'
down_revision = '20260101_0001_role_permissions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safely create all tables that do not exist
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    # Downgrade logic is skipped for now as we used create_all
    pass
