"""Store publication metadata for public-site images.

Image bytes are stored outside the application checkout. This table keeps
only an opaque server-generated storage key and metadata; a row is eligible
for public delivery only when explicitly published.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0080_public_site_media"
down_revision = "0079_kosmed_website_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_site_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_kind", sa.String(length=32), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_public_site_media"),
        sa.UniqueConstraint("storage_key", name="uq_public_site_media_storage_key"),
        sa.CheckConstraint(
            "asset_kind IN ('clinic_logo', 'doctor_portrait')",
            name="ck_public_site_media_asset_kind",
        ),
        sa.CheckConstraint(
            "(asset_kind = 'clinic_logo' AND doctor_id IS NULL) OR "
            "(asset_kind = 'doctor_portrait' AND doctor_id IS NOT NULL)",
            name="ck_public_site_media_owner",
        ),
        sa.CheckConstraint(
            "storage_key ~ '^[0-9a-f]{64}$'",
            name="ck_public_site_media_storage_key_format",
        ),
        sa.CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_public_site_media_mime_type",
        ),
        sa.CheckConstraint(
            "byte_size > 0",
            name="ck_public_site_media_byte_size_positive",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_public_site_media_sha256_format",
        ),
        sa.CheckConstraint(
            "(is_published AND published_at IS NOT NULL) OR "
            "(NOT is_published AND published_at IS NULL)",
            name="ck_public_site_media_publication_state",
        ),
    )
    op.create_foreign_key(
        "fk_public_site_media_doctor_id",
        "public_site_media",
        "doctors",
        ["doctor_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_public_site_media_uploaded_by_user_id",
        "public_site_media",
        "users",
        ["uploaded_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_public_site_media_published_clinic_logo",
        "public_site_media",
        ["asset_kind"],
        unique=True,
        postgresql_where=sa.text("asset_kind = 'clinic_logo' AND is_published IS TRUE"),
    )
    op.create_index(
        "uq_public_site_media_published_doctor_portrait",
        "public_site_media",
        ["doctor_id"],
        unique=True,
        postgresql_where=sa.text(
            "asset_kind = 'doctor_portrait' AND is_published IS TRUE"
        ),
    )
    op.create_index(
        "ix_public_site_media_doctor_id",
        "public_site_media",
        ["doctor_id"],
        unique=False,
    )
    op.execute("ALTER TABLE public.public_site_media ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.public_site_media DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_public_site_media_doctor_id",
        table_name="public_site_media",
    )
    op.drop_index(
        "uq_public_site_media_published_doctor_portrait",
        table_name="public_site_media",
    )
    op.drop_index(
        "uq_public_site_media_published_clinic_logo",
        table_name="public_site_media",
    )
    op.drop_constraint(
        "fk_public_site_media_uploaded_by_user_id",
        "public_site_media",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_public_site_media_doctor_id",
        "public_site_media",
        type_="foreignkey",
    )
    op.drop_table("public_site_media")
