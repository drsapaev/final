"""Add unpublished public content fields to services and doctors.

Existing catalog rows remain unpublished. Public copy and slugs are left
empty until clinic staff prepare and explicitly publish each profile.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0079_kosmed_website_content"
down_revision = "0078_clinic_settings_keys"
branch_labels = None
depends_on = None

_WEBSITE_SLUG_FORMAT_CHECK = "slug IS NULL OR slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'"


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column(
            "show_on_website",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("services", sa.Column("name_uz", sa.String(256), nullable=True))
    op.add_column("services", sa.Column("description_ru", sa.Text(), nullable=True))
    op.add_column("services", sa.Column("description_uz", sa.Text(), nullable=True))
    op.add_column("services", sa.Column("slug", sa.String(160), nullable=True))
    op.create_check_constraint(
        "ck_services_website_slug_format",
        "services",
        sa.text(_WEBSITE_SLUG_FORMAT_CHECK),
    )
    op.add_column(
        "services",
        sa.Column("website_first_published_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_services_website_slug",
        "services",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )

    op.add_column(
        "doctors",
        sa.Column(
            "show_on_website",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("doctors", sa.Column("bio_ru", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("bio_uz", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("slug", sa.String(160), nullable=True))
    op.create_check_constraint(
        "ck_doctors_website_slug_format",
        "doctors",
        sa.text(_WEBSITE_SLUG_FORMAT_CHECK),
    )
    op.add_column(
        "doctors",
        sa.Column("website_first_published_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_doctors_website_slug",
        "doctors",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_doctors_website_slug", table_name="doctors")
    op.drop_constraint("ck_doctors_website_slug_format", "doctors", type_="check")
    op.drop_column("doctors", "website_first_published_at")
    op.drop_column("doctors", "slug")
    op.drop_column("doctors", "bio_uz")
    op.drop_column("doctors", "bio_ru")
    op.drop_column("doctors", "show_on_website")

    op.drop_index("uq_services_website_slug", table_name="services")
    op.drop_constraint("ck_services_website_slug_format", "services", type_="check")
    op.drop_column("services", "website_first_published_at")
    op.drop_column("services", "slug")
    op.drop_column("services", "description_uz")
    op.drop_column("services", "description_ru")
    op.drop_column("services", "name_uz")
    op.drop_column("services", "show_on_website")
