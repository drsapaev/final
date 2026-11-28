"""Add versioned review, QC, release, and correction history for lab reports."""

import sqlalchemy as sa

from alembic import op

revision = "0105_lab_review_release"
down_revision = "0104_lab_specimens"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("lab:review", "Лаборатория: проверка результатов"),
    ("lab:release", "Лаборатория: выпуск результатов"),
    ("lab:qc", "Лаборатория: регистрация контроля качества"),
)


def upgrade() -> None:
    op.add_column(
        "lab_report_instances",
        sa.Column(
            "managed_release", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.create_table(
        "lab_report_workflow_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "instance_id",
            sa.Integer(),
            sa.ForeignKey("lab_report_instances.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_version", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_version", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(1000)),
        sa.Column("evidence", sa.JSON()),
        sa.CheckConstraint(
            "kind IN ('entered', 'submitted', 'reviewed', 'returned', "
            "'qc_recorded', 'finalized', 'revision_created')",
            name="ck_lab_workflow_event_kind",
        ),
    )
    op.create_index(
        "ix_lab_workflow_event_report_kind",
        "lab_report_workflow_events",
        ["instance_id", "kind", "id"],
    )
    op.create_index(
        "ix_lab_report_workflow_events_actor_user_id",
        "lab_report_workflow_events",
        ["actor_user_id"],
    )

    permissions = sa.table(
        "permissions",
        sa.column("codename", sa.String()),
        sa.column("name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    for code, name in _PERMISSIONS:
        op.execute(
            permissions.insert().from_select(
                ["codename", "name", "category", "is_active"],
                sa.select(
                    op.inline_literal(code),
                    op.inline_literal(name),
                    op.inline_literal("lab"),
                    sa.true(),
                ).where(
                    ~sa.exists(
                        sa.select(permissions.c.codename).where(
                            permissions.c.codename == op.inline_literal(code),
                        )
                    )
                ),
            )
        )

    if op.get_context().dialect.name != "postgresql":
        return

    op.execute(
        "ALTER TABLE public.lab_report_workflow_events ENABLE ROW LEVEL SECURITY"
    )
    op.execute("""
        CREATE FUNCTION prevent_lab_workflow_event_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Laboratory workflow events are append-only';
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_lab_workflow_event_immutable
        BEFORE UPDATE OR DELETE ON lab_report_workflow_events
        FOR EACH ROW EXECUTE FUNCTION prevent_lab_workflow_event_mutation();
    """)
    op.execute("""
        CREATE FUNCTION enforce_lab_report_managed_release()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.managed_release IS DISTINCT FROM NEW.managed_release THEN
                RAISE EXCEPTION 'Laboratory report release mode is fixed at creation';
            END IF;
            IF NEW.managed_release AND NEW.status = 'FINALIZED' AND OLD.status <> 'REVIEWED' THEN
                RAISE EXCEPTION 'Managed laboratory release requires a reviewed report';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_lab_report_managed_release
        BEFORE UPDATE ON lab_report_instances
        FOR EACH ROW EXECUTE FUNCTION enforce_lab_report_managed_release();
    """)
    op.execute("""
        CREATE FUNCTION require_lab_report_release_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM lab_report_workflow_events AS release
                JOIN lab_report_workflow_events AS review
                  ON review.instance_id = release.instance_id
                 AND review.kind = 'reviewed'
                 AND review.report_version = release.expected_version
                WHERE release.instance_id = NEW.id
                  AND release.kind = 'finalized'
                  AND release.report_version = NEW.updated_at
                  AND release.expected_version = OLD.updated_at
            ) THEN
                RAISE EXCEPTION 'Managed report release requires review and release evidence';
            END IF;
            RETURN NULL;
        END;
        $$;
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_lab_report_release_evidence
        AFTER UPDATE ON lab_report_instances
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        WHEN (NEW.managed_release AND NEW.status = 'FINALIZED')
        EXECUTE FUNCTION require_lab_report_release_evidence();
    """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "LOCK TABLE lab_report_instances, lab_report_workflow_events IN ACCESS EXCLUSIVE MODE"
        )
    has_workflow_data = bind.execute(
        sa.text("""
        SELECT EXISTS (SELECT 1 FROM lab_report_workflow_events)
            OR EXISTS (SELECT 1 FROM lab_report_instances WHERE managed_release)
    """)
    ).scalar_one()
    if has_workflow_data:
        raise RuntimeError("Refusing to remove laboratory release history.")

    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER trg_lab_report_release_evidence ON lab_report_instances"
        )
        op.execute("DROP FUNCTION require_lab_report_release_evidence()")
        op.execute(
            "DROP TRIGGER trg_lab_report_managed_release ON lab_report_instances"
        )
        op.execute("DROP FUNCTION enforce_lab_report_managed_release()")
    op.drop_table("lab_report_workflow_events")
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION prevent_lab_workflow_event_mutation()")
    op.drop_column("lab_report_instances", "managed_release")
    # The permissions are intentionally retained. Grants use the existing
    # roles system and must never disappear implicitly during a code rollback.
