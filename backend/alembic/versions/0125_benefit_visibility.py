"""Evidence for every encounter Visit and atomic benefit quote visibility.

Existing applications without the newly required per-Visit evidence remain
unresolved; this migration never invents their group or their clinical epochs.
No benefit is authorized by this schema or its read capability.
"""
import hashlib

import sqlalchemy as sa

from alembic import op

revision = "0125_benefit_visibility"
down_revision = "0124_telegram_ownership"
branch_labels = None
depends_on = None


def _capability_schema_name(schema: str) -> str:
    # Immutable v1, kept in parity with 0112 and app.db.capability_namespace.
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + schema.encode("utf-8")).hexdigest()[:32]


def upgrade() -> None:
    op.create_index("uq_enc_benefit_app_identity", "encounter_benefit_applications", ["id", "encounter_id", "patient_id"], unique=True)
    op.create_table(
        "encounter_benefit_visit_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("encounter_benefit_applications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("visit_id", sa.Integer, sa.ForeignKey("visits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("encounter_id", sa.Integer, nullable=True),
        sa.Column("patient_id", sa.Integer, nullable=True),
        sa.Column("visit_id_snapshot", sa.Integer, nullable=False),
        sa.Column("visit_context_epoch", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("application_id", "visit_id_snapshot", name="uq_enc_benefit_visit_snapshot"),
        sa.ForeignKeyConstraint(["application_id", "encounter_id", "patient_id"],
            ["encounter_benefit_applications.id", "encounter_benefit_applications.encounter_id", "encounter_benefit_applications.patient_id"],
            name="fk_enc_benefit_visit_application_identity", onupdate="CASCADE", deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["visit_id", "patient_id", "encounter_id"],
            ["visits.id", "visits.patient_id", "visits.encounter_id"],
            name="fk_enc_benefit_visit_live_identity", deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("visit_id_snapshot > 0 AND visit_context_epoch > 0", name="ck_enc_benefit_visit_context"),
        sa.CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_enc_benefit_visit_live_snapshot"),
        sa.CheckConstraint("visit_id IS NULL OR (encounter_id IS NOT NULL AND patient_id IS NOT NULL)", name="ck_enc_benefit_visit_identity_present"),
    )
    op.create_index("ix_encounter_benefit_visit_snapshots_application_id", "encounter_benefit_visit_snapshots", ["application_id"])
    context = op.get_context()
    if context.dialect.name == "sqlite":
        op.execute("""
          CREATE TRIGGER trg_benefit_visit_evidence_update BEFORE UPDATE ON encounter_benefit_visit_snapshots
          WHEN NEW.application_id IS NOT OLD.application_id OR NEW.visit_id_snapshot IS NOT OLD.visit_id_snapshot
            OR NEW.visit_context_epoch IS NOT OLD.visit_context_epoch OR NEW.encounter_id IS NOT OLD.encounter_id
            OR (NEW.visit_id IS NOT OLD.visit_id AND NOT (OLD.visit_id IS NOT NULL AND NEW.visit_id IS NULL))
            OR (NEW.patient_id IS NOT OLD.patient_id AND NOT (OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL AND NEW.visit_id IS NULL))
          BEGIN SELECT RAISE(ABORT, 'benefit visit evidence is immutable'); END
        """)
        op.execute("CREATE TRIGGER trg_benefit_visit_evidence_delete BEFORE DELETE ON encounter_benefit_visit_snapshots BEGIN SELECT RAISE(ABORT, 'benefit visit evidence is immutable'); END")
        return
    if context.dialect.name != "postgresql":
        raise RuntimeError("unsupported benefit visibility dialect")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("trusted migration schema required")
    quoted = context.dialect.identifier_preparer.quote_schema(schema)
    private_name = _capability_schema_name(schema)
    private = context.dialect.identifier_preparer.quote_schema(private_name)
    app_literal = schema.replace("'", "''")
    private_literal = private_name.replace("'", "''")
    tag = "$benefit_private$"
    while tag in app_literal:
        tag = tag[:-1] + "_x$"
    op.execute(f"""DO {tag} DECLARE app_owner oid; private_oid oid; BEGIN
      SELECT nspowner INTO STRICT app_owner FROM pg_catalog.pg_namespace WHERE nspname='{app_literal}';
      SELECT oid INTO STRICT private_oid FROM pg_catalog.pg_namespace
        WHERE nspname='{private_literal}' AND nspowner=app_owner;
      IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
          LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
          WHERE n.oid=private_oid AND a.privilege_type='CREATE' AND a.grantee<>app_owner)
        OR (SELECT count(*) FROM {private}.clinic_capability_namespace)<>1
        OR NOT EXISTS (SELECT 1 FROM {private}.clinic_capability_namespace
          WHERE id=1 AND format_version=1 AND application_schema='{app_literal}' AND private_schema='{private_literal}')
      THEN RAISE EXCEPTION 'benefit private capability namespace is invalid'; END IF;
    END {tag}""")
    op.execute(f"ALTER TABLE {quoted}.encounter_benefit_visit_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
      CREATE FUNCTION {quoted}.protect_benefit_visit_evidence() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'benefit visit evidence is immutable'; END IF;
        IF ROW(NEW.application_id, NEW.visit_id_snapshot, NEW.visit_context_epoch, NEW.encounter_id)
          IS DISTINCT FROM ROW(OLD.application_id, OLD.visit_id_snapshot, OLD.visit_context_epoch, OLD.encounter_id)
          OR (NEW.visit_id IS DISTINCT FROM OLD.visit_id AND NOT (OLD.visit_id IS NOT NULL AND NEW.visit_id IS NULL AND pg_catalog.pg_trigger_depth()>1))
          OR (NEW.patient_id IS DISTINCT FROM OLD.patient_id AND NOT (OLD.patient_id IS NOT NULL AND NEW.patient_id IS NULL AND NEW.visit_id IS NULL AND pg_catalog.pg_trigger_depth()>1)) THEN
          RAISE EXCEPTION 'benefit visit evidence is immutable';
        END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(f"CREATE TRIGGER trg_benefit_visit_evidence BEFORE UPDATE OR DELETE ON {quoted}.encounter_benefit_visit_snapshots FOR EACH ROW EXECUTE FUNCTION {quoted}.protect_benefit_visit_evidence()")
    _create_quote_function(quoted, private)
    op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
      SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{app_literal}';
      EXECUTE pg_catalog.format('ALTER FUNCTION %I.encounter_benefit_quote(integer) OWNER TO %I',
        '{private_literal}', trusted_owner);
    END {tag}""")


def _create_quote_function(schema: str, private: str) -> None:
    """One SQL STABLE statement => one MVCC snapshot for all inputs."""
    encounter_regclass = f"{schema}.encounters".replace("'", "''")
    body = f"""
      WITH selected AS (
        SELECT id,patient_id,encounter_id FROM {schema}.visits WHERE id=target_visit
      ), members AS (
        SELECT v.id,v.patient_id,v.encounter_id,v.confirmation_context_epoch
        FROM {schema}.visits v CROSS JOIN selected s
        WHERE (s.encounter_id IS NULL AND v.id=s.id) OR (s.encounter_id IS NOT NULL AND v.encounter_id=s.encounter_id)
      ), apps AS (
        SELECT a.* FROM {schema}.encounter_benefit_applications a JOIN selected s ON a.encounter_id=s.encounter_id
      ), policy_check AS (
        SELECT count(*)=8 AND COALESCE(bool_and(NOT c.relrowsecurity OR (
          EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid AND p.polpermissive AND p.polcmd IN ('r','*')
            AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
            AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid AND NOT p.polpermissive AND p.polcmd IN ('r','*')
            AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) rid WHERE CASE WHEN rid=0 THEN true ELSE pg_catalog.pg_has_role(CURRENT_USER,rid,'MEMBER') END))
        )),false) AS ok
        FROM pg_catalog.pg_class c WHERE c.relnamespace=(SELECT relnamespace FROM pg_catalog.pg_class
          WHERE oid='{encounter_regclass}'::pg_catalog.regclass)
        AND c.relname IN ('visits','encounters','visit_services','encounter_benefit_applications',
                          'encounter_benefit_allocations','encounter_benefit_events','encounter_benefit_visit_snapshots','all_free_requests')
      ), trigger_check AS (
        SELECT count(*)=3 AND COALESCE(bool_and(t.tgenabled IN ('O','A') AND NOT t.tgisinternal
          AND t.tgqual IS NULL AND t.tgattr::text='' AND t.tgtype=expected.trigger_type
          AND p.proname=expected.function_name AND 'search_path=pg_catalog'=ANY(p.proconfig)),false)
          AND pg_catalog.current_setting('session_replication_role')='origin' AS ok
        FROM (VALUES
          ('visits','trg_visit_confirmation_context',23,'invalidate_visit_confirmation_context'),
          ('visit_services','trg_visit_service_confirmation_context',29,'invalidate_visit_service_confirmation'),
          ('visits','trg_financial_visit_membership',29,'financial_visit_membership_fence')
        ) expected(table_name, trigger_name, trigger_type, function_name)
        JOIN pg_catalog.pg_class c ON c.relnamespace=(SELECT relnamespace FROM pg_catalog.pg_class
          WHERE oid='{encounter_regclass}'::pg_catalog.regclass) AND c.relname=expected.table_name
        JOIN pg_catalog.pg_trigger t ON t.tgrelid=c.oid AND t.tgname=expected.trigger_name
        JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
      )
      SELECT pg_catalog.jsonb_build_object(
        'visible', (SELECT ok FROM policy_check) AND (SELECT ok FROM trigger_check),
        'selected', (SELECT pg_catalog.jsonb_build_object('id',id,'patient',patient_id,'encounter',encounter_id) FROM selected),
        'encounter', (SELECT pg_catalog.jsonb_build_object('id',e.id,'patient',e.patient_id,'generation',e.generation,'provenance',e.provenance)
                      FROM {schema}.encounters e JOIN selected s ON e.id=s.encounter_id),
        'visits', COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('id',id,'patient',patient_id,'encounter',encounter_id,'epoch',confirmation_context_epoch) ORDER BY id) FROM members), '[]'::jsonb),
        'lines', COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('id',v.id,'visit',v.visit_id,'service',v.service_id,'qty',v.qty,'price',v.price::text,'currency',v.currency) ORDER BY v.id)
                          FROM {schema}.visit_services v WHERE v.visit_id IN (SELECT id FROM members)), '[]'::jsonb),
        'applications', COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('id',id,'encounter',encounter_id,'patient',patient_id,'generation',encounter_generation,'gross',gross_total::text,'discount',benefit_total::text,'net',net_total::text) ORDER BY id) FROM apps), '[]'::jsonb),
        'snapshots', COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('app',s.application_id,'visit',s.visit_id,'visit_snapshot',s.visit_id_snapshot,'patient',s.patient_id,'encounter',s.encounter_id,'epoch',s.visit_context_epoch) ORDER BY s.id)
                               FROM {schema}.encounter_benefit_visit_snapshots s WHERE s.application_id IN (SELECT id FROM apps)), '[]'::jsonb),
        'allocations', COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('app',a.application_id,'visit',a.visit_id,'visit_snapshot',a.visit_id_snapshot,'line',a.visit_service_id,'line_snapshot',a.visit_service_id_snapshot,'service',a.service_id_snapshot,'epoch',a.visit_context_epoch,'qty',a.quantity,'unit',a.unit_price::text,'gross',a.gross_amount::text,'discount',a.benefit_amount::text,'net',a.net_amount::text) ORDER BY a.id)
                                 FROM {schema}.encounter_benefit_allocations a WHERE a.application_id IN (SELECT id FROM apps)), '[]'::jsonb),
        'events', COALESCE((SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('app',e.application_id,'kind',e.event_type) ORDER BY e.id)
                            FROM {schema}.encounter_benefit_events e WHERE e.application_id IN (SELECT id FROM apps)), '[]'::jsonb),
        'approved_all_free', COALESCE((SELECT pg_catalog.jsonb_agg(r.id ORDER BY r.id) FROM {schema}.all_free_requests r
                                      WHERE r.visit_id IN (SELECT id FROM members) AND r.status='approved'), '[]'::jsonb)
      )
    """
    delimiter = "$benefit_quote$"
    suffix = 0
    while delimiter in body:
        suffix += 1
        delimiter = f"$benefit_quote_{suffix}$"
    op.execute(f"""CREATE FUNCTION {private}.encounter_benefit_quote(target_visit integer) RETURNS jsonb
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog SET row_security=on
      AS {delimiter}{body}{delimiter}""")
    op.execute(f"REVOKE ALL ON FUNCTION {private}.encounter_benefit_quote(integer) FROM PUBLIC")


def downgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        op.execute("SET LOCAL row_security=off")
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        quoted = context.dialect.identifier_preparer.quote_schema(schema)
        private = context.dialect.identifier_preparer.quote_schema(_capability_schema_name(schema))
        delimiter = "$benefit_downgrade$"
        while delimiter in quoted:
            delimiter = delimiter[:-1] + "_x$"
        op.execute(f"LOCK TABLE {quoted}.encounter_benefit_visit_snapshots IN ACCESS EXCLUSIVE MODE")
        op.execute(f"DO {delimiter} BEGIN IF EXISTS (SELECT 1 FROM {quoted}.encounter_benefit_visit_snapshots) THEN RAISE EXCEPTION 'benefit visit evidence prevents downgrade'; END IF; END {delimiter}")
        op.execute(f"DROP FUNCTION {private}.encounter_benefit_quote(integer)")
        op.execute(f"DROP TRIGGER trg_benefit_visit_evidence ON {quoted}.encounter_benefit_visit_snapshots")
        op.execute(f"DROP FUNCTION {quoted}.protect_benefit_visit_evidence()")
    elif context.dialect.name == "sqlite":
        op.execute("CREATE TEMP TABLE _benefit_visit_downgrade_guard (value INTEGER CHECK(value=1))")
        op.execute("INSERT INTO _benefit_visit_downgrade_guard SELECT CASE WHEN EXISTS (SELECT 1 FROM encounter_benefit_visit_snapshots) THEN 0 ELSE 1 END")
        op.execute("DROP TABLE _benefit_visit_downgrade_guard")
        op.execute("DROP TRIGGER trg_benefit_visit_evidence_delete")
        op.execute("DROP TRIGGER trg_benefit_visit_evidence_update")
    else:
        raise RuntimeError("unsupported benefit visibility dialect")
    op.drop_index("ix_encounter_benefit_visit_snapshots_application_id", table_name="encounter_benefit_visit_snapshots")
    op.drop_table("encounter_benefit_visit_snapshots")
    op.drop_index("uq_enc_benefit_app_identity", table_name="encounter_benefit_applications")
