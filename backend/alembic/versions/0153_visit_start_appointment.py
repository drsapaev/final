"""Preserve an appointment resolved before the first actual visit start."""

from alembic import op
import sqlalchemy as sa

revision = "0153_visit_start_appointment"
down_revision = "0152_refund_claim_truncate_guard"
branch_labels = None
depends_on = None

INDEX = "uq_visits_started_appointment"
FOREIGN_KEY = "fk_visits_started_appointment"
CHECK = "ck_visits_started_appointment_checked"


def upgrade() -> None:
    schema = op.get_context().opts.get("version_table_schema")
    with op.batch_alter_table("visits", schema=schema) as table:
        table.add_column(
            sa.Column("started_appointment_checked", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        table.add_column(sa.Column("started_appointment_id", sa.Integer(), nullable=True))
        table.create_foreign_key(
            FOREIGN_KEY, "appointments", ["started_appointment_id"], ["id"],
            referent_schema=schema, ondelete="SET NULL",
        )
        table.create_check_constraint(CHECK, "started_appointment_id IS NULL OR started_appointment_checked")

    paired = sa.text("started_appointment_id IS NOT NULL")
    op.create_index(
        INDEX, "visits", ["started_appointment_id"], unique=True, schema=schema,
        postgresql_where=paired, sqlite_where=paired,
    )


def downgrade() -> None:
    context = op.get_context()
    schema = context.opts.get("version_table_schema")
    if context.dialect.name == "postgresql":
        qualifier = f"{context.dialect.identifier_preparer.quote_schema(schema)}." if schema else ""
        visits = f"{qualifier}visits"
        tag = "$started_appointment$"
        while tag in visits:
            tag = tag[:-1] + "_x$"
        # Preserve any captured clinical provenance and fence concurrent starts.
        op.execute("SET LOCAL row_security=off")
        op.execute(f"LOCK TABLE {visits} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""DO {tag} BEGIN
            IF EXISTS (SELECT 1 FROM {visits} WHERE started_appointment_checked) THEN
                RAISE EXCEPTION 'Started appointment evidence prevents downgrade';
            END IF;
        END {tag}""")
    else:
        visits_table = sa.table("visits", sa.column("started_appointment_checked", sa.Boolean), schema=schema)
        if op.get_bind().scalar(sa.select(visits_table.c.started_appointment_checked).where(
            visits_table.c.started_appointment_checked
        ).limit(1)):
            raise RuntimeError("Started appointment evidence prevents downgrade")

    op.drop_index(INDEX, table_name="visits", schema=schema)
    with op.batch_alter_table("visits", schema=schema) as table:
        table.drop_constraint(CHECK, type_="check")
        table.drop_constraint(FOREIGN_KEY, type_="foreignkey")
        table.drop_column("started_appointment_id")
        table.drop_column("started_appointment_checked")
