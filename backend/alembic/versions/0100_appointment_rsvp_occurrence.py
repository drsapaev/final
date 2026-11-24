"""Keep patient RSVP separate from the appointment payment lifecycle."""

import sqlalchemy as sa
from alembic import op

revision = "0100_appointment_rsvp"
down_revision = "0099_activation_rate_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("occurrence_revision", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column("appointments", sa.Column("patient_rsvp_at", sa.DateTime(timezone=True)))
    op.add_column("appointments", sa.Column("patient_rsvp_revision", sa.BigInteger()))

    # The database, not just one ORM path, invalidates an RSVP whenever the
    # encounter itself changes. A monotonic revision also prevents A -> B -> A
    # from reviving an old reminder. Payment/status changes do not count unless
    # they enter or leave a terminal status.
    if op.get_context().dialect.name == "postgresql":
        op.execute("""
        CREATE FUNCTION bump_appointment_occurrence_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.patient_id IS DISTINCT FROM NEW.patient_id
             OR OLD.doctor_id IS DISTINCT FROM NEW.doctor_id
             OR OLD.department_id IS DISTINCT FROM NEW.department_id
             OR OLD.appointment_date IS DISTINCT FROM NEW.appointment_date
             OR OLD.appointment_time IS DISTINCT FROM NEW.appointment_time
             OR OLD.duration_minutes_snapshot IS DISTINCT FROM NEW.duration_minutes_snapshot
             OR OLD.notes IS DISTINCT FROM NEW.notes
             OR OLD.visit_type IS DISTINCT FROM NEW.visit_type
             OR OLD.services::jsonb IS DISTINCT FROM NEW.services::jsonb
             OR (OLD.status IS DISTINCT FROM NEW.status AND
                 (lower(OLD.status) IN ('cancelled','canceled','completed','no_show') OR
                  lower(NEW.status) IN ('cancelled','canceled','completed','no_show'))) THEN
            NEW.occurrence_revision := OLD.occurrence_revision + 1;
          END IF;
          RETURN NEW;
        END;
        $$
        """)
        op.execute("""
        CREATE TRIGGER appointments_occurrence_revision
        BEFORE UPDATE ON appointments FOR EACH ROW
        EXECUTE FUNCTION bump_appointment_occurrence_revision()
        """)
    elif op.get_context().dialect.name == "sqlite":
        op.execute("""
        CREATE TRIGGER appointments_occurrence_revision
        AFTER UPDATE OF patient_id, doctor_id, department_id, appointment_date,
          appointment_time, duration_minutes_snapshot, notes, visit_type, services, status
        ON appointments FOR EACH ROW
        WHEN OLD.patient_id IS NOT NEW.patient_id
          OR OLD.doctor_id IS NOT NEW.doctor_id
          OR OLD.department_id IS NOT NEW.department_id
          OR OLD.appointment_date IS NOT NEW.appointment_date
          OR OLD.appointment_time IS NOT NEW.appointment_time
          OR OLD.duration_minutes_snapshot IS NOT NEW.duration_minutes_snapshot
          OR OLD.notes IS NOT NEW.notes
          OR OLD.visit_type IS NOT NEW.visit_type
          OR OLD.services IS NOT NEW.services
          OR (OLD.status IS NOT NEW.status AND
              (lower(OLD.status) IN ('cancelled','canceled','completed','no_show') OR
               lower(NEW.status) IN ('cancelled','canceled','completed','no_show')))
        BEGIN
          UPDATE appointments SET occurrence_revision = OLD.occurrence_revision + 1
          WHERE id = NEW.id;
        END
        """)


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER appointments_occurrence_revision ON appointments")
        op.execute("DROP FUNCTION bump_appointment_occurrence_revision()")
    elif op.get_context().dialect.name == "sqlite":
        op.execute("DROP TRIGGER appointments_occurrence_revision")
    op.drop_column("appointments", "patient_rsvp_revision")
    op.drop_column("appointments", "patient_rsvp_at")
    op.drop_column("appointments", "occurrence_revision")
