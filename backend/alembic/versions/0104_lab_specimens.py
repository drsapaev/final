"""Add specimen identities, assignment links, and custody events."""

import sqlalchemy as sa

from alembic import op

revision = "0104_lab_specimens"
down_revision = "0103_public_site_daily_counts"
branch_labels = None
depends_on = None

TABLES = ("lab_specimens", "lab_specimen_assignments", "lab_specimen_events")


def upgrade() -> None:
    op.create_table(
        "lab_specimens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("lab_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("barcode", sa.String(24), nullable=False),
        sa.Column("material_code", sa.String(32), nullable=False),
        sa.Column("container_code", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("parent_specimen_id", sa.Integer()),
        sa.Column("replaces_specimen_id", sa.Integer()),
        sa.Column("create_request_id", sa.String(36), nullable=False),
        sa.Column("latest_reason", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "order_id", name="uq_lab_specimens_id_order"),
        sa.UniqueConstraint("barcode", name="uq_lab_specimens_barcode"),
        sa.UniqueConstraint(
            "order_id", "create_request_id", name="uq_lab_specimens_create_request"
        ),
        sa.UniqueConstraint(
            "replaces_specimen_id", name="uq_lab_specimens_replacement"
        ),
        sa.ForeignKeyConstraint(
            ["parent_specimen_id", "order_id"],
            ["lab_specimens.id", "lab_specimens.order_id"],
            name="fk_lab_specimens_parent_order",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replaces_specimen_id", "order_id"],
            ["lab_specimens.id", "lab_specimens.order_id"],
            name="fk_lab_specimens_replacement_order",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "parent_specimen_id IS NULL OR replaces_specimen_id IS NULL",
            name="ck_lab_specimens_single_origin",
        ),
        sa.CheckConstraint(
            "(parent_specimen_id IS NULL OR parent_specimen_id <> id) AND "
            "(replaces_specimen_id IS NULL OR replaces_specimen_id <> id)",
            name="ck_lab_specimens_no_self_reference",
        ),
        sa.CheckConstraint(
            "status IN ('expected', 'collected', 'received', 'accepted', 'held', 'rejected')",
            name="ck_lab_specimens_status",
        ),
        sa.CheckConstraint("revision > 0", name="ck_lab_specimens_revision"),
    )
    op.create_index(
        "ix_lab_specimens_order_status", "lab_specimens", ["order_id", "status"]
    )
    op.create_index("ix_lab_specimens_parent", "lab_specimens", ["parent_specimen_id"])
    op.create_table(
        "lab_specimen_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specimen_id",
            sa.Integer(),
            sa.ForeignKey("lab_specimens.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "visit_service_id",
            sa.Integer(),
            sa.ForeignKey("visit_services.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "report_instance_id",
            sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="RESTRICT"),
        ),
        sa.UniqueConstraint(
            "specimen_id", "visit_service_id", name="uq_lab_specimen_visit_service"
        ),
        sa.UniqueConstraint(
            "specimen_id", "report_instance_id", name="uq_lab_specimen_report"
        ),
        sa.CheckConstraint(
            "(visit_service_id IS NULL) <> (report_instance_id IS NULL)",
            name="ck_lab_specimen_assignment_target",
        ),
    )
    op.create_index(
        "ix_lab_specimen_assignments_visit_service_id",
        "lab_specimen_assignments",
        ["visit_service_id"],
    )
    op.create_index(
        "ix_lab_specimen_assignments_report_instance_id",
        "lab_specimen_assignments",
        ["report_instance_id"],
    )
    op.create_table(
        "lab_specimen_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specimen_id",
            sa.Integer(),
            sa.ForeignKey("lab_specimens.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("resulting_status", sa.String(16), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(300)),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("visit_service_ids", sa.JSON(), nullable=False),
        sa.Column("report_instance_ids", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "specimen_id", "revision", name="uq_lab_specimen_event_revision"
        ),
        sa.UniqueConstraint(
            "specimen_id", "request_id", name="uq_lab_specimen_event_request"
        ),
        sa.CheckConstraint("revision > 0", name="ck_lab_specimen_event_revision"),
    )
    op.create_index(
        "ix_lab_specimen_events_actor_user_id", "lab_specimen_events", ["actor_user_id"]
    )
    if op.get_context().dialect.name == "postgresql":
        for table_name in TABLES:
            op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute("""
        CREATE FUNCTION public.reject_lab_specimen_event_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'Lab specimen events are immutable';
        END;
        $$
        """)
        op.execute("""
        CREATE TRIGGER trg_lab_specimen_events_immutable
        BEFORE UPDATE OR DELETE ON public.lab_specimen_events
        FOR EACH ROW EXECUTE FUNCTION public.reject_lab_specimen_event_change()
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in TABLES:
            bind.execute(
                sa.text(f"LOCK TABLE public.{table_name} IN ACCESS EXCLUSIVE MODE")
            )
    if bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM lab_specimens)")
    ).scalar_one():
        raise RuntimeError(
            "Refusing to remove recorded lab specimens and custody history."
        )
    for table_name in reversed(TABLES):
        op.drop_table(table_name)
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION public.reject_lab_specimen_event_change()")
