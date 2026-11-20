"""Serialize encounter membership and existing financial row writers.

This installs only the database serialization substrate. The runtime role's
complete RLS capability, provider debit reconciliation, checked re-quote and
all user-facing integrations are separate prerequisites before approval.
"""

import hashlib

from alembic import op

revision = "0118_encounter_financial_fence"
down_revision = "0117_visit_invitation_delivery"
branch_labels = None
depends_on = None


def _capability_schema_name(schema: str) -> str:
    # Immutable v1, kept in parity with 0112 and app.db.capability_namespace.
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + schema.encode("utf-8")).hexdigest()[:32]


def upgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect == "sqlite":
        _sqlite_upgrade()
        return
    if dialect != "postgresql":
        raise RuntimeError("unsupported financial fence dialect")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("trusted migration schema required")
    quoted = context.dialect.identifier_preparer.quote_schema(schema)
    private_name = _capability_schema_name(schema)
    private = context.dialect.identifier_preparer.quote_schema(private_name)
    app_literal = schema.replace("'", "''")
    private_literal = private_name.replace("'", "''")
    tag = "$financial_private$"
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
      THEN RAISE EXCEPTION 'financial private capability namespace is invalid'; END IF;
    END {tag}""")
    sequence_literal = f"{quoted}.encounter_financial_generation_seq".replace("'", "''")
    # Block old writers while choosing the counter's actual high-water mark.
    op.execute(f"LOCK TABLE {quoted}.visits, {quoted}.encounters IN ACCESS EXCLUSIVE MODE")
    op.execute(f"CREATE SEQUENCE IF NOT EXISTS {quoted}.encounter_financial_generation_seq AS bigint")
    op.execute(f"""
      SELECT 1 / CASE WHEN GREATEST(4503599627370496::bigint,
        COALESCE((SELECT MAX(generation) FROM {quoted}.encounters), 0),
        (SELECT last_value FROM {quoted}.encounter_financial_generation_seq))
        < 9223372036854775807 THEN 1 ELSE 0 END
    """)
    op.execute(f"""
      SELECT pg_catalog.setval('{sequence_literal}'::pg_catalog.regclass,
        GREATEST(4503599627370496::bigint,
          COALESCE((SELECT MAX(generation) FROM {quoted}.encounters), 0),
          (SELECT last_value FROM {quoted}.encounter_financial_generation_seq)), true)
    """)
    # A separately provisioned, NOLOGIN capability owner supplies explicit RLS
    # policies, including under FORCE RLS. Until then any incomplete visibility
    # must fail closed; ownership alone is not a FORCE-RLS bypass.
    op.execute(f"""
      CREATE OR REPLACE FUNCTION {private}.financial_encounter_generation_fence()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
      SET search_path = pg_catalog SET row_security = on AS $$
      BEGIN
        IF TG_OP = 'INSERT' THEN
          NEW.generation := pg_catalog.nextval(pg_catalog.format('%I.encounter_financial_generation_seq', TG_TABLE_SCHEMA)::pg_catalog.regclass);
        ELSIF NEW.generation IS DISTINCT FROM OLD.generation AND pg_catalog.pg_trigger_depth() <= 1 THEN
          RAISE EXCEPTION 'Encounter generation is server controlled';
        END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(f"""
      CREATE OR REPLACE FUNCTION {private}.financial_visit_membership_fence()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
      SET search_path = pg_catalog SET row_security = on AS $$
      DECLARE old_enc integer; new_enc integer; locked_count integer;
      BEGIN
        IF TG_OP = 'UPDATE' AND ROW(OLD.encounter_id, OLD.patient_id)
          IS NOT DISTINCT FROM ROW(NEW.encounter_id, NEW.patient_id) THEN RETURN NEW; END IF;
        IF TG_OP <> 'INSERT' THEN old_enc := OLD.encounter_id; END IF;
        IF TG_OP <> 'DELETE' THEN new_enc := NEW.encounter_id; END IF;
        EXECUTE pg_catalog.format('SELECT count(*) FROM (SELECT id FROM %I.encounters WHERE id IN ($1,$2) ORDER BY id FOR UPDATE NOWAIT) locked', TG_TABLE_SCHEMA)
          INTO locked_count USING old_enc, new_enc;
        IF locked_count <> (SELECT count(DISTINCT x) FROM pg_catalog.unnest(ARRAY[old_enc,new_enc]) x WHERE x IS NOT NULL) THEN
          RAISE EXCEPTION 'Encounter membership changed';
        END IF;
        EXECUTE pg_catalog.format('UPDATE %I.encounters SET generation=pg_catalog.nextval(pg_catalog.format(''%%I.encounter_financial_generation_seq'', $3)::pg_catalog.regclass) WHERE id IN ($1,$2)', TG_TABLE_SCHEMA)
          USING old_enc, new_enc, TG_TABLE_SCHEMA;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(f"""
      CREATE OR REPLACE FUNCTION {private}.financial_visit_reference_fence()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
      SET search_path = pg_catalog SET row_security = on AS $$
      DECLARE old_visit integer; new_visit integer; old_invoice integer; new_invoice integer;
              ids integer[]; locked_count integer;
      BEGIN
        IF TG_TABLE_NAME = 'payment_invoices' THEN
          EXECUTE pg_catalog.format('SELECT COALESCE(array_agg(DISTINCT visit_id ORDER BY visit_id), ARRAY[]::integer[]) FROM %I.payment_invoice_visits WHERE invoice_id=$1', TG_TABLE_SCHEMA)
            INTO ids USING OLD.id;
        ELSE
          IF TG_OP <> 'INSERT' THEN old_visit := OLD.visit_id; END IF;
          IF TG_OP <> 'DELETE' THEN new_visit := NEW.visit_id; END IF;
          SELECT COALESCE(array_agg(DISTINCT x ORDER BY x), ARRAY[]::integer[])
            INTO ids FROM pg_catalog.unnest(ARRAY[old_visit,new_visit]) x WHERE x IS NOT NULL;
        END IF;
        EXECUTE pg_catalog.format('SELECT count(*) FROM (SELECT id FROM %I.visits WHERE id = ANY($1) ORDER BY id FOR UPDATE NOWAIT) locked', TG_TABLE_SCHEMA)
          INTO locked_count USING ids;
        IF locked_count <> pg_catalog.cardinality(ids) THEN RAISE EXCEPTION 'Visit reference changed'; END IF;
        IF TG_TABLE_NAME = 'payment_invoice_visits' THEN
          IF TG_OP <> 'INSERT' THEN old_invoice := OLD.invoice_id; END IF;
          IF TG_OP <> 'DELETE' THEN new_invoice := NEW.invoice_id; END IF;
          EXECUTE pg_catalog.format('SELECT count(*) FROM (SELECT id FROM %I.payment_invoices WHERE id IN ($1,$2) ORDER BY id FOR UPDATE NOWAIT) locked', TG_TABLE_SCHEMA)
            INTO locked_count USING old_invoice, new_invoice;
          IF locked_count <> (SELECT count(DISTINCT x) FROM pg_catalog.unnest(ARRAY[old_invoice,new_invoice]) x WHERE x IS NOT NULL) THEN
            RAISE EXCEPTION 'Invoice reference changed';
          END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$
    """)
    for function in ("financial_encounter_generation_fence", "financial_visit_membership_fence", "financial_visit_reference_fence"):
        op.execute(f"REVOKE ALL ON FUNCTION {private}.{function}() FROM PUBLIC")
    _postgres_capabilities(quoted, private)
    # Alembic may authenticate as a member of the schema owner. New
    # functions must nevertheless start with the trusted schema owner, so
    # the namespace provisioner never silently adopts the login as owner.
    for signature in ("financial_encounter_generation_fence()", "financial_visit_membership_fence()",
                      "financial_visit_reference_fence()", "financial_lock_rows(text,integer[])",
                      "financial_probe_group(integer)"):
        op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{app_literal}';
          EXECUTE pg_catalog.format('ALTER FUNCTION %I.{signature} OWNER TO %I', '{private_literal}', trusted_owner);
        END {tag}""")
    op.execute(f"DROP TRIGGER IF EXISTS trg_financial_encounter_generation ON {quoted}.encounters")
    op.execute(f"CREATE TRIGGER trg_financial_encounter_generation BEFORE INSERT OR UPDATE ON {quoted}.encounters FOR EACH ROW EXECUTE FUNCTION {private}.financial_encounter_generation_fence()")
    triggers = (
        ("visits", "trg_financial_visit_membership", "INSERT OR UPDATE OR DELETE", "financial_visit_membership_fence"),
        ("payment_invoice_visits", "trg_financial_invoice_link", "INSERT OR UPDATE OR DELETE", "financial_visit_reference_fence"),
        ("payments", "trg_financial_payment", "INSERT OR UPDATE OR DELETE", "financial_visit_reference_fence"),
        ("payment_visits", "trg_financial_payment_link", "INSERT OR UPDATE OR DELETE", "financial_visit_reference_fence"),
        ("payment_invoices", "trg_financial_invoice", "UPDATE OR DELETE", "financial_visit_reference_fence"),
        ("invoices", "trg_financial_billing_invoice", "INSERT OR UPDATE OR DELETE", "financial_visit_reference_fence"),
    )
    for table, trigger, events, function in triggers:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {quoted}.{table}")
        op.execute(f"CREATE TRIGGER {trigger} AFTER {events} ON {quoted}.{table} FOR EACH ROW EXECUTE FUNCTION {private}.{function}()")


