"""Conservative mutex for unresolved provider evidence.

Not deployable until every legacy callback durably stores a receipt before a
retryable trigger conflict and has a phase-correct ACK. No settlement is enabled.
"""
import hashlib

import sqlalchemy as sa

from alembic import op

revision = "0123_reconciliation_fence"
down_revision = "0122_telegram_link_epoch"
branch_labels = None
depends_on = None


def _capability_schema_name(schema: str) -> str:
    # Frozen v1; parity with migration 0112 and app.db.capability_namespace.
    if not isinstance(schema, str) or not schema or "\0" in schema:
        raise ValueError("Invalid application schema")
    raw = schema.encode("utf-8")
    if len(raw) > 63:
        raise ValueError("Application schema exceeds PostgreSQL identifier limit")
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + raw).hexdigest()[:32]


def upgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Unsupported reconciliation fence dialect")
    op.create_table(
        "provider_reconciliation_mutex",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.CheckConstraint("id = 1", name="ck_provider_reconciliation_mutex_singleton"),
    )
    op.execute("INSERT INTO provider_reconciliation_mutex (id) VALUES (1)")
    if dialect == "sqlite":
        op.execute("CREATE TRIGGER reconciliation_mutex_no_delete BEFORE DELETE ON provider_reconciliation_mutex BEGIN SELECT RAISE(ABORT, 'reconciliation mutex is immutable'); END")
        for table, events in (("provider_reconciliation_events", ("INSERT", "UPDATE", "DELETE")), ("click_callback_receipts", ("INSERT",))):
            for event in events:
                when = " WHEN NEW.phase='complete'" if table == "click_callback_receipts" else ""
                op.execute(f"CREATE TRIGGER reconciliation_{table}_{event.lower()} BEFORE {event} ON {table}{when} BEGIN UPDATE provider_reconciliation_mutex SET id=id WHERE id=1; END")
        return
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted migration schema required")
    q = context.dialect.identifier_preparer.quote_schema(schema)
    private = _capability_schema_name(schema)
    qp = context.dialect.identifier_preparer.quote_schema(private)
    literal_q = q.replace("'", "''")
    literal_qp = qp.replace("'", "''")
    literal_schema = schema.replace("'", "''")
    literal_private = private.replace("'", "''")
    # 0112 creates this exact owner-controlled private namespace. Do not adopt
    # an absent, mismatched or publicly writable schema.
    op.execute(f"""
      SELECT 1 / CASE WHEN EXISTS (SELECT 1 FROM pg_catalog.pg_namespace app
        JOIN pg_catalog.pg_namespace priv ON priv.nspname='{literal_private}' AND priv.nspowner=app.nspowner
        WHERE app.nspname='{literal_schema}' AND NOT EXISTS (
          SELECT 1 FROM pg_catalog.aclexplode(COALESCE(priv.nspacl,pg_catalog.acldefault('n',priv.nspowner))) a
          WHERE a.privilege_type='CREATE' AND a.grantee<>priv.nspowner))
        AND (SELECT count(*) FROM {qp}.clinic_capability_namespace)=1
        AND EXISTS (SELECT 1 FROM {qp}.clinic_capability_namespace
          WHERE id=1 AND format_version=1 AND application_schema='{literal_schema}' AND private_schema='{literal_private}')
        THEN 1 ELSE 0 END
    """)
    # Schema identifiers appear inside both PL/pgSQL bodies. PostgreSQL does
    # not recognize SQL quoting inside a dollar-quoted literal, so choose a
    # tag absent even from adversarially quoted schema names.
    tag_number = 0
    while True:
        dollar_tag = f"$reconciliation_fence_{tag_number}$"
        if dollar_tag not in q:
            break
        tag_number += 1
    op.execute(f"""DO {dollar_tag} DECLARE trusted_owner name; BEGIN
      SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{literal_schema}';
      EXECUTE pg_catalog.format('ALTER TABLE %I.provider_reconciliation_mutex OWNER TO %I', '{literal_schema}', trusted_owner);
      EXECUTE pg_catalog.format('CREATE POLICY reconciliation_mutex_owner_select ON %I.provider_reconciliation_mutex FOR SELECT TO %I USING (true)', '{literal_schema}', trusted_owner);
      EXECUTE pg_catalog.format('CREATE POLICY reconciliation_mutex_owner_update ON %I.provider_reconciliation_mutex FOR UPDATE TO %I USING (true) WITH CHECK (false)', '{literal_schema}', trusted_owner);
    END {dollar_tag}""")
    op.execute(f"ALTER TABLE {q}.provider_reconciliation_mutex ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {q}.provider_reconciliation_mutex FORCE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON {q}.provider_reconciliation_mutex FROM PUBLIC")
    op.execute(f"""
      CREATE FUNCTION {qp}.reconciliation_mutex_lock() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS {dollar_tag}
      DECLARE found_id integer;
      BEGIN
        IF TG_TABLE_NAME = 'click_callback_receipts' AND NEW.phase <> 'complete' THEN RETURN NEW; END IF;
        SELECT id INTO found_id FROM {q}.provider_reconciliation_mutex WHERE id=1 FOR UPDATE NOWAIT;
        IF found_id IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'Reconciliation mutex unavailable'; END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END {dollar_tag}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {qp}.reconciliation_mutex_lock() FROM PUBLIC")
    op.execute(f"CREATE TRIGGER reconciliation_event_lock BEFORE INSERT OR UPDATE OR DELETE ON {q}.provider_reconciliation_events FOR EACH ROW EXECUTE FUNCTION {qp}.reconciliation_mutex_lock()")
    op.execute(f"CREATE TRIGGER reconciliation_receipt_lock BEFORE INSERT ON {q}.click_callback_receipts FOR EACH ROW EXECUTE FUNCTION {qp}.reconciliation_mutex_lock()")
    # A separate statement after the mutex ensures a fresh READ COMMITTED snapshot.
    op.execute(f"""
      CREATE FUNCTION {qp}.reconciliation_pending_guard() RETURNS boolean
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS {dollar_tag}
      DECLARE found_id integer; policies_safe boolean; triggers_safe boolean;
      BEGIN
        IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
          RAISE EXCEPTION 'Reconciliation requires read committed';
        END IF;
        -- Zero-row SELECT takes ACCESS SHARE with column-only privileges.
        PERFORM id FROM {q}.provider_reconciliation_events WHERE false;
        PERFORM phase FROM {q}.click_callback_receipts WHERE false;
        PERFORM id FROM {q}.provider_reconciliation_mutex WHERE false;
        SELECT count(*)=3 AND COALESCE(bool_and(c.relrowsecurity AND EXISTS (
          SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid AND p.polpermissive
            AND p.polcmd IN ('r','*') AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
            AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true'
        ) AND NOT EXISTS (
          SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid AND NOT p.polpermissive
            AND p.polcmd IN ('r','*') AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) role_id
              WHERE role_id=0 OR pg_catalog.pg_has_role(CURRENT_USER,role_id,'MEMBER'))
        )),false) INTO policies_safe
        FROM pg_catalog.pg_class c WHERE c.oid IN (
          '{literal_q}.provider_reconciliation_events'::pg_catalog.regclass,
          '{literal_q}.click_callback_receipts'::pg_catalog.regclass,
          '{literal_q}.provider_reconciliation_mutex'::pg_catalog.regclass);
        IF policies_safe IS NOT TRUE THEN RAISE EXCEPTION 'Incomplete reconciliation visibility'; END IF;
        SELECT count(*)=2 AND COALESCE(bool_and(t.tgenabled IN ('O','A') AND NOT t.tgisinternal
          AND t.tgqual IS NULL AND t.tgattr::text='' AND t.tgtype=expected.kind
          AND p.oid='{literal_qp}.reconciliation_mutex_lock()'::pg_catalog.regprocedure
          AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)
          AND p.prosecdef AND 'search_path=pg_catalog'=ANY(p.proconfig)
          AND 'row_security=on'=ANY(p.proconfig)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')
        ),false) INTO triggers_safe
        FROM (VALUES ('provider_reconciliation_events','reconciliation_event_lock',31),
                     ('click_callback_receipts','reconciliation_receipt_lock',7)) expected(table_name,trigger_name,kind)
        JOIN pg_catalog.pg_class c ON c.relnamespace=(SELECT relnamespace FROM pg_catalog.pg_class WHERE oid='{literal_q}.provider_reconciliation_mutex'::pg_catalog.regclass) AND c.relname=expected.table_name
        JOIN pg_catalog.pg_trigger t ON t.tgrelid=c.oid AND t.tgname=expected.trigger_name
        JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid;
        IF triggers_safe IS NOT TRUE THEN RAISE EXCEPTION 'Reconciliation triggers unavailable'; END IF;
        SELECT id INTO found_id FROM {q}.provider_reconciliation_mutex WHERE id=1 FOR UPDATE;
        IF found_id IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'Reconciliation mutex unavailable'; END IF;
        RETURN EXISTS (SELECT 1 FROM {q}.provider_reconciliation_events)
            OR EXISTS (SELECT 1 FROM {q}.click_callback_receipts WHERE phase='complete');
      END {dollar_tag}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {qp}.reconciliation_pending_guard() FROM PUBLIC")
    for signature in ("reconciliation_mutex_lock()", "reconciliation_pending_guard()"):
        op.execute(f"""DO {dollar_tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{literal_schema}';
          EXECUTE pg_catalog.format('ALTER FUNCTION %I.{signature} OWNER TO %I', '{literal_private}', trusted_owner);
        END {dollar_tag}""")


def downgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect == "postgresql":
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted migration schema required")
        q = context.dialect.identifier_preparer.quote_schema(schema)
        qp = context.dialect.identifier_preparer.quote_schema(_capability_schema_name(schema))
        op.execute(f"LOCK TABLE {q}.provider_reconciliation_events, {q}.click_callback_receipts, {q}.provider_reconciliation_mutex IN ACCESS EXCLUSIVE MODE")
        op.execute("SET LOCAL row_security=off")
        events, receipts = f"{q}.provider_reconciliation_events", f"{q}.click_callback_receipts"
    elif dialect == "sqlite":
        op.execute("UPDATE provider_reconciliation_mutex SET id=id WHERE id=1")
        events, receipts = "provider_reconciliation_events", "click_callback_receipts"
    else:
        raise RuntimeError("Unsupported reconciliation fence dialect")
    op.execute("CREATE TEMPORARY TABLE reconciliation_downgrade_guard_0123 (valid integer NOT NULL CHECK (valid=1))")
    op.execute(f"INSERT INTO reconciliation_downgrade_guard_0123 SELECT CASE WHEN EXISTS(SELECT 1 FROM {events}) OR EXISTS(SELECT 1 FROM {receipts} WHERE phase='complete') THEN 0 ELSE 1 END")
    op.execute("DROP TABLE reconciliation_downgrade_guard_0123")
    if dialect == "postgresql":
        op.execute(f"DROP TRIGGER reconciliation_event_lock ON {q}.provider_reconciliation_events")
        op.execute(f"DROP TRIGGER reconciliation_receipt_lock ON {q}.click_callback_receipts")
        op.execute(f"DROP FUNCTION {qp}.reconciliation_pending_guard()")
        op.execute(f"DROP FUNCTION {qp}.reconciliation_mutex_lock()")
        op.drop_table("provider_reconciliation_mutex", schema=schema)
    else:
        for table, events in (("provider_reconciliation_events", ("insert", "update", "delete")), ("click_callback_receipts", ("insert",))):
            for event in events:
                op.execute(f"DROP TRIGGER reconciliation_{table}_{event}")
        op.execute("DROP TRIGGER reconciliation_mutex_no_delete")
        op.drop_table("provider_reconciliation_mutex")
