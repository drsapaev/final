"""Add typed result snapshots, ordered-test identity, and operational receipts."""

import sqlalchemy as sa

from alembic import op

revision = "0106_lab_result_contracts"
down_revision = "0105_lab_review_release"
branch_labels = None
depends_on = None

REFERENCE_SCOPE = ("analyte_code", "sex", "age_min_months", "age_max_months")
REFERENCE_DIMENSIONS = ("material_code", "method_code", "unit_code")
REFERENCE_LEGACY_INDEX = "uq_lab_catalog_reference_range_scope"
REFERENCE_DIMENSIONS_INDEX = "uq_lab_catalog_reference_range_dimensions"
NEW_TABLES = (
    "lab_order_tests",
    "lab_critical_communications",
    "lab_critical_communication_events",
    "lab_import_receipts",
)


def upgrade() -> None:
    op.add_column(
        "lab_report_values", sa.Column("result_payload", sa.JSON(), nullable=True)
    )
    op.add_column(
        "lab_report_values", sa.Column("evaluation_snapshot", sa.JSON(), nullable=True)
    )
    for name, size in (("material_code", 64), ("method_code", 64), ("unit_code", 32)):
        op.add_column(
            "lab_catalog_reference_ranges",
            sa.Column(name, sa.String(size), nullable=True),
        )
    op.drop_constraint(
        REFERENCE_LEGACY_INDEX, "lab_catalog_reference_ranges", type_="unique"
    )
    op.create_index(
        REFERENCE_LEGACY_INDEX,
        "lab_catalog_reference_ranges",
        [*REFERENCE_SCOPE, "sort_order"],
        unique=True,
        postgresql_where=sa.text(
            " AND ".join(f"{name} IS NULL" for name in REFERENCE_DIMENSIONS)
        ),
    )
    op.create_index(
        REFERENCE_DIMENSIONS_INDEX,
        "lab_catalog_reference_ranges",
        [*REFERENCE_SCOPE, *REFERENCE_DIMENSIONS, "sort_order"],
        unique=True,
        postgresql_where=sa.text(
            " OR ".join(f"{name} IS NOT NULL" for name in REFERENCE_DIMENSIONS)
        ),
        postgresql_nulls_not_distinct=True,
    )
    op.add_column(
        "lab_orders", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("lab_orders", sa.Column("priority", sa.String(16), nullable=True))
    op.create_check_constraint(
        "ck_lab_orders_priority",
        "lab_orders",
        "priority IS NULL OR priority IN ('routine', 'urgent')",
    )
    op.create_table(
        "lab_order_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("lab_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "visit_service_id",
            sa.Integer(),
            sa.ForeignKey("visit_services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "report_instance_id",
            sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="RESTRICT"),
        ),
        sa.Column("canceled_at", sa.DateTime(timezone=True)),
        sa.Column(
            "canceled_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("cancel_reason", sa.String(300)),
        sa.UniqueConstraint(
            "visit_service_id", name="uq_lab_order_tests_visit_service"
        ),
        sa.CheckConstraint(
            "(canceled_at IS NULL AND canceled_by_user_id IS NULL AND cancel_reason IS NULL) OR "
            "(canceled_at IS NOT NULL AND canceled_by_user_id IS NOT NULL "
            "AND cancel_reason IS NOT NULL AND report_instance_id IS NULL)",
            name="ck_lab_order_tests_cancellation",
        ),
    )
    op.create_index("ix_lab_order_tests_order_id", "lab_order_tests", ["order_id"])
    op.create_index(
        "ix_lab_order_tests_report_instance_id",
        "lab_order_tests",
        ["report_instance_id"],
    )
    op.create_table(
        "lab_critical_communications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "report_instance_id",
            sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "supersedes_communication_id",
            sa.Integer(),
            sa.ForeignKey("lab_critical_communications.id", ondelete="RESTRICT"),
        ),
        sa.Column("field_keys", sa.JSON(), nullable=False),
        sa.Column(
            "recipient_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "released_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "acknowledged_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("inbox_recorded_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("escalated_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_lab_critical_dispatch",
        "lab_critical_communications",
        ["state", "next_attempt_at"],
    )
    op.create_index(
        "ix_lab_critical_recipient",
        "lab_critical_communications",
        ["recipient_user_id", "state"],
    )
    op.create_table(
        "lab_critical_communication_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "communication_id",
            sa.Integer(),
            sa.ForeignKey("lab_critical_communications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("channel", sa.String(24)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_lab_critical_events_communication",
        "lab_critical_communication_events",
        ["communication_id", "id"],
    )
    op.create_table(
        "lab_import_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "report_instance_id",
            sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "specimen_id",
            sa.Integer(),
            sa.ForeignKey("lab_specimens.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("field_keys", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_token", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "source", "message_id", name="uq_lab_import_source_message"
        ),
    )
    op.create_index(
        "ix_lab_import_report", "lab_import_receipts", ["report_instance_id"]
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in NEW_TABLES:
            op.execute(sa.text(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    bind = op.get_bind()
    populated_checks = (
        *(f"SELECT 1 FROM {table}" for table in NEW_TABLES),
        "SELECT 1 FROM lab_report_values WHERE result_payload IS NOT NULL OR evaluation_snapshot IS NOT NULL",
        "SELECT 1 FROM lab_catalog_reference_ranges WHERE material_code IS NOT NULL OR method_code IS NOT NULL OR unit_code IS NOT NULL",
        "SELECT 1 FROM lab_orders WHERE due_at IS NOT NULL OR priority IS NOT NULL",
    )
    if bind.dialect.name == "postgresql":
        tables = (
            *NEW_TABLES,
            "lab_report_values",
            "lab_catalog_reference_ranges",
            "lab_orders",
        )
        bind.execute(
            sa.text(f"LOCK TABLE {', '.join(tables)} IN ACCESS EXCLUSIVE MODE")
        )
    if any(
        bind.scalar(sa.text(f"SELECT EXISTS ({query})")) for query in populated_checks
    ):
        raise RuntimeError(
            "Laboratory v2 data is present. Restore compatible application code or use a forward fix."
        )

    for table in reversed(NEW_TABLES):
        op.drop_table(table)
    op.drop_constraint("ck_lab_orders_priority", "lab_orders", type_="check")
    for name in ("priority", "due_at"):
        op.drop_column("lab_orders", name)
    op.drop_index(REFERENCE_DIMENSIONS_INDEX, table_name="lab_catalog_reference_ranges")
    op.drop_index(REFERENCE_LEGACY_INDEX, table_name="lab_catalog_reference_ranges")
    op.create_unique_constraint(
        REFERENCE_LEGACY_INDEX,
        "lab_catalog_reference_ranges",
        [*REFERENCE_SCOPE, "sort_order"],
    )
    for name in ("unit_code", "method_code", "material_code"):
        op.drop_column("lab_catalog_reference_ranges", name)
    for name in ("evaluation_snapshot", "result_payload"):
        op.drop_column("lab_report_values", name)
