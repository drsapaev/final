"""M4-P1-3: Create patient_relationships table for context roles.

Revision ID: 0041_patient_relationships
Revises: 0040_patient_access_audit
Create Date: 2026-07-15

Epic M4 — Backend Security & Compliance:
Context roles (guardian/heir/caregiver) for non-self PHI access.
Allows one patient (actor) to access another patient's (subject) PHI
based on an authorization relationship.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "0041_patient_relationships"
down_revision = "0040_patient_access_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_relationships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # Subject: whose PHI can be accessed
        sa.Column(
            "subject_patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Patient whose PHI can be accessed (the child/ward/deceased)",
        ),

        # Actor: who can access the PHI
        sa.Column(
            "actor_patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Patient who can access the subject's PHI (the guardian/heir/caregiver)",
        ),

        # Relationship type
        sa.Column(
            "relationship_type",
            sa.String(length=20),
            nullable=False,
            index=True,
            comment="guardian | heir | caregiver",
        ),

        # Permissions (JSON)
        sa.Column(
            "permissions",
            JSON(),
            nullable=True,
            comment="Allowed resource:actions. null = all, {} = none.",
        ),

        # Validity period
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When access becomes valid. null = immediately.",
        ),
        sa.Column(
            "valid_to",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When access expires. null = indefinite.",
        ),

        # Status
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            index=True,
            comment="Can be deactivated without deleting the record.",
        ),

        # Audit
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Admin who created this relationship.",
        ),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the relationship was deactivated.",
        ),
        sa.Column(
            "deactivated_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Admin who deactivated this relationship.",
        ),

        # Notes
        sa.Column(
            "notes",
            sa.String(length=512),
            nullable=True,
            comment="Optional notes (e.g. court order reference, guardianship document).",
        ),
    )

    # Constraints
    op.create_check_constraint(
        "ck_patient_relationships_subject_not_actor",
        "patient_relationships",
        "subject_patient_id != actor_patient_id",
    )

    # Indexes
    op.create_index(
        "ix_patient_relationships_unique_active",
        "patient_relationships",
        ["subject_patient_id", "actor_patient_id", "relationship_type"],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )
    op.create_index(
        "ix_patient_relationships_subject_type",
        "patient_relationships",
        ["subject_patient_id", "relationship_type"],
    )
    op.create_index(
        "ix_patient_relationships_actor_type",
        "patient_relationships",
        ["actor_patient_id", "relationship_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patient_relationships_actor_type",
        table_name="patient_relationships",
    )
    op.drop_index(
        "ix_patient_relationships_subject_type",
        table_name="patient_relationships",
    )
    op.drop_index(
        "ix_patient_relationships_unique_active",
        table_name="patient_relationships",
    )
    op.drop_constraint(
        "ck_patient_relationships_subject_not_actor",
        "patient_relationships",
        type_="check",
    )
    op.drop_table("patient_relationships")
