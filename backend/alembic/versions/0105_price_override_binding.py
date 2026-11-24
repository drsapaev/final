"""Add nullable bindings for precise doctor price override requests.

Existing rows remain unknown and must not be approved until re-requested.
This schema alone does not enforce request, payment, or approval invariants.
"""

import sqlalchemy as sa

from alembic import op

revision = "0105_price_override_binding"
down_revision = "0104_encounters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    op.add_column("doctor_price_overrides", sa.Column("target_scope", sa.String(32), nullable=True))
    op.add_column("doctor_price_overrides", sa.Column("visit_context_epoch", sa.BigInteger(), nullable=True))
    op.add_column("doctor_price_overrides", sa.Column("doctor_owner_generation", sa.BigInteger(), nullable=True))
    if dialect == "postgresql":
        op.add_column("doctor_price_overrides", sa.Column("target_visit_service_id", sa.Integer(), nullable=True))
        op.add_column("doctor_price_overrides", sa.Column("doctor_owner_user_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_price_override_target_visit_service", "doctor_price_overrides", "visit_services",
            ["target_visit_service_id"], ["id"], ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_price_override_doctor_owner_user", "doctor_price_overrides", "users",
            ["doctor_owner_user_id"], ["id"], ondelete="SET NULL",
        )
    elif dialect == "sqlite":
        # Inline references avoid rebuilding the table and discarding triggers.
        op.execute("ALTER TABLE doctor_price_overrides ADD COLUMN target_visit_service_id INTEGER REFERENCES visit_services(id) ON DELETE SET NULL")
        op.execute("ALTER TABLE doctor_price_overrides ADD COLUMN doctor_owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
    else:
        raise RuntimeError(f"Unsupported override binding dialect: {dialect}")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    unsafe = """EXISTS (SELECT 1 FROM doctor_price_overrides
        WHERE target_scope IS NOT NULL OR target_visit_service_id IS NOT NULL
           OR visit_context_epoch IS NOT NULL OR doctor_owner_user_id IS NOT NULL
           OR doctor_owner_generation IS NOT NULL)"""
    if dialect == "postgresql":
        # If forced RLS hides rows from the migration role, fail instead of
        # mistaking the table for empty and discarding bound requests.
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE doctor_price_overrides IN ACCESS EXCLUSIVE MODE")
        op.execute(f"""DO $$ BEGIN IF {unsafe} THEN
            RAISE EXCEPTION 'price override downgrade would discard bound requests';
        END IF; END $$""")
        op.drop_constraint("fk_price_override_target_visit_service", "doctor_price_overrides", type_="foreignkey")
        op.drop_constraint("fk_price_override_doctor_owner_user", "doctor_price_overrides", type_="foreignkey")
    elif dialect == "sqlite":
        # Acquire the writer lock before the check; render the guard offline too.
        op.execute("UPDATE doctor_price_overrides SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE price_override_downgrade_guard_0105 (value INTEGER NOT NULL CHECK (value=0))")
        op.execute(f"INSERT INTO price_override_downgrade_guard_0105 SELECT CASE WHEN {unsafe} THEN 1 ELSE 0 END")
        op.execute("DROP TABLE price_override_downgrade_guard_0105")
    else:
        raise RuntimeError(f"Unsupported override binding dialect: {dialect}")
    for name in ("doctor_owner_user_id", "target_visit_service_id", "doctor_owner_generation", "visit_context_epoch", "target_scope"):
        op.drop_column("doctor_price_overrides", name)