def _postgres_capabilities(schema: str, private: str) -> None:
    """Install ungranted, constrained locks/snapshots for one provisioned role."""
    encounter_regclass = f"{schema}.encounters".replace("'", "''")
    definitions = (
        ("financial_lock_rows", "kind text, ids integer[]", "integer[]", f"""
          DECLARE result integer[];
          BEGIN
            IF ids IS NULL OR pg_catalog.cardinality(ids)>1000 OR EXISTS
              (SELECT 1 FROM pg_catalog.unnest(ids) x WHERE x IS NULL OR x<=0) THEN
              RAISE EXCEPTION 'Invalid financial lock request';
            END IF;
            IF kind='visit' THEN
              SELECT ARRAY(SELECT id FROM {schema}.visits WHERE id=ANY(ids) ORDER BY id FOR UPDATE NOWAIT) INTO result;
            ELSIF kind='encounter' THEN
              SELECT ARRAY(SELECT id FROM {schema}.encounters WHERE id=ANY(ids) ORDER BY id FOR UPDATE NOWAIT) INTO result;
            ELSIF kind='invoice' THEN
              SELECT ARRAY(SELECT id FROM {schema}.payment_invoices WHERE id=ANY(ids) ORDER BY id FOR UPDATE NOWAIT) INTO result;
            ELSE RAISE EXCEPTION 'Invalid financial lock kind'; END IF;
            RETURN result;
          END
        """),
        ("financial_probe_group", "encounter_id_input integer", "jsonb", f"""
          DECLARE members integer[]; lines integer[]; invoices integer[]; links integer[];
                  pending integer[]; history boolean; policy_safe boolean; triggers_safe boolean;
          BEGIN
            IF encounter_id_input IS NULL OR encounter_id_input<=0 THEN RAISE EXCEPTION 'Invalid encounter'; END IF;
            LOCK TABLE {schema}.visits, {schema}.encounters, {schema}.visit_services,
              {schema}.payment_invoices, {schema}.payment_invoice_visits, {schema}.payments,
              {schema}.payment_visits, {schema}.payment_webhooks, {schema}.payment_transactions,
              {schema}.invoices, {schema}.provider_active_visit_reservations,
              {schema}.provider_attempt_visits, {schema}.provider_reconciliation_events,
              {schema}.all_free_requests IN ACCESS SHARE MODE;
            -- A role-visible policy is required for every RLS table. An extra
            -- restrictive policy or a removed policy is a closed failure.
            SELECT count(*)=14 AND COALESCE(bool_and(NOT c.relrowsecurity OR (
              EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
                WHERE p.polrelid=c.oid AND p.polpermissive AND p.polcmd IN ('r','*')
                  AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
                  AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
                WHERE p.polrelid=c.oid AND NOT p.polpermissive AND p.polcmd IN ('r','*')
                  AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) role_id
                    WHERE CASE WHEN role_id=0 THEN true ELSE pg_catalog.pg_has_role(CURRENT_USER,role_id,'MEMBER') END))
            )),false) INTO policy_safe
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.oid=(SELECT relnamespace FROM pg_catalog.pg_class
                         WHERE oid='{encounter_regclass}'::pg_catalog.regclass)
              AND c.relname IN ('visits','encounters','visit_services','payment_invoices',
                'payment_invoice_visits','payments','payment_visits','payment_webhooks','payment_transactions',
                'invoices','provider_active_visit_reservations','provider_attempt_visits',
                'provider_reconciliation_events','all_free_requests');
            IF policy_safe IS NOT TRUE THEN RAISE EXCEPTION 'Incomplete financial capability visibility'; END IF;
            SELECT count(*)=7 AND COALESCE(bool_and(t.tgenabled IN ('O','A')
              AND NOT t.tgisinternal AND t.tgqual IS NULL AND t.tgattr::text=''
              AND t.tgtype=expected.trigger_type AND p.proname=expected.function_name
              AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)
              AND p.prosecdef AND pg_catalog.cardinality(p.proconfig)=2
              AND 'search_path=pg_catalog'=ANY(p.proconfig) AND 'row_security=on'=ANY(p.proconfig)
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE')),false) INTO triggers_safe
            FROM (VALUES
              ('encounters','trg_financial_encounter_generation',23,'financial_encounter_generation_fence'),
              ('visits','trg_financial_visit_membership',29,'financial_visit_membership_fence'),
              ('payment_invoice_visits','trg_financial_invoice_link',29,'financial_visit_reference_fence'),
              ('payments','trg_financial_payment',29,'financial_visit_reference_fence'),
              ('payment_visits','trg_financial_payment_link',29,'financial_visit_reference_fence'),
              ('payment_invoices','trg_financial_invoice',25,'financial_visit_reference_fence'),
              ('invoices','trg_financial_billing_invoice',29,'financial_visit_reference_fence')
            ) AS expected(table_name, trigger_name, trigger_type, function_name)
            JOIN pg_catalog.pg_class c ON c.relnamespace=(SELECT relnamespace FROM pg_catalog.pg_class
                  WHERE oid='{encounter_regclass}'::pg_catalog.regclass) AND c.relname=expected.table_name
            JOIN pg_catalog.pg_trigger t ON t.tgrelid=c.oid AND t.tgname=expected.trigger_name
            JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid;
            IF triggers_safe IS NOT TRUE OR pg_catalog.current_setting('session_replication_role')<>'origin' THEN
              RAISE EXCEPTION 'Financial writer fence is unavailable';
            END IF;
            SELECT ARRAY(SELECT id FROM {schema}.visits WHERE encounter_id=encounter_id_input ORDER BY id) INTO members;
            SELECT ARRAY(SELECT id FROM {schema}.visit_services WHERE visit_id=ANY(members) ORDER BY id) INTO lines;
            SELECT ARRAY(SELECT DISTINCT invoice_id FROM {schema}.payment_invoice_visits WHERE visit_id=ANY(members) ORDER BY invoice_id) INTO invoices;
            SELECT ARRAY(SELECT id FROM {schema}.payment_invoice_visits WHERE invoice_id=ANY(invoices) ORDER BY id) INTO links;
            PERFORM id FROM {schema}.all_free_requests WHERE visit_id=ANY(members) AND status='pending' ORDER BY id FOR UPDATE NOWAIT;
            SELECT ARRAY(SELECT id FROM {schema}.all_free_requests WHERE visit_id=ANY(members) AND status='pending' ORDER BY id) INTO pending;
            SELECT EXISTS (SELECT 1 FROM {schema}.payments p WHERE p.visit_id=ANY(members)
                OR EXISTS (SELECT 1 FROM {schema}.payment_visits pv WHERE pv.payment_id=p.id AND pv.visit_id=ANY(members)))
              OR EXISTS (SELECT 1 FROM {schema}.payment_webhooks WHERE visit_id=ANY(members))
              OR EXISTS (SELECT 1 FROM {schema}.payment_transactions WHERE visit_id=ANY(members))
              OR EXISTS (SELECT 1 FROM {schema}.invoices WHERE visit_id=ANY(members))
              OR EXISTS (SELECT 1 FROM {schema}.provider_active_visit_reservations WHERE visit_id=ANY(members))
              OR EXISTS (SELECT 1 FROM {schema}.provider_attempt_visits WHERE visit_id_snapshot=ANY(members))
              OR EXISTS (SELECT 1 FROM {schema}.provider_reconciliation_events r
                WHERE r.invoice_id_snapshot=ANY(invoices) OR r.target_kind='unmatched') INTO history;
            RETURN pg_catalog.jsonb_build_object('members',members,'lines',lines,'invoices',invoices,
                                                  'links',links,'pending',pending,'history',history);
          END
        """),
    )
    for name, arguments, result, body in definitions:
        # Quoted SQL identifiers can themselves contain dollar-quote tokens.
        suffix = 0
        delimiter = "$financial_capability$"
        while delimiter in body:
            suffix += 1
            delimiter = f"$financial_capability_{suffix}$"
        op.execute(f"""CREATE OR REPLACE FUNCTION {private}.{name}({arguments}) RETURNS {result}
          LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on
          AS {delimiter}{body}{delimiter}""")
        signature = "text, integer[]" if name == "financial_lock_rows" else "integer"
        op.execute(f"REVOKE ALL ON FUNCTION {private}.{name}({signature}) FROM PUBLIC")


