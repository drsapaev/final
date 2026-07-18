"""M4-P0-1: Create patient_access_audit_logs table.

Revision ID: 0040_patient_access_audit
Revises: 0039_feature_flags
Create Date: 2026-07-15

Epic M4 — Backend Security & Compliance:
PHI access audit trail for patient-facing endpoints. Previously,
patient-access endpoints (cabinet summary, forms preview, form
submission, report download, appointment booking) did NOT log
PHI access. EMRAuditLog exists but is doctor/staff-facing only.

This migration creates the patient_access_audit_logs table with:
- subject_patient_id: whose PHI is being accessed
- actor_patient_id / actor_staff_user_id: who is accessing
- actor_type: self | guardian | heir | staff (future-proofing)
- resource_type + resource_id: what is being accessed
- action + outcome: view/download/submit/create + success/denied/error
- ip_address, user_agent, session_id, correlation_id: request metadata
- timestamp: timezone-aware

Immutable: append-only table. No UPDATE/DELETE in application code.
DB-level GRANT restrictions should be added separately by DBA.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "0040_patient_access_audit"
down_revision = "0039_feature_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_access_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # ─── Subject: whose PHI is being accessed ──────────────────────────
        sa.Column(
            "subject_patient_id",
            sa.Integer(),
            nullable=False,
            index=True,
            comment="Patient whose PHI is being accessed",
        ),

        # ─── Actor: who is accessing ────────────────────────────────────────
        sa.Column(
            "actor_patient_id",
            sa.Integer(),
            nullable=True,
            index=True,
            comment="Patient actor (self-access). NULL if actor is staff.",
        ),
        sa.Column(
            "actor_staff_user_id",
            sa.Integer(),
            nullable=True,
            index=True,
            comment="Staff user actor. NULL if actor is patient.",
        ),
        sa.Column(
            "actor_type",
            sa.String(length=20),
            nullable=False,
            comment="self | guardian | heir | staff (future-proofing for M4-P1-3)",
        ),
        sa.Column(
            "actor_telegram_user_id",
            sa.Integer(),
            nullable=True,
            index=True,
            comment="Telegram user ID if access via Mini App",
        ),

        # ─── Resource: what is being accessed ──────────────────────────────
        sa.Column(
            "resource_type",
            sa.String(length=50),
            nullable=False,
            index=True,
            comment="lab_report | cabinet_summary | form_submission | appointment | manifest | forms_preview",
        ),
        sa.Column(
            "resource_id",
            sa.String(length=100),
            nullable=True,
            comment="ID of specific resource (e.g. report_id, form_id, appointment_id)",
        ),

        # ─── Action + outcome ──────────────────────────────────────────────
        sa.Column(
            "action",
            sa.String(length=30),
            nullable=False,
            index=True,
            comment="view | download | submit | create | preview",
        ),
        sa.Column(
            "outcome",
            sa.String(length=20),
            nullable=False,
            server_default="success",
            comment="success | denied | error",
        ),

        # ─── Request metadata ──────────────────────────────────────────────
        sa.Column(
            "ip_address",
            sa.String(length=45),
            nullable=True,
            comment="IPv4 or IPv6",
        ),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "session_id",
            sa.String(length=128),
            nullable=True,
            index=True,
            comment="UserSession ID (future M4-P0-2 JWT jti)",
        ),
        sa.Column(
            "correlation_id",
            sa.String(length=128),
            nullable=True,
            index=True,
            comment="Request tracing ID",
        ),

        # ─── Additional context ────────────────────────────────────────────
        sa.Column(
            "extra_data",
            JSON(),
            nullable=True,
            comment="Additional context: form_status, appointment_date, etc.",
        ),

        # ─── Timestamp ─────────────────────────────────────────────────────
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ─── Indexes for common audit queries ──────────────────────────────────
    op.create_index(
        "ix_patient_access_audit_logs_subject_timestamp",
        "patient_access_audit_logs",
        ["subject_patient_id", "timestamp"],
    )
    op.create_index(
        "ix_patient_access_audit_logs_actor_timestamp",
        "patient_access_audit_logs",
        ["actor_patient_id", "timestamp"],
    )
    op.create_index(
        "ix_patient_access_audit_logs_resource_action",
        "patient_access_audit_logs",
        ["resource_type", "action"],
    )
    op.create_index(
        "ix_patient_access_audit_logs_outcome_timestamp",
        "patient_access_audit_logs",
        ["outcome", "timestamp"],
    )
    # Explicit index on timestamp for range queries
    op.create_index(
        "ix_patient_access_audit_logs_timestamp",
        "patient_access_audit_logs",
        ["timestamp"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patient_access_audit_logs_timestamp",
        table_name="patient_access_audit_logs",
    )
    op.drop_index(
        "ix_patient_access_audit_logs_outcome_timestamp",
        table_name="patient_access_audit_logs",
    )
    op.drop_index(
        "ix_patient_access_audit_logs_resource_action",
        table_name="patient_access_audit_logs",
    )
    op.drop_index(
        "ix_patient_access_audit_logs_actor_timestamp",
        table_name="patient_access_audit_logs",
    )
    op.drop_index(
        "ix_patient_access_audit_logs_subject_timestamp",
        table_name="patient_access_audit_logs",
    )
    op.drop_table("patient_access_audit_logs")
