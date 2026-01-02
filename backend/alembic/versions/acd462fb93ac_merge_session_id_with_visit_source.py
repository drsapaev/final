"""merge_session_id_with_visit_source

Revision ID: acd462fb93ac
Revises: 20251220_0001_visit_source_ssot, 20251226_0002_add_queue_profile
Create Date: 2025-12-26 00:18:17.766003

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'acd462fb93ac'
down_revision = ('20251220_0001_visit_source_ssot', '20251226_0002_add_queue_profile')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

