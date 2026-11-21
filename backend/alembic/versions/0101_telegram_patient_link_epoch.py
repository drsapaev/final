"""Fence patient-chat capabilities across revocation and relinking."""

import sqlalchemy as sa

from alembic import op

revision = "0101_tg_patient_link_epoch"
down_revision = "0100_appointment_rsvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_users",
        sa.Column(
            "patient_link_epoch", sa.BigInteger(),
            sa.CheckConstraint("patient_link_epoch >= 0", name="ck_telegram_user_patient_link_epoch"),
            server_default="0", nullable=False,
        ),
    )
    if op.get_context().dialect.name == "postgresql":
        # Reinitialise per row on every upgrade, including after a downgrade.
        # Otherwise an old signed invitation could revive when the epoch resets.
        op.execute("UPDATE telegram_users SET patient_link_epoch = floor(random() * 4503599627370496)::bigint + 1")
        op.alter_column("telegram_users", "patient_link_epoch", server_default=sa.text("(floor(random() * 4503599627370496)::bigint + 1)"))
        op.execute("""
        CREATE FUNCTION bump_telegram_patient_link_epoch() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            NEW.patient_link_epoch := floor(random() * 4503599627370496)::bigint + 1;
          ELSIF ROW(NEW.patient_id, NEW.chat_id, NEW.active, NEW.blocked,
                 NEW.notifications_enabled, NEW.appointment_reminders)
             IS DISTINCT FROM
             ROW(OLD.patient_id, OLD.chat_id, OLD.active, OLD.blocked,
                 OLD.notifications_enabled, OLD.appointment_reminders) THEN
            NEW.patient_link_epoch := floor(random() * 4503599627370496)::bigint + 1;
          ELSE
            NEW.patient_link_epoch := OLD.patient_link_epoch;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """)
        op.execute("""
        CREATE TRIGGER trg_telegram_patient_link_epoch
        BEFORE INSERT OR UPDATE ON telegram_users
        FOR EACH ROW EXECUTE FUNCTION bump_telegram_patient_link_epoch()
        """)
    elif op.get_context().dialect.name == "sqlite":
        op.execute("UPDATE telegram_users SET patient_link_epoch = (random() & 4503599627370495) + 1")
        op.execute("""
        CREATE TRIGGER trg_telegram_patient_link_epoch_insert
        AFTER INSERT ON telegram_users FOR EACH ROW
        BEGIN
          UPDATE telegram_users SET patient_link_epoch = (random() & 4503599627370495) + 1
          WHERE id = NEW.id;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_telegram_patient_link_epoch
        AFTER UPDATE OF patient_id, chat_id, active, blocked,
                        notifications_enabled, appointment_reminders
        ON telegram_users FOR EACH ROW
        WHEN OLD.patient_id IS NOT NEW.patient_id OR OLD.chat_id IS NOT NEW.chat_id
          OR OLD.active IS NOT NEW.active OR OLD.blocked IS NOT NEW.blocked
          OR OLD.notifications_enabled IS NOT NEW.notifications_enabled
          OR OLD.appointment_reminders IS NOT NEW.appointment_reminders
        BEGIN
          UPDATE telegram_users SET patient_link_epoch = (random() & 4503599627370495) + 1
          WHERE id = NEW.id;
        END
        """)


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER trg_telegram_patient_link_epoch ON telegram_users")
        op.execute("DROP FUNCTION bump_telegram_patient_link_epoch()")
    elif op.get_context().dialect.name == "sqlite":
        op.execute("DROP TRIGGER trg_telegram_patient_link_epoch")
        op.execute("DROP TRIGGER trg_telegram_patient_link_epoch_insert")
    op.drop_column("telegram_users", "patient_link_epoch")