def _sqlite_upgrade() -> None:
    # SQLite's writer reservation serializes all mutations once the caller
    # reserves it before reading. Keep the counter even across downgrades.
    op.execute("CREATE TABLE IF NOT EXISTS encounter_financial_generation_clock (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(typeof(value)='integer' AND value>=4503599627370496))")
    op.execute("INSERT INTO encounter_financial_generation_clock (id,value) SELECT 1, MAX(4503599627370496, COALESCE((SELECT MAX(generation) FROM encounters), 0)) WHERE NOT EXISTS (SELECT 1 FROM encounter_financial_generation_clock)")
    op.execute("CREATE TEMP TABLE financial_clock_upgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
    op.execute("INSERT INTO financial_clock_upgrade_guard SELECT CASE WHEN value < 9223372036854775807 AND value >= COALESCE((SELECT MAX(generation) FROM encounters),0) THEN 1 ELSE 0 END FROM encounter_financial_generation_clock WHERE id=1")
    op.execute("DROP TABLE financial_clock_upgrade_guard")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_financial_clock_no_delete BEFORE DELETE ON encounter_financial_generation_clock BEGIN SELECT RAISE(ABORT, 'financial clock is persistent'); END")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_financial_clock_no_insert BEFORE INSERT ON encounter_financial_generation_clock WHEN EXISTS (SELECT 1 FROM encounter_financial_generation_clock) BEGIN SELECT RAISE(ABORT, 'financial clock is persistent'); END")
    op.execute("CREATE TRIGGER IF NOT EXISTS trg_financial_clock_monotonic BEFORE UPDATE ON encounter_financial_generation_clock WHEN NEW.id IS NOT OLD.id OR typeof(NEW.value)<>'integer' OR OLD.value>=9223372036854775807 OR NEW.value<>OLD.value+1 BEGIN SELECT RAISE(ABORT, 'invalid financial clock'); END")
    op.execute("DROP TRIGGER IF EXISTS trg_financial_encounter_generation_insert")
    op.execute("""
      CREATE TRIGGER trg_financial_encounter_generation_insert AFTER INSERT ON encounters BEGIN
        UPDATE encounter_financial_generation_clock SET value=value+1 WHERE id=1;
        UPDATE encounters SET generation=(SELECT value FROM encounter_financial_generation_clock WHERE id=1) WHERE id=NEW.id;
      END
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_financial_encounter_generation_update")
    op.execute("""
      CREATE TRIGGER trg_financial_encounter_generation_update BEFORE UPDATE OF generation ON encounters
      WHEN typeof(NEW.generation)<>'integer' OR (NEW.generation<>OLD.generation
        AND (NEW.generation<=OLD.generation OR NEW.generation<>(SELECT value FROM encounter_financial_generation_clock WHERE id=1)))
      BEGIN SELECT RAISE(ABORT, 'invalid encounter generation'); END
    """)
    for event, ids, condition in (
        ("insert", "NEW.encounter_id", "NEW.encounter_id IS NOT NULL"),
        ("delete", "OLD.encounter_id", "OLD.encounter_id IS NOT NULL"),
        ("update", "OLD.encounter_id, NEW.encounter_id", "OLD.encounter_id IS NOT NEW.encounter_id OR OLD.patient_id IS NOT NEW.patient_id"),
    ):
        name = f"trg_financial_visit_membership_{event}"
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
        op.execute(f"""
          CREATE TRIGGER {name} AFTER {event.upper()} ON visits WHEN {condition} BEGIN
            UPDATE encounter_financial_generation_clock SET value=value+1 WHERE id=1;
            UPDATE encounters SET generation=(SELECT value FROM encounter_financial_generation_clock WHERE id=1) WHERE id IN ({ids});
          END
        """)


def downgrade() -> None:
    # Never restore a weaker fence or reset the generation allocator while
    # its capabilities could remain live. Refuse before Alembic lowers its
    # revision while the 0118 objects still exist.
    raise RuntimeError("Encounter financial fence requires an audited rollback")
