"""Create Telegram patient onboarding request storage.

Revision ID: 0029_tg_patient_onboarding
Revises: 0028_tg_patient_form_submissions
Create Date: 2026-05-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0029_tg_patient_onboarding"
down_revision = "0028_tg_patient_form_submissions"
branch_labels = None
depends_on = None


ONBOARDING_STATUSES = (
    "pending_review",
    "linked_existing",
    "created_patient",
    "needs_more_info",
    "rejected",
    "cancelled",
    "expired",
)


def upgrade() -> None:
    op.create_table(
        "patient_onboarding_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.Integer(), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending_review'"),
        ),
        sa.Column(
            "language_code",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'ru'"),
        ),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("contact_name", sa.String(length=256), nullable=True),
        sa.Column("desired_service", sa.String(length=128), nullable=True),
        sa.Column("desired_branch", sa.String(length=128), nullable=True),
        sa.Column("desired_doctor_id", sa.Integer(), nullable=True),
        sa.Column("desired_date", sa.Date(), nullable=True),
        sa.Column("desired_time", sa.String(length=8), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("review_message", sa.String(length=512), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_patient_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ({})".format(
                ", ".join(f"'{status}'" for status in ONBOARDING_STATUSES)
            ),
            name="ck_patient_onboarding_requests_status_allowed",
        ),
        sa.CheckConstraint(
            "desired_time IS NULL OR desired_time <> ''",
            name="ck_patient_onboarding_requests_desired_time_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["desired_doctor_id"],
            ["doctors.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_patient_id"],
            ["patients.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"],
            ["telegram_users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_patient_onboarding_requests_id"),
        "patient_onboarding_requests",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_onboarding_requests_status_created_at",
        "patient_onboarding_requests",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_patient_onboarding_requests_telegram_user_status",
        "patient_onboarding_requests",
        ["telegram_user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_patient_onboarding_requests_telegram_chat_id",
        "patient_onboarding_requests",
        ["telegram_chat_id"],
        unique=False,
    )
    op.create_index(
        "ix_patient_onboarding_requests_expires_at",
        "patient_onboarding_requests",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patient_onboarding_requests_expires_at",
        table_name="patient_onboarding_requests",
    )
    op.drop_index(
        "ix_patient_onboarding_requests_telegram_chat_id",
        table_name="patient_onboarding_requests",
    )
    op.drop_index(
        "ix_patient_onboarding_requests_telegram_user_status",
        table_name="patient_onboarding_requests",
    )
    op.drop_index(
        "ix_patient_onboarding_requests_status_created_at",
        table_name="patient_onboarding_requests",
    )
    op.drop_index(
        op.f("ix_patient_onboarding_requests_id"),
        table_name="patient_onboarding_requests",
    )
    op.drop_table("patient_onboarding_requests")
