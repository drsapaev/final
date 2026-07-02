"""Create Telegram Mini App patient form submission storage.

Revision ID: 0028_tg_patient_form_submissions
Revises: 0027_repair_tg_user_lang_len
Create Date: 2026-05-19 21:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0028_tg_patient_form_submissions"
down_revision = "0027_repair_tg_user_lang_len"
branch_labels = None
depends_on = None


json_payload_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "telegram_patient_form_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.Integer(), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("form_id", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("answers", json_payload_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'telegram_mini_app'")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "form_id <> ''",
            name="ck_telegram_patient_form_submissions_form_id_not_empty",
        ),
        sa.CheckConstraint(
            "schema_version > 0",
            name="ck_telegram_patient_form_submissions_schema_version_positive",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted')",
            name="ck_telegram_patient_form_submissions_status_allowed",
        ),
        sa.CheckConstraint(
            "source <> ''",
            name="ck_telegram_patient_form_submissions_source_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"],
            ["telegram_users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "patient_id",
            "form_id",
            name="uq_telegram_patient_form_submissions_patient_form",
        ),
    )
    op.create_index(
        op.f("ix_telegram_patient_form_submissions_id"),
        "telegram_patient_form_submissions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_patient_form_submissions_patient_id",
        "telegram_patient_form_submissions",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_patient_form_submissions_telegram_user_id",
        "telegram_patient_form_submissions",
        ["telegram_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_patient_form_submissions_chat_id",
        "telegram_patient_form_submissions",
        ["telegram_chat_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_patient_form_submissions_patient_status",
        "telegram_patient_form_submissions",
        ["patient_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_patient_form_submissions_updated_at",
        "telegram_patient_form_submissions",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_patient_form_submissions_updated_at",
        table_name="telegram_patient_form_submissions",
    )
    op.drop_index(
        "ix_telegram_patient_form_submissions_patient_status",
        table_name="telegram_patient_form_submissions",
    )
    op.drop_index(
        "ix_telegram_patient_form_submissions_chat_id",
        table_name="telegram_patient_form_submissions",
    )
    op.drop_index(
        "ix_telegram_patient_form_submissions_telegram_user_id",
        table_name="telegram_patient_form_submissions",
    )
    op.drop_index(
        "ix_telegram_patient_form_submissions_patient_id",
        table_name="telegram_patient_form_submissions",
    )
    op.drop_index(
        op.f("ix_telegram_patient_form_submissions_id"),
        table_name="telegram_patient_form_submissions",
    )
    op.drop_table("telegram_patient_form_submissions")
