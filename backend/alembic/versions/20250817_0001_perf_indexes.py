"""add safe performance indexes (id columns) if tables/columns exist

Revision ID: 20250817_0001
Revises: 20250814_0013_activation
Create Date: 2025-08-17 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20250817_0001"
down_revision = "20250814_0013"
branch_labels = None
depends_on = None


def _ensure_index(conn, table: str, column: str, name: str | None = None):
    """
    Create index if table/column exist and index not present.
    Safe for repeated runs (idempotent).
    """
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())
    if table not in tables:
        return
    cols = {c["name"] for c in insp.get_columns(table)}
    if column not in cols:
        return
    target = name or f"idx_{table}_{column}"
    existing = {ix["name"] for ix in insp.get_indexes(table)}
    if target in existing:
        return
    op.create_index(target, table, [column], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in [
        ("visits", "patient_id"),
        ("visits", "doctor_id"),
        ("visit_services", "visit_id"),
        ("visit_services", "service_id"),
        ("payments", "visit_id"),
        ("payments", "patient_id"),
        ("schedules", "doctor_id"),
        ("schedules", "patient_id"),
        ("queues", "patient_id"),
        ("queues", "service_id"),
        ("online_appointments", "patient_id"),
        ("online_appointments", "doctor_id"),
        ("lab_results", "visit_id"),
        ("audit_trail", "user_id"),
        ("activations", "key"),
        ("activations", "machine_hash"),
    ]:
        _ensure_index(bind, table, column)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    to_drop = [
        "idx_visits_patient_id",
        "idx_visits_doctor_id",
        "idx_visit_services_visit_id",
        "idx_visit_services_service_id",
        "idx_payments_visit_id",
        "idx_payments_patient_id",
        "idx_schedules_doctor_id",
        "idx_schedules_patient_id",
        "idx_queues_patient_id",
        "idx_queues_service_id",
        "idx_online_appointments_patient_id",
        "idx_online_appointments_doctor_id",
        "idx_lab_results_visit_id",
        "idx_audit_trail_user_id",
        "idx_activations_key",
        "idx_activations_machine_hash",
    ]
    tables = set(insp.get_table_names())
    for idx in to_drop:
        parts = idx.split("_")
        if len(parts) < 3:
            continue
        table = "_".join(parts[1:-1])
        if table not in tables:
            continue
        existing = {ix["name"] for ix in insp.get_indexes(table)}
        if idx in existing:
            op.drop_index(idx, table_name=table)
