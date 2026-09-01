"""Medical Specialty Catalog — table + baseline seed.

Owner decision 2026-09-01 (prerequisite for canonical doctor onboarding,
PR scope excludes admin UI / FK / queue+Department integration):

- ``medical_specialties`` becomes the RUNTIME SSOT for the specialty
  vocabulary selectable at new-doctor onboarding.
- ``Doctor.specialty`` stays a plain string — the catalog is a
  validation/source-of-options layer, NOT a foreign key.
- Baseline seed (cardiology / dermatology / dentistry) is deterministic and
  non-destructive: ``ON CONFLICT (code) DO NOTHING`` never overwrites
  admin-edited display titles.
- Canonical codes only: the "general" incomplete sentinel and legacy
  dental-family aliases (dental/stomatology/dentist) are NOT seeded.
- No runtime hardcoded fallback exists: an empty catalog is an explicit
  configuration error (see MedicalSpecialtyCatalogService).

Downgrade drops the catalog table. Doctor rows are untouched either way —
the catalog never owned doctor data.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from app.services.medical_specialty_seed import seed_medical_specialties

# Revision identifiers — chained after 0050_enable_rls_sweep.
revision = "0051_medical_specialty_catalog"
down_revision = "0050_enable_rls_sweep"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medical_specialties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title_ru", sa.String(length=200), nullable=False),
        sa.Column("title_uz", sa.String(length=200), nullable=True),
        sa.Column("title_en", sa.String(length=200), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_specialties")),
        sa.UniqueConstraint("code", name=op.f("uq_medical_specialties_code")),
    )
    op.create_index(
        op.f("ix_medical_specialties_id"), "medical_specialties", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_medical_specialties_code"), "medical_specialties", ["code"], unique=False
    )
    # RLS parity with the 0046/0050 sweeps: the app connects as the table
    # owner and bypasses RLS; deny-all for PostgREST anon/authenticated.
    op.execute("ALTER TABLE medical_specialties ENABLE ROW LEVEL SECURITY")

    seed_medical_specialties(op.get_bind())


def downgrade() -> None:
    op.drop_index(op.f("ix_medical_specialties_code"), table_name="medical_specialties")
    op.drop_index(op.f("ix_medical_specialties_id"), table_name="medical_specialties")
    op.drop_table("medical_specialties")
