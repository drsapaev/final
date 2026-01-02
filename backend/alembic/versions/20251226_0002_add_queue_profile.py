"""Add QueueProfile for dynamic queue tabs

Revision ID: 20251226_0002
Revises: 20251226_0001_add_session_id
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '20251226_0002_add_queue_profile'
down_revision = '20251226_0001_add_session_id'
branch_labels = None
depends_on = None


# Initial profiles for seeding
INITIAL_QUEUE_PROFILES = [
    {
        "key": "cardiology",
        "title": "Cardiology",
        "title_ru": "Кардиология",
        "queue_tags": '["cardio", "cardiology", "cardiology_common"]',
        "department_key": "cardiology",
        "order": 1,
        "icon": "Heart",
        "color": "#E53E3E",
    },
    {
        "key": "ecg",
        "title": "ECG",
        "title_ru": "ЭКГ",
        "queue_tags": '["ecg", "echokg"]',
        "department_key": None,
        "order": 2,
        "icon": "Activity",
        "color": "#3182CE",
    },
    {
        "key": "dermatology",
        "title": "Dermatology",
        "title_ru": "Дерматология",
        "queue_tags": '["derma", "dermatology"]',
        "department_key": "dermatology",
        "order": 3,
        "icon": "Sparkles",
        "color": "#9F7AEA",
    },
    {
        "key": "stomatology",
        "title": "Dental",
        "title_ru": "Стоматология",
        "queue_tags": '["dental", "stomatology", "dentist"]',
        "department_key": "stomatology",
        "order": 4,
        "icon": "Smile",
        "color": "#38A169",
    },
    {
        "key": "lab",
        "title": "Laboratory",
        "title_ru": "Лаборатория",
        "queue_tags": '["lab", "laboratory"]',
        "department_key": "laboratory",
        "order": 5,
        "icon": "TestTube",
        "color": "#DD6B20",
    },
    {
        "key": "procedures",
        "title": "Procedures",
        "title_ru": "Процедуры",
        "queue_tags": '["procedures", "physio", "therapy"]',
        "department_key": None,
        "order": 6,
        "icon": "Stethoscope",
        "color": "#718096",
    },
    {
        "key": "cosmetology",
        "title": "Cosmetology",
        "title_ru": "Косметология",
        "queue_tags": '["cosmetology"]',
        "department_key": "cosmetology",
        "order": 7,
        "icon": "Sparkle",
        "color": "#D53F8C",
    },
    {
        "key": "general",
        "title": "General",
        "title_ru": "Общая очередь",
        "queue_tags": '["general"]',
        "department_key": None,
        "order": 99,
        "icon": "Users",
        "color": "#4A5568",
    },
]


def upgrade():
    # Check if table already exists
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    if 'queue_profiles' in inspector.get_table_names():
        print("Table queue_profiles already exists, skipping creation")
        return
    
    # 1. Create queue_profiles table (SQLite compatible)
    op.create_table(
        'queue_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(50), unique=True, nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('title_ru', sa.String(100), nullable=True),
        sa.Column('queue_tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('department_key', sa.String(50), nullable=True, index=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),  # SQLite: avoid 'order' keyword
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),  # SQLite: use 1 instead of true
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    
    # 2. Create index on key
    op.create_index('ix_queue_profiles_key', 'queue_profiles', ['key'], unique=True)
    
    # 3. Seed initial profiles (SQLite compatible)
    for profile in INITIAL_QUEUE_PROFILES:
        dept_key = f"'{profile['department_key']}'" if profile['department_key'] else "NULL"
        op.execute(f"""
            INSERT INTO queue_profiles (key, title, title_ru, queue_tags, department_key, display_order, is_active, icon, color)
            VALUES (
                '{profile['key']}',
                '{profile['title']}',
                '{profile['title_ru']}',
                '{profile['queue_tags']}',
                {dept_key},
                {profile['order']},
                1,
                '{profile['icon']}',
                '{profile['color']}'
            )
        """)


def downgrade():
    op.drop_index('ix_queue_profiles_key', table_name='queue_profiles')
    op.drop_table('queue_profiles')
