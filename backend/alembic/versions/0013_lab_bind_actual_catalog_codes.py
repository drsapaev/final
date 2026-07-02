"""Synchronize lab template bindings with the live registrar catalog.

Revision ID: 0013_lab_bind_actual_codes
Revises: 0012_lab_bind_real_codes
Create Date: 2026-03-20 17:55:00.000000

"""

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision = "0013_lab_bind_actual_codes"
down_revision = "0012_lab_bind_real_codes"
branch_labels = None
depends_on = None


binding_table = sa.table(
    "lab_template_service_bindings",
    sa.column("service_code", sa.String(length=32)),
    sa.column("template_code", sa.String(length=64)),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_default", sa.Boolean()),
    sa.column("is_active", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


DESIRED_REAL_CODE_BINDINGS = {
    "L01": "cbc_oak",
    "L02": "cbc_oak",
    "L03": "glucose_coag_panel",
    "L10": "biochem_panel",
    "L11": "glucose_panel",
    "L12": "biochem_panel",
    "L13": "biochem_panel",
    "L14": "biochem_panel",
    "L15": "biochem_panel",
    "L16": "biochem_panel",
    "L17": "biochem_panel",
    "L18": "biochem_panel",
    "L19": "biochem_panel",
    "L20": "biochem_panel",
    "L21": "biochem_panel",
    "L22": "biochem_panel",
    "L25": "urinalysis_oam",
    "L26": "urinalysis_oam",
    "L30": "hepatitis_bs",
    "L31": "hepatitis_bs",
    "L32": "syphilis_hiv",
    "L33": "syphilis_hiv",
    "L34": "spermogramma",
    "L35": "glucose_panel",
    "L40": "revmoprobe",
    "L41": "revmoprobe",
    "L42": "revmoprobe",
    "L43": "revmoprobe",
    "L50": "thyroid_hormones",
    "L51": "thyroid_hormones",
    "L52": "thyroid_hormones",
    "L53": "thyroid_hormones",
    "L60": "fungal_hyphae_panel",
    "L61": "malassezia_panel",
    "L62": "demodex_panel",
    "L63": "smear_cleanliness",
    "L64": "helminth_panel",
    "L65": "ige_total",
}

# These services exist in the live registrar catalog but do not yet have
# a template with exact field coverage in the lab module.
UNSUPPORTED_REAL_CODES = {"L23", "L24", "L54"}

# Older real-code experiments to deactivate if they still exist.
LEGACY_REAL_CODES = {"L00", "L05", "L27", "L28", "L29"}


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    for service_code, template_code in DESIRED_REAL_CODE_BINDINGS.items():
        stmt = insert(binding_table).values(
            service_code=service_code,
            template_code=template_code,
            sort_order=10,
            is_default=True,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_lab_template_service_binding",
            set_={
                "sort_order": 10,
                "is_default": True,
                "is_active": True,
                "updated_at": now,
            },
        )
        bind.execute(stmt)

    cleanup_codes = sorted(
        set(DESIRED_REAL_CODE_BINDINGS)
        | UNSUPPORTED_REAL_CODES
        | LEGACY_REAL_CODES
    )

    for service_code in cleanup_codes:
        desired_template = DESIRED_REAL_CODE_BINDINGS.get(service_code)
        stmt = binding_table.update().where(
            binding_table.c.service_code == service_code
        )
        if desired_template is not None:
            stmt = stmt.where(binding_table.c.template_code != desired_template)
        stmt = stmt.values(
            is_active=False,
            is_default=False,
            sort_order=999,
            updated_at=now,
        )
        bind.execute(stmt)


def downgrade() -> None:
    # Intentionally irreversible: downgrade would re-enable known-wrong mappings.
    pass
