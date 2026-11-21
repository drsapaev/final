"""Add a restricted, read-only pending all-free visibility capability.

PostgreSQL grants no PUBLIC access. An operator must grant EXECUTE to the
specific application role after reviewing schema ownership and privileges.
This function cannot authorize a discount or provide request details.
"""
from alembic import op

revision = "0114_all_free_visibility"
down_revision = "0113_subject_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported all-free visibility migration dialect")
    # The migration's trusted current_schema is embedded as a SQL identifier
    # using PostgreSQL format(%I), not a caller-controlled runtime search path.
    op.execute("""
    DO $migration$
    DECLARE target_schema text := current_schema();
            private_schema text;
            namespace_ok boolean;
            trusted_owner name;
            trusted_owner_id oid;
            original_path text := current_setting('search_path');
            template_digest text;
            template_count integer;
    BEGIN
      IF target_schema IS NULL OR target_schema IN ('pg_catalog', 'information_schema') THEN
        RAISE EXCEPTION 'A trusted application schema is required';
      END IF;
      -- Frozen namespace v1, created by 0112. The private function body still
      -- references the application tables by fully qualified identifiers.
      private_schema := 'clinic_internal_' || pg_catalog.substr(pg_catalog.encode(
        pg_catalog.sha256(pg_catalog.convert_to('clinic-capability-schema-v1','UTF8') ||
          pg_catalog.decode('00','hex') || pg_catalog.convert_to(target_schema,'UTF8')), 'hex'),1,32);
      SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace a JOIN pg_catalog.pg_namespace p ON p.nspname=private_schema
        JOIN pg_catalog.pg_roles owner ON owner.oid=a.nspowner
        WHERE a.nspname=target_schema AND p.nspowner=a.nspowner
          AND (owner.rolsuper OR NOT owner.rolcanlogin)
          AND pg_catalog.pg_has_role(CURRENT_USER,a.nspowner,'USAGE')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(a.nspacl,pg_catalog.acldefault('n',a.nspowner))) x
            WHERE x.privilege_type='CREATE' AND x.grantee<>a.nspowner)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.nspacl,pg_catalog.acldefault('n',p.nspowner))) x
            WHERE x.privilege_type='CREATE' AND x.grantee<>p.nspowner)) INTO namespace_ok;
      IF namespace_ok IS NOT TRUE THEN RAISE EXCEPTION 'Capability namespace unavailable'; END IF;
      SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=private_schema AND c.relname='clinic_capability_namespace' AND c.relkind='r'
          AND c.relowner=n.nspowner
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x WHERE x.grantee<>c.relowner)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=c.oid AND a.attacl IS NOT NULL)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal)) INTO namespace_ok;
      IF namespace_ok IS NOT TRUE THEN RAISE EXCEPTION 'Capability marker unavailable'; END IF;
      EXECUTE pg_catalog.format('SELECT count(*)=1 AND bool_and(id=1 AND format_version=1 AND application_schema=%L AND private_schema=%L) FROM %I.clinic_capability_namespace',
        target_schema,private_schema,private_schema) INTO namespace_ok;
      IF namespace_ok IS NOT TRUE THEN RAISE EXCEPTION 'Capability namespace identity mismatch'; END IF;
      SELECT n.nspowner,r.rolname INTO STRICT trusted_owner_id,trusted_owner FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname=target_schema;
      SELECT count(*)=3 AND COALESCE(bool_and(c.relowner=trusted_owner_id AND c.relrowsecurity),false)
        INTO namespace_ok FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=target_schema AND c.relname IN ('all_free_requests','all_free_request_lines','all_free_request_events');
      IF namespace_ok IS NOT TRUE THEN RAISE EXCEPTION 'All-free table ownership mismatch'; END IF;
      EXECUTE format($ddl$
        CREATE FUNCTION %2$I.all_free_pending_exists(p_visit_id integer)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog SET row_security = on AS $body$
        DECLARE pending boolean;
        BEGIN
          IF p_visit_id IS NULL OR p_visit_id <= 0 THEN
            RAISE EXCEPTION 'Invalid visit identifier';
          END IF;
          -- Stabilize RLS/table identity for the duration of the caller's tx.
          LOCK TABLE %1$I.all_free_requests IN ACCESS SHARE MODE;
          SELECT EXISTS (
            SELECT 1 FROM %1$I.all_free_requests r
            WHERE r.visit_id = p_visit_id AND r.status = 'pending'
          ) INTO pending;
          RETURN pending;
        END;
        $body$
      $ddl$, target_schema, private_schema);
      EXECUTE format('REVOKE ALL ON FUNCTION %I.all_free_pending_exists(integer) FROM PUBLIC', private_schema);
      EXECUTE format('ALTER FUNCTION %I.all_free_pending_exists(integer) OWNER TO %I', private_schema, trusted_owner);
      -- Owner-only templates provide a canonical predicate. The trusted
      -- operator can provision matching policies for one explicit backend
      -- role; no runtime role is guessed or granted here.
      EXECUTE format('CREATE POLICY allfree_template_select ON %I.all_free_requests FOR SELECT TO %I USING (true)', target_schema, trusted_owner);
      EXECUTE format($policy$
        CREATE POLICY allfree_template_insert ON %1$I.all_free_requests FOR INSERT TO %2$I
        WITH CHECK (
          status='pending' AND visit_id IS NOT NULL AND patient_id IS NOT NULL
          AND encounter_id IS NOT NULL AND requested_by_user_id IS NOT NULL
          AND decision_kind IS NULL AND decision_context_epoch IS NULL
          AND decided_by_user_id IS NULL AND decided_by_user_id_snapshot IS NULL
          AND decided_by_role_snapshot IS NULL AND decided_at IS NULL
        )
      $policy$, target_schema, trusted_owner);
      EXECUTE format('CREATE POLICY allfree_template_select ON %I.all_free_request_lines FOR SELECT TO %I USING (true)', target_schema, trusted_owner);
      EXECUTE format($policy$
        CREATE POLICY allfree_template_insert ON %1$I.all_free_request_lines FOR INSERT TO %2$I
        WITH CHECK (EXISTS (
          SELECT 1 FROM %1$I.all_free_requests r
          JOIN %1$I.visit_services vs ON vs.id=all_free_request_lines.visit_service_id
          WHERE r.id=all_free_request_lines.request_id AND r.status='pending'
            AND r.visit_id=vs.visit_id AND r.visit_id_snapshot=all_free_request_lines.visit_id_snapshot
            AND vs.service_id=all_free_request_lines.service_id_snapshot
            AND vs.qty=all_free_request_lines.quantity AND vs.price=all_free_request_lines.unit_price
            AND vs.currency=all_free_request_lines.currency
        ))
      $policy$, target_schema, trusted_owner);
      EXECUTE format('CREATE POLICY allfree_template_select ON %I.all_free_request_events FOR SELECT TO %I USING (true)', target_schema, trusted_owner);
      EXECUTE format($policy$
        CREATE POLICY allfree_template_insert ON %1$I.all_free_request_events FOR INSERT TO %2$I
        WITH CHECK (event_type='requested' AND EXISTS (
          SELECT 1 FROM %1$I.all_free_requests r
          WHERE r.id=all_free_request_events.request_id AND r.status='pending'
            AND r.requested_by_user_id=all_free_request_events.actor_user_id
            AND r.requested_by_user_id_snapshot=all_free_request_events.actor_user_id_snapshot
            AND r.requested_by_role_snapshot=all_free_request_events.actor_role_snapshot
        ))
      $policy$, target_schema, trusted_owner);
      -- Pin the exact six server-deparsed owner templates in the function
      -- body. Compute under the same pg_catalog-only path the function uses.
      PERFORM pg_catalog.set_config('search_path','pg_catalog',true);
      SELECT count(*), pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.string_agg(
        pg_catalog.concat_ws('|', c.relname, p.polname, p.polcmd::text,
          p.polpermissive::text, p.polroles::text,
          COALESCE(pg_catalog.pg_get_expr(p.polqual,p.polrelid),'<null>'),
          COALESCE(pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid),'<null>')),
        E'\\n' ORDER BY c.relname,p.polname), 'UTF8')), 'hex')
      INTO template_count, template_digest
      FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname=target_schema
        AND c.relname IN ('all_free_requests','all_free_request_lines','all_free_request_events')
        AND p.polname IN ('allfree_template_select','allfree_template_insert');
      PERFORM pg_catalog.set_config('search_path',original_path,true);
      IF template_count <> 6 OR template_digest IS NULL THEN
        RAISE EXCEPTION 'All-free policy templates incomplete';
      END IF;
      EXECUTE format($ddl$
        CREATE OR REPLACE FUNCTION %4$I.all_free_pending_exists(p_visit_id integer)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog SET row_security = on AS $body$
        DECLARE pending boolean; actual_digest text; actual_count integer; visibility_ok boolean;
        BEGIN
          IF p_visit_id IS NULL OR p_visit_id <= 0 THEN
            RAISE EXCEPTION 'Invalid visit identifier';
          END IF;
          LOCK TABLE %1$I.all_free_requests, %1$I.all_free_request_lines,
                     %1$I.all_free_request_events IN ACCESS SHARE MODE;
          SELECT count(*), pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.string_agg(
            pg_catalog.concat_ws('|', c.relname, p.polname, p.polcmd::text,
              p.polpermissive::text, p.polroles::text,
              COALESCE(pg_catalog.pg_get_expr(p.polqual,p.polrelid),'<null>'),
              COALESCE(pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid),'<null>')),
            E'\\n' ORDER BY c.relname,p.polname), 'UTF8')), 'hex')
          INTO actual_count, actual_digest
          FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
          JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname=%2$L
            AND c.relname IN ('all_free_requests','all_free_request_lines','all_free_request_events')
            AND p.polname IN ('allfree_template_select','allfree_template_insert');
          IF actual_count <> 6 OR actual_digest IS DISTINCT FROM %3$L THEN
            RAISE EXCEPTION 'All-free policy templates changed';
          END IF;
          -- FORCE RLS applies to a non-bypass owner. Verify an unconditional
          -- applicable SELECT policy and exclude restrictive policies before
          -- interpreting an absent row as permission to proceed.
          SELECT count(*)=3 AND COALESCE(bool_and(c.relrowsecurity AND EXISTS (
            SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid AND p.polpermissive
              AND p.polcmd IN ('r','*') AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true'
              AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) rid
                WHERE CASE WHEN rid=0 THEN true ELSE pg_catalog.pg_has_role(CURRENT_USER,rid,'MEMBER') END)
          ) AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid AND NOT p.polpermissive
              AND p.polcmd IN ('r','*') AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) rid
                WHERE CASE WHEN rid=0 THEN true ELSE pg_catalog.pg_has_role(CURRENT_USER,rid,'MEMBER') END)
          )),false) INTO visibility_ok FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname=%2$L AND c.relname IN ('all_free_requests','all_free_request_lines','all_free_request_events');
          IF visibility_ok IS NOT TRUE THEN RAISE EXCEPTION 'Incomplete all-free visibility'; END IF;
          SELECT EXISTS (
            SELECT 1 FROM %1$I.all_free_requests r
            WHERE r.visit_id = p_visit_id AND r.status = 'pending'
          ) INTO pending;
          RETURN pending;
        END;
        $body$
      $ddl$, target_schema, target_schema, template_digest, private_schema);
    END
    $migration$
    """)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported all-free visibility migration dialect")
    op.execute("""
    DO $migration$
    DECLARE target_schema text := current_schema(); private_schema text; namespace_ok boolean;
    BEGIN
      IF target_schema IS NULL OR target_schema IN ('pg_catalog', 'information_schema') THEN
        RAISE EXCEPTION 'A trusted application schema is required';
      END IF;
      private_schema := 'clinic_internal_' || pg_catalog.substr(pg_catalog.encode(
        pg_catalog.sha256(pg_catalog.convert_to('clinic-capability-schema-v1','UTF8') ||
          pg_catalog.decode('00','hex') || pg_catalog.convert_to(target_schema,'UTF8')), 'hex'),1,32);
      SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace a JOIN pg_catalog.pg_namespace p ON p.nspname=private_schema
        JOIN pg_catalog.pg_roles owner ON owner.oid=a.nspowner
        WHERE a.nspname=target_schema AND p.nspowner=a.nspowner AND (owner.rolsuper OR NOT owner.rolcanlogin)
          AND pg_catalog.pg_has_role(CURRENT_USER,a.nspowner,'USAGE')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(a.nspacl,pg_catalog.acldefault('n',a.nspowner))) x
            WHERE x.privilege_type='CREATE' AND x.grantee<>a.nspowner)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.nspacl,pg_catalog.acldefault('n',p.nspowner))) x
            WHERE x.privilege_type='CREATE' AND x.grantee<>p.nspowner)) INTO namespace_ok;
      IF namespace_ok IS NOT TRUE THEN RAISE EXCEPTION 'Capability namespace unavailable'; END IF;
      SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=private_schema AND c.relname='clinic_capability_namespace' AND c.relkind='r'
          AND c.relowner=n.nspowner
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x WHERE x.grantee<>c.relowner)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=c.oid AND a.attacl IS NOT NULL)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal)) INTO namespace_ok;
      IF namespace_ok IS NOT TRUE THEN RAISE EXCEPTION 'Capability marker unavailable'; END IF;
      EXECUTE pg_catalog.format('SELECT count(*)=1 AND bool_and(id=1 AND format_version=1 AND application_schema=%L AND private_schema=%L) FROM %I.clinic_capability_namespace',
        target_schema,private_schema,private_schema) INTO namespace_ok;
      IF namespace_ok IS NOT TRUE THEN RAISE EXCEPTION 'Capability namespace identity mismatch'; END IF;
      IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=target_schema AND c.relname IN ('all_free_requests','all_free_request_lines','all_free_request_events')
          AND p.polname IN ('allfree_backend_select','allfree_backend_insert')
      ) THEN RAISE EXCEPTION 'Remove provisioned all-free role policies before downgrade'; END IF;
      EXECUTE format('DROP POLICY allfree_template_insert ON %I.all_free_request_events', target_schema);
      EXECUTE format('DROP POLICY allfree_template_select ON %I.all_free_request_events', target_schema);
      EXECUTE format('DROP POLICY allfree_template_insert ON %I.all_free_request_lines', target_schema);
      EXECUTE format('DROP POLICY allfree_template_select ON %I.all_free_request_lines', target_schema);
      EXECUTE format('DROP POLICY allfree_template_insert ON %I.all_free_requests', target_schema);
      EXECUTE format('DROP POLICY allfree_template_select ON %I.all_free_requests', target_schema);
      EXECUTE format('DROP FUNCTION %I.all_free_pending_exists(integer)', private_schema);
    END
    $migration$
    """)
