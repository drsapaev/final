"""create display config tables

Revision ID: 0018_display_config_tables
Revises: 0017_finance_transactions
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_display_config_tables"
down_revision = "0017_finance_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "display_boards",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("theme", sa.String(length=50), nullable=False, server_default=sa.text("'light'")),
        sa.Column("show_patient_names", sa.String(length=20), nullable=False, server_default=sa.text("'initials'")),
        sa.Column("show_doctor_photos", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("queue_display_count", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("show_announcements", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("show_banners", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("show_videos", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("call_display_duration", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("sound_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("voice_announcements", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("voice_language", sa.String(length=5), nullable=False, server_default=sa.text("'ru'")),
        sa.Column("volume_level", sa.Integer(), nullable=False, server_default=sa.text("70")),
        sa.Column("colors", sa.JSON(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_display_boards_id"), "display_boards", ["id"], unique=False)

    op.create_table(
        "display_themes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("css_variables", sa.JSON(), nullable=False),
        sa.Column("font_family", sa.String(length=100), nullable=False, server_default=sa.text("'system-ui'")),
        sa.Column("font_sizes", sa.JSON(), nullable=True),
        sa.Column("background_config", sa.JSON(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_display_themes_id"), "display_themes", ["id"], unique=False)

    op.create_table(
        "display_announcements",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("announcement_type", sa.String(length=50), nullable=False, server_default=sa.text("'info'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("scroll_speed", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False, server_default=sa.text("'ru'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_display_announcements_id"), "display_announcements", ["id"], unique=False)

    op.create_table(
        "display_banners",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("display_duration", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False, server_default=sa.text("'ru'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_display_banners_id"), "display_banners", ["id"], unique=False)

    op.create_table(
        "display_videos",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("display_boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("video_url", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("file_size_mb", sa.Float(), nullable=True),
        sa.Column("video_format", sa.String(length=20), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("loop_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_display_videos_id"), "display_videos", ["id"], unique=False)

    op.bulk_insert(
        sa.table(
            "display_boards",
            sa.column("name", sa.String),
            sa.column("display_name", sa.String),
            sa.column("location", sa.String),
            sa.column("theme", sa.String),
            sa.column("show_patient_names", sa.String),
            sa.column("show_doctor_photos", sa.Boolean),
            sa.column("queue_display_count", sa.Integer),
            sa.column("show_announcements", sa.Boolean),
            sa.column("show_banners", sa.Boolean),
            sa.column("show_videos", sa.Boolean),
            sa.column("call_display_duration", sa.Integer),
            sa.column("sound_enabled", sa.Boolean),
            sa.column("voice_announcements", sa.Boolean),
            sa.column("voice_language", sa.String),
            sa.column("volume_level", sa.Integer),
            sa.column("colors", sa.JSON),
            sa.column("active", sa.Boolean),
        ),
        [
            {
                "name": "main_board",
                "display_name": "Главное табло",
                "location": "Зона ожидания, 1 этаж",
                "theme": "light",
                "show_patient_names": "initials",
                "show_doctor_photos": True,
                "queue_display_count": 5,
                "show_announcements": True,
                "show_banners": True,
                "show_videos": False,
                "call_display_duration": 30,
                "sound_enabled": True,
                "voice_announcements": False,
                "voice_language": "ru",
                "volume_level": 70,
                "colors": {
                    "primary": "#0066cc",
                    "secondary": "#f8f9fa",
                    "text": "#333333",
                    "background": "#ffffff",
                },
                "active": True,
            }
        ],
    )

    op.bulk_insert(
        sa.table(
            "display_themes",
            sa.column("name", sa.String),
            sa.column("display_name", sa.String),
            sa.column("css_variables", sa.JSON),
            sa.column("font_family", sa.String),
            sa.column("active", sa.Boolean),
            sa.column("is_default", sa.Boolean),
        ),
        [
            {
                "name": "light",
                "display_name": "Светлая тема",
                "css_variables": {
                    "--primary-color": "#0066cc",
                    "--secondary-color": "#f8f9fa",
                    "--text-color": "#333333",
                    "--background-color": "#ffffff",
                    "--border-color": "#dee2e6",
                },
                "font_family": "system-ui, sans-serif",
                "active": True,
                "is_default": True,
            },
            {
                "name": "dark",
                "display_name": "Темная тема",
                "css_variables": {
                    "--primary-color": "#0d6efd",
                    "--secondary-color": "#1a1a1a",
                    "--text-color": "#ffffff",
                    "--background-color": "#000000",
                    "--border-color": "#333333",
                },
                "font_family": "system-ui, sans-serif",
                "active": True,
                "is_default": False,
            },
            {
                "name": "medical",
                "display_name": "Медицинская тема",
                "css_variables": {
                    "--primary-color": "#28a745",
                    "--secondary-color": "#e8f5e8",
                    "--text-color": "#2c3e50",
                    "--background-color": "#f8fff8",
                    "--border-color": "#c3e6cb",
                },
                "font_family": "system-ui, sans-serif",
                "active": True,
                "is_default": False,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_display_videos_id"), table_name="display_videos")
    op.drop_table("display_videos")
    op.drop_index(op.f("ix_display_banners_id"), table_name="display_banners")
    op.drop_table("display_banners")
    op.drop_index(op.f("ix_display_announcements_id"), table_name="display_announcements")
    op.drop_table("display_announcements")
    op.drop_index(op.f("ix_display_themes_id"), table_name="display_themes")
    op.drop_table("display_themes")
    op.drop_index(op.f("ix_display_boards_id"), table_name="display_boards")
    op.drop_table("display_boards")
