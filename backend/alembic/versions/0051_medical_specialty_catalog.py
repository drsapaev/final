"""Medical Specialty Catalog — table + baseline seed (adoption-aware).

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

Adoption (Codex round-4 P1): production already contains an out-of-band
``public.medical_specialties`` (see
docs/incidents/2026-09-02-supabase-rls-disabled-in-public.md — created
outside Alembic, RLS re-enabled by the sweep). Following the
0051_salary_tables_adoption pattern, an EXISTING table is adopted as-is
(create skipped, indexes/RLS applied idempotently); fresh installs get the
full CREATE. Either way the baseline seed then runs.

Downgrade drops the catalog table. Doctor rows are untouched either way —
the catalog never owned doctor data.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import context, op

from app.services.medical_specialty_seed import seed_medical_specialties

# Revision identifiers — chained after 0050_enable_rls_sweep.
revision = "0051_medical_specialty_catalog"
down_revision = "0050_enable_rls_sweep"
branch_labels = None
depends_on = None

_EXPECTED_COLUMNS = {
    "id", "code", "title_ru", "title_uz", "title_en",
    "active", "sort_order", "created_at", "updated_at",
}


def _create_catalog_table() -> None:
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


def upgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        # Offline `--sql` mode runs on a MockConnection with no inspector:
        # render the fresh-install path (CREATE + indexes + RLS + seed).
        # Online runs (CI Postgres, production) take the adoption-aware
        # branch below against the real catalog state.
        _create_catalog_table()
        op.create_index(
            op.f("ix_medical_specialties_id"), "medical_specialties", ["id"], unique=False
        )
        op.create_index(
            op.f("ix_medical_specialties_code"), "medical_specialties", ["code"], unique=False
        )
        op.execute("ALTER TABLE medical_specialties ENABLE ROW LEVEL SECURITY")
        seed_medical_specialties(bind)
        return

    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names(schema="public"))

    if "medical_specialties" in existing:
        # Adoption path: live table already exists (out-of-band creation,
        # see the RLS incident doc). Validate the shape we are about to own,
        # then take it over without destructive changes.
        columns = {col["name"] for col in inspector.get_columns("medical_specialties")}
        missing = _EXPECTED_COLUMNS - columns
        if missing:
            raise RuntimeError(
                "0051 adoption: public.medical_specialties exists but is missing "
                f"expected columns {sorted(missing)} — manual reconciliation "
                "required before this migration can adopt the table"
            )
        print("0051 adoption: public.medical_specialties already exists — skipping CREATE")
    else:
        _create_catalog_table()

    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes("medical_specialties")
    }
    if "ix_medical_specialties_id" not in existing_indexes:
        op.create_index(
            op.f("ix_medical_specialties_id"), "medical_specialties", ["id"], unique=False
        )
    if "ix_medical_specialties_code" not in existing_indexes:
        op.create_index(
            op.f("ix_medical_specialties_code"), "medical_specialties", ["code"], unique=False
        )
    # RLS parity with the 0046/0050 sweeps (idempotent): the app connects as
    # the table owner and bypasses RLS; deny-all for PostgREST roles.
    op.execute("ALTER TABLE medical_specialties ENABLE ROW LEVEL SECURITY")

    seed_medical_specialties(bind)


def downgrade() -> None:
    op.drop_index(op.f("ix_medical_specialties_code"), table_name="medical_specialties")
    op.drop_index(op.f("ix_medical_specialties_id"), table_name="medical_specialties")
    op.drop_table("medical_specialties")
