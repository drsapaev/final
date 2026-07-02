"""schema_parity_tables

Revision ID: 0003_schema_parity_tables
Revises: 0002_emr_v2_hard_cutover
Create Date: 2026-03-19 11:30:00.000000

"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

from app.db.base_class import Base

# Import model modules so their tables are registered on Base.metadata.
import app.models.discount_benefits  # noqa: F401
import app.models.doctor_templates  # noqa: F401
import app.models.dynamic_pricing  # noqa: F401
import app.models.section_templates  # noqa: F401
import app.models.webhook  # noqa: F401


# revision identifiers, used by Alembic.
revision = "0003_schema_parity_tables"
down_revision = "0002_emr_v2_hard_cutover"
branch_labels = None
depends_on = None


TARGET_TABLES = {
    "benefit_applications",
    "benefits",
    "discount_applications",
    "discount_services",
    "discounts",
    "doctor_section_templates",
    "doctor_treatment_templates",
    "dynamic_prices",
    "loyalty_point_transactions",
    "loyalty_programs",
    "package_purchases",
    "package_services",
    "patient_benefits",
    "patient_loyalty",
    "price_history",
    "pricing_rule_services",
    "pricing_rules",
    "service_packages",
    "webhook_calls",
    "webhook_events",
    "webhooks",
}


def _ordered_target_tables() -> list[str]:
    return [
        table.name
        for table in Base.metadata.sorted_tables
        if table.name in TARGET_TABLES
    ]


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    metadata_tables = Base.metadata.tables

    for table_name in _ordered_target_tables():
        if table_name in existing_tables:
            continue
        metadata_tables[table_name].create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    metadata_tables = Base.metadata.tables

    for table_name in reversed(_ordered_target_tables()):
        if table_name not in existing_tables:
            continue
        metadata_tables[table_name].drop(bind, checkfirst=True)
