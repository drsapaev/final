"""Align real lab service codes with the correct report templates.

Revision ID: 0012_lab_bind_real_codes
Revises: 0011_lab_tpl_service_bind
Create Date: 2026-03-20 17:20:00.000000

"""

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op
from app.services.lab_template_binding_seed_data import (
    DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS,
)

revision = "0012_lab_bind_real_codes"
down_revision = "0011_lab_tpl_service_bind"
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


def _real_catalog_definitions():
    return [
        definition
        for definition in DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS
        if str(definition["service_code"]).startswith("L")
        or str(definition["service_code"]).startswith("LAB_")
    ]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    desired_templates_by_code: dict[str, set[str]] = {}

    for definition in _real_catalog_definitions():
        service_code = definition["service_code"]
        template_code = definition["template_code"]
        desired_templates_by_code.setdefault(service_code, set()).add(template_code)

        stmt = insert(binding_table).values(
            service_code=service_code,
            template_code=template_code,
            sort_order=definition.get("sort_order", 0),
            is_default=definition.get("is_default", False),
            is_active=definition.get("is_active", True),
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_lab_template_service_binding",
            set_={
                "sort_order": definition.get("sort_order", 0),
                "is_default": definition.get("is_default", False),
                "is_active": definition.get("is_active", True),
                "updated_at": now,
            },
        )
        bind.execute(stmt)

    for service_code, template_codes in desired_templates_by_code.items():
        bind.execute(
            binding_table.update()
            .where(binding_table.c.service_code == service_code)
            .where(~binding_table.c.template_code.in_(sorted(template_codes)))
            .values(
                is_active=False,
                is_default=False,
                sort_order=999,
                updated_at=now,
            )
        )


def downgrade() -> None:
    # This migration intentionally preserves live operator mapping data.
    # Reversing it automatically would reintroduce known-bad bindings.
    pass
