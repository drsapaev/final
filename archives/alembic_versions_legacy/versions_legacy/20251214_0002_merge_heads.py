"""Merge heads for refund_deposits

Revision ID: 20251214_0002_merge_heads
Revises: 20251214_0001_refund_deposits, p2p4_tables_001
Create Date: 2025-12-14 11:39:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251214_0002_merge_heads'
down_revision: Union[str, Sequence[str]] = ('20251214_0001_refund_deposits', 'p2p4_tables_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
