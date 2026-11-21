"""Store all-free request evidence without granting a discount.

This schema does not authorize actors, enforce immutable audit evidence, close
line totals, validate live generations, or block confirmation/payment. Those
must be implemented together before this evidence can grant a discount. No
historic prices or approvals are inferred by this migration.
"""

import json

import sqlalchemy as sa

from alembic import context as alembic_context
from alembic import op

revision = "0107_all_free_requests"
down_revision = "0106_encounter_benefit_ledger"
branch_labels = None
depends_on = None


def _pin_pg_schema():
    """Use the configured schema and an explicit owner-membership profile."""
    context = op.get_context()
    schema = context.version_table_schema
    if not schema and not context.as_sql:
        schema = op.get_bind().dialect.default_schema_name
    if (not isinstance(schema, str) or not schema or "\0" in schema
            or schema == "information_schema" or schema.startswith("pg_")):
        raise RuntimeError("An explicit trusted application schema is required")
    try:
        if len(schema.encode("utf-8")) > 63:
            raise RuntimeError("An explicit trusted application schema is required")
    except UnicodeError:
        raise RuntimeError("An explicit trusted application schema is required") from None
    value = context.opts.get("trusted_capability_owner_members")
    if value is None:
        try:
            values = [arg.partition("=")[2] for arg in alembic_context.get_x_argument()
                      if arg.partition("=")[0] == "capability_owner_members"]
            if len(values) > 1:
                raise RuntimeError("Invalid capability owner-member allowlist")
            value = values[0] if values else None
        except (AttributeError, NameError):
            value = None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            raise RuntimeError("Invalid capability owner-member allowlist") from None
    value = () if value is None else value
    if not isinstance(value, (tuple, list)):
        raise RuntimeError("Invalid capability owner-member allowlist")
    names = []
    for name in value:
        if (not isinstance(name, str) or not name or "\0" in name
                or name.lower() in {"public", "anon", "authenticated"}):
            raise RuntimeError("Invalid capability owner-member allowlist")
        try:
            if len(name.encode("utf-8")) > 63:
                raise RuntimeError("Invalid capability owner-member allowlist")
        except UnicodeError:
            raise RuntimeError("Invalid capability owner-member allowlist") from None
        names.append(name)
    if len(names) != len(set(names)):
        raise RuntimeError("Invalid capability owner-member allowlist")
    literal = schema.replace("'", "''")
    members = [name.replace("'", "''") for name in names]
    member_array = "ARRAY[" + ",".join("'" + name + "'" for name in members) + "]::text[]"
    tag = "$allfree_0107_schema$"
    while tag in literal or any(tag in name for name in members):
        tag = tag[:-1] + "_x$"
    op.execute("SELECT pg_catalog.set_config('allfree_0107.saved_strings', pg_catalog.current_setting('standard_conforming_strings'), true)")
    op.execute("SELECT pg_catalog.set_config('allfree_0107.saved_path', pg_catalog.current_setting('search_path'), true)")
    op.execute("SET LOCAL standard_conforming_strings=on")
    op.execute(f"""DO {tag} BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles o ON o.oid=n.nspowner
        WHERE n.nspname='{literal}' AND (o.rolsuper OR NOT o.rolcanlogin)
          AND pg_catalog.pg_has_role(CURRENT_USER,n.nspowner,'USAGE')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
            WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.oid<>n.nspowner AND NOT r.rolsuper
            AND pg_catalog.pg_has_role(r.oid,n.nspowner,'MEMBER') AND
            (r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication OR NOT EXISTS (
              SELECT 1 FROM pg_catalog.unnest({member_array}) e(name)
              WHERE pg_catalog.convert_to(r.rolname::text,'UTF8')=pg_catalog.convert_to(e.name,'UTF8'))))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.unnest({member_array}) e(name) WHERE NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles r WHERE r.oid<>n.nspowner AND NOT r.rolsuper
              AND pg_catalog.pg_has_role(r.oid,n.nspowner,'MEMBER')
              AND pg_catalog.convert_to(r.rolname::text,'UTF8')=pg_catalog.convert_to(e.name,'UTF8')))
      ) THEN RAISE EXCEPTION 'All-free migration schema is not trusted'; END IF;
    END {tag}""")
    quote = context.dialect.identifier_preparer.quote_identifier
    op.execute(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog, pg_temp")
    return schema


def _restore_pg_schema():
    op.execute("SELECT pg_catalog.set_config('search_path', pg_catalog.current_setting('allfree_0107.saved_path'), true)")
    op.execute("SELECT pg_catalog.set_config('standard_conforming_strings', pg_catalog.current_setting('allfree_0107.saved_strings'), true)")


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Unsupported all-free request migration dialect")
    schema = _pin_pg_schema() if dialect == "postgresql" else None
    identity_expr = "CASE WHEN encounter_id IS NULL THEN 'N' ELSE 'I' || CAST(encounter_id AS TEXT) END"
    # A generated, non-null key makes a NULL encounter part of the native FK
    # identity as well. SQLite adds a VIRTUAL column without rebuilding Visit.
    op.add_column("visits", sa.Column("allfree_encounter_identity", sa.String(24), sa.Computed(identity_expr, persisted=dialect == "postgresql")))
    op.create_index("uq_visits_allfree_identity", "visits", ["id", "patient_id", "allfree_encounter_identity"], unique=True)
    op.create_index("uq_visit_services_allfree_identity", "visit_services", ["id", "visit_id", "service_id"], unique=True)
    op.create_table(
        "all_free_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="SET NULL")),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id", ondelete="SET NULL")),
        sa.Column("allfree_encounter_identity", sa.String(24), sa.Computed(identity_expr, persisted=dialect == "postgresql")),
        sa.Column("visit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("patient_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("encounter_id_snapshot", sa.Integer()),
        sa.Column("visit_context_epoch", sa.BigInteger(), nullable=False),
        sa.Column("decision_context_epoch", sa.BigInteger()),
        sa.Column("encounter_generation", sa.BigInteger()),
        sa.Column("baseline_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("requested_by_user_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("requested_by_role_snapshot", sa.String(32), nullable=False),
        sa.Column("policy_auto_approve", sa.Boolean(), nullable=False),
        sa.Column("decision_kind", sa.String(16)),
        sa.Column("decided_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_by_user_id_snapshot", sa.Integer()),
        sa.Column("decided_by_role_snapshot", sa.String(32)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("visit_id_snapshot > 0 AND patient_id_snapshot > 0 AND requested_by_user_id_snapshot > 0", name="ck_allfree_request_snapshot_ids"),
        sa.CheckConstraint("encounter_id_snapshot IS NULL OR encounter_id_snapshot > 0", name="ck_allfree_encounter_snapshot"),
        sa.CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_allfree_visit_snapshot"),
        sa.CheckConstraint("patient_id IS NULL OR patient_id = patient_id_snapshot", name="ck_allfree_patient_snapshot"),
        sa.CheckConstraint("encounter_id IS NULL OR (encounter_id_snapshot IS NOT NULL AND encounter_id = encounter_id_snapshot)", name="ck_allfree_encounter_live_snapshot"),
        sa.CheckConstraint("visit_id IS NULL OR patient_id IS NOT NULL", name="ck_allfree_live_patient"),
        sa.CheckConstraint("requested_by_user_id IS NULL OR requested_by_user_id = requested_by_user_id_snapshot", name="ck_allfree_requester_snapshot"),
        sa.CheckConstraint("decided_by_user_id IS NULL OR (decided_by_user_id_snapshot IS NOT NULL AND decided_by_user_id = decided_by_user_id_snapshot)", name="ck_allfree_decider_snapshot"),
        sa.CheckConstraint("visit_context_epoch > 0 AND (decision_context_epoch IS NULL OR decision_context_epoch > 0) AND (encounter_generation IS NULL OR encounter_generation > 0)", name="ck_allfree_epochs"),
        sa.CheckConstraint("baseline_total >= 0 AND baseline_total <= 9999999999.99 AND baseline_total = round(baseline_total, 2)", name="ck_allfree_baseline"),
        sa.CheckConstraint("status IN ('pending','approved','rejected','invalidated')", name="ck_allfree_status"),
        sa.CheckConstraint("decision_kind IS NULL OR decision_kind IN ('admin','policy')", name="ck_allfree_decision_kind"),
        sa.CheckConstraint("length(trim(requested_by_role_snapshot)) > 0", name="ck_allfree_requester_role"),
        sa.CheckConstraint("policy_auto_approve IN (TRUE, FALSE)", name="ck_allfree_policy_boolean"),
        sa.CheckConstraint("decided_by_user_id_snapshot IS NULL OR decided_by_user_id_snapshot > 0", name="ck_allfree_decider_id"),
        sa.CheckConstraint("status NOT IN ('approved','rejected') OR (decision_kind IS NOT NULL AND decided_at IS NOT NULL)", name="ck_allfree_decision_recorded"),
        sa.CheckConstraint("decision_kind != 'admin' OR (decided_by_user_id_snapshot IS NOT NULL AND decided_by_role_snapshot IS NOT NULL AND length(trim(decided_by_role_snapshot)) > 0)", name="ck_allfree_admin_decision_actor"),
        sa.CheckConstraint("status != 'rejected' OR decision_kind = 'admin'", name="ck_allfree_reject_admin"),
        sa.CheckConstraint("decision_kind != 'policy' OR policy_auto_approve", name="ck_allfree_policy_decision"),
        sa.UniqueConstraint("id", "visit_id_snapshot", name="uq_allfree_request_visit_snapshot"),
        sa.ForeignKeyConstraint(["visit_id", "patient_id", "allfree_encounter_identity"],
                                ["visits.id", "visits.patient_id", "visits.allfree_encounter_identity"],
                                name="fk_allfree_visit_identity", deferrable=True, initially="DEFERRED"),
    )
    op.create_index("uq_allfree_active_visit", "all_free_requests", ["visit_id"], unique=True,
                    postgresql_where=sa.text("visit_id IS NOT NULL AND status IN ('pending','approved')"),
                    sqlite_where=sa.text("visit_id IS NOT NULL AND status IN ('pending','approved')"))
    op.create_table(
        "all_free_request_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("all_free_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("visit_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("visit_service_id", sa.Integer(), sa.ForeignKey("visit_services.id", ondelete="SET NULL")),
        sa.Column("visit_service_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("service_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.UniqueConstraint("request_id", "visit_service_id_snapshot", name="uq_allfree_request_line"),
        sa.ForeignKeyConstraint(["request_id", "visit_id_snapshot"], ["all_free_requests.id", "all_free_requests.visit_id_snapshot"],
                                name="fk_allfree_line_request_visit", deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["visit_service_id", "visit_id_snapshot", "service_id_snapshot"],
                                ["visit_services.id", "visit_services.visit_id", "visit_services.service_id"],
                                name="fk_allfree_line_visit_service", deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("visit_id_snapshot > 0 AND visit_service_id_snapshot > 0 AND service_id_snapshot > 0", name="ck_allfree_line_snapshot_ids"),
        sa.CheckConstraint("visit_service_id IS NULL OR visit_service_id = visit_service_id_snapshot", name="ck_allfree_line_live_snapshot"),
        sa.CheckConstraint("quantity > 0 AND quantity <= 2147483647 AND quantity = CAST(quantity AS INTEGER)", name="ck_allfree_line_quantity"),
        sa.CheckConstraint("unit_price >= 0 AND unit_price <= 9999999999.99 AND unit_price = round(unit_price, 2)", name="ck_allfree_line_unit"),
        sa.CheckConstraint("gross_amount >= 0 AND gross_amount <= 9999999999.99 AND gross_amount = round(gross_amount, 2) AND round(unit_price * quantity, 2) = gross_amount", name="ck_allfree_line_gross"),
        sa.CheckConstraint("length(trim(currency)) > 0", name="ck_allfree_line_currency"),
    )
    op.create_index("ix_allfree_lines_request", "all_free_request_lines", ["request_id"])
    op.create_table(
        "all_free_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("all_free_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_user_id_snapshot", sa.Integer()),
        sa.Column("actor_role_snapshot", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("event_type IN ('requested','approved','rejected','invalidated')", name="ck_allfree_event_type"),
        sa.CheckConstraint("actor_user_id_snapshot IS NULL OR actor_user_id_snapshot > 0", name="ck_allfree_event_actor_id"),
        sa.CheckConstraint("actor_user_id IS NULL OR (actor_user_id_snapshot IS NOT NULL AND actor_user_id = actor_user_id_snapshot)", name="ck_allfree_event_actor_snapshot"),
        sa.CheckConstraint("length(trim(actor_role_snapshot)) > 0", name="ck_allfree_event_actor_role"),
    )
    op.create_index("ix_allfree_events_request", "all_free_request_events", ["request_id"])
    if dialect == "postgresql":
        for table in ("all_free_requests", "all_free_request_lines", "all_free_request_events"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # The Alembic login can be a member of the NOLOGIN schema owner. New
        # tables and their OWNED BY sequences must belong to that owner, not
        # to the deploy login, before later SECURITY DEFINER provisioning.
        literal = schema.replace("'", "''")
        tag = "$allfree_0107_owner$"
        while tag in literal:
            tag = tag[:-1] + "_x$"
        op.execute(f"""DO {tag} DECLARE owner_name name; owner_id oid; t text; seq regclass; BEGIN
          SELECT n.nspowner,r.rolname INTO STRICT owner_id,owner_name FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{literal}';
          FOREACH t IN ARRAY ARRAY['all_free_requests','all_free_request_lines','all_free_request_events'] LOOP
            EXECUTE pg_catalog.format('ALTER TABLE %I.%I OWNER TO %I', '{literal}', t, owner_name);
            SELECT pg_catalog.pg_get_serial_sequence(pg_catalog.format('%I.%I','{literal}',t),'id')::regclass INTO seq;
            IF seq IS NULL OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c WHERE c.oid=seq AND c.relowner=owner_id)
            THEN RAISE EXCEPTION 'All-free sequence ownership mismatch'; END IF;
          END LOOP;
        END {tag}""")
        _restore_pg_schema()


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    tables = ("all_free_requests", "all_free_request_lines", "all_free_request_events")
    if dialect == "postgresql":
        _pin_pg_schema()
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE " + ", ".join(tables) + " IN ACCESS EXCLUSIVE MODE")
        op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM all_free_requests) OR EXISTS (SELECT 1 FROM all_free_request_lines)
             OR EXISTS (SELECT 1 FROM all_free_request_events)
          THEN RAISE EXCEPTION 'all-free evidence exists; downgrade refused'; END IF;
        END $$
        """)
    elif dialect == "sqlite":
        op.execute("UPDATE all_free_requests SET id=id WHERE 0")
        op.execute("CREATE TEMP TABLE _allfree_downgrade_guard (id INTEGER)")
        op.execute("""
        CREATE TEMP TRIGGER _allfree_downgrade_refuse BEFORE INSERT ON _allfree_downgrade_guard
        WHEN EXISTS (SELECT 1 FROM all_free_requests) OR EXISTS (SELECT 1 FROM all_free_request_lines)
          OR EXISTS (SELECT 1 FROM all_free_request_events)
        BEGIN SELECT RAISE(ABORT, 'all-free evidence exists; downgrade refused'); END
        """)
        op.execute("INSERT INTO _allfree_downgrade_guard VALUES (1)")
        op.execute("DROP TRIGGER _allfree_downgrade_refuse")
        op.execute("DROP TABLE _allfree_downgrade_guard")
    else:
        raise RuntimeError("Unsupported all-free request migration dialect")
    op.drop_index("ix_allfree_events_request", table_name="all_free_request_events")
    op.drop_table("all_free_request_events")
    op.drop_index("ix_allfree_lines_request", table_name="all_free_request_lines")
    op.drop_table("all_free_request_lines")
    op.drop_index("uq_allfree_active_visit", table_name="all_free_requests")
    op.drop_table("all_free_requests")
    op.drop_index("uq_visit_services_allfree_identity", table_name="visit_services")
    op.drop_index("uq_visits_allfree_identity", table_name="visits")
    op.drop_column("visits", "allfree_encounter_identity")
    if dialect == "postgresql":
        _restore_pg_schema()
