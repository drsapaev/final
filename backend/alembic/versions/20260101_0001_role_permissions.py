"""Add role permissions tables

Revision ID: 20260101_0001_role_permissions
Revises: 20251228_0001_unique_queue_tag
Create Date: 2026-01-01 08:10:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = '20260101_0001_role_permissions'
down_revision = '20251228_0001_unique_queue_tag'
branch_labels = None
depends_on = None


def table_exists(conn, table_name):
    """Check if table exists in SQLite database."""
    result = conn.execute(sa.text(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
    ))
    return result.fetchone() is not None


def upgrade() -> None:
    """Create role and permissions tables with IF NOT EXISTS logic."""
    
    conn = op.get_bind()
    
    # 1. Create permissions table
    if not table_exists(conn, 'permissions'):
        op.create_table(
            'permissions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
            sa.Column('codename', sa.String(100), unique=True, nullable=False, index=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(50), nullable=True, index=True),
            sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
        )
        print("Created table: permissions")
    else:
        print("Table permissions already exists, skipping")
    
    # 2. Create roles table
    if not table_exists(conn, 'roles'):
        op.create_table(
            'roles',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(50), unique=True, nullable=False, index=True),
            sa.Column('display_name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('parent_role_id', sa.Integer(), sa.ForeignKey('roles.id'), nullable=True),
            sa.Column('level', sa.Integer(), default=0, nullable=False),
            sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
            sa.Column('is_system', sa.Boolean(), default=False, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
        )
        print("Created table: roles")
    else:
        print("Table roles already exists, skipping")
    
    # 3. Create user_roles association table
    if not table_exists(conn, 'user_roles'):
        op.create_table(
            'user_roles',
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('assigned_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )
        print("Created table: user_roles")
    else:
        print("Table user_roles already exists, skipping")
    
    # 4. Create role_permissions association table
    if not table_exists(conn, 'role_permissions'):
        op.create_table(
            'role_permissions',
            sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('permission_id', sa.Integer(), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('granted_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('granted_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        print("Created table: role_permissions")
    else:
        print("Table role_permissions already exists, skipping")
    
    # 5. Create user_groups table
    if not table_exists(conn, 'user_groups'):
        op.create_table(
            'user_groups',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
            sa.Column('display_name', sa.String(150), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('group_type', sa.String(50), default='custom', nullable=False, index=True),
            sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
        )
        print("Created table: user_groups")
    else:
        print("Table user_groups already exists, skipping")
    
    # 6. Create user_groups_members association table  
    if not table_exists(conn, 'user_groups_members'):
        op.create_table(
            'user_groups_members',
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('group_id', sa.Integer(), sa.ForeignKey('user_groups.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('joined_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('added_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        print("Created table: user_groups_members")
    else:
        print("Table user_groups_members already exists, skipping")
    
    # 7. Create group_roles association table
    if not table_exists(conn, 'group_roles'):
        op.create_table(
            'group_roles',
            sa.Column('group_id', sa.Integer(), sa.ForeignKey('user_groups.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('assigned_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )
        print("Created table: group_roles")
    else:
        print("Table group_roles already exists, skipping")
    
    # 8. Create user_permission_overrides table
    if not table_exists(conn, 'user_permission_overrides'):
        op.create_table(
            'user_permission_overrides',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('permission_id', sa.Integer(), sa.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('override_type', sa.String(20), nullable=False),  # grant, deny
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
            sa.Column('granted_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
        )
        print("Created table: user_permission_overrides")
    else:
        print("Table user_permission_overrides already exists, skipping")
    
    # 9. Create role_hierarchy table
    if not table_exists(conn, 'role_hierarchy'):
        op.create_table(
            'role_hierarchy',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('parent_role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('child_role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        print("Created table: role_hierarchy")
    else:
        print("Table role_hierarchy already exists, skipping")
    
    # 10. Create permission_audit_log table
    if not table_exists(conn, 'permission_audit_log'):
        op.create_table(
            'permission_audit_log',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('action', sa.String(50), nullable=False, index=True),  # grant, revoke, override
            sa.Column('target_type', sa.String(20), nullable=False),  # user, role, group
            sa.Column('target_id', sa.Integer(), nullable=False),
            sa.Column('permission_id', sa.Integer(), sa.ForeignKey('permissions.id'), nullable=True),
            sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id'), nullable=True),
            sa.Column('old_value', sa.Text(), nullable=True),
            sa.Column('new_value', sa.Text(), nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
        )
        print("Created table: permission_audit_log")
    else:
        print("Table permission_audit_log already exists, skipping")
    
    # 11. Seed default roles (only if roles table was just created or is empty)
    result = conn.execute(sa.text("SELECT COUNT(*) FROM roles"))
    if result.fetchone()[0] == 0:
        conn.execute(sa.text("""
            INSERT INTO roles (name, display_name, description, level, is_active, is_system) VALUES
            ('Admin', 'Администратор', 'Полный доступ к системе', 100, 1, 1),
            ('Doctor', 'Врач', 'Медицинский персонал - врачи', 80, 1, 1),
            ('Nurse', 'Медсестра', 'Медицинский персонал - медсестры', 70, 1, 1),
            ('Receptionist', 'Регистратор', 'Регистрация пациентов и управление очередями', 60, 1, 1),
            ('Cashier', 'Кассир', 'Управление платежами', 50, 1, 1),
            ('Lab', 'Лаборант', 'Лабораторный персонал', 40, 1, 1),
            ('Patient', 'Пациент', 'Пациент клиники', 10, 1, 1)
        """))
        print("Seeded default roles")
    else:
        print("Roles table already has data, skipping seed")


def downgrade() -> None:
    """Drop role and permissions tables."""
    op.drop_table('permission_audit_log')
    op.drop_table('role_hierarchy')
    op.drop_table('user_permission_overrides')
    op.drop_table('group_roles')
    op.drop_table('user_groups_members')
    op.drop_table('user_groups')
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    op.drop_table('roles')
    op.drop_table('permissions')
