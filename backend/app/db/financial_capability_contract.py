"""Frozen 0118 financial capability definitions and trigger identity checks.

These reviewed templates are independent of database catalog contents. An
operator must drain traffic while database roles, functions, or triggers change.
"""
from __future__ import annotations

from sqlalchemy import text

_BODY_TEMPLATES = {'financial_encounter_generation_fence': '      BEGIN\n'
                                         "        IF TG_OP = 'INSERT' THEN\n"
                                         '          NEW.generation := '
                                         "pg_catalog.nextval(pg_catalog.format('%I.encounter_financial_generation_seq', "
                                         'TG_TABLE_SCHEMA)::pg_catalog.regclass);\n'
                                         '        ELSIF NEW.generation IS DISTINCT FROM OLD.generation AND '
                                         'pg_catalog.pg_trigger_depth() <= 1 THEN\n'
                                         "          RAISE EXCEPTION 'Encounter generation is server "
                                         "controlled';\n"
                                         '        END IF;\n'
                                         '        RETURN NEW;\n'
                                         '      END',
 'financial_lock_rows': '\n'
                        '          DECLARE result integer[];\n'
                        '          BEGIN\n'
                        '            IF ids IS NULL OR pg_catalog.cardinality(ids)>1000 OR EXISTS\n'
                        '              (SELECT 1 FROM pg_catalog.unnest(ids) x WHERE x IS NULL OR x<=0) '
                        'THEN\n'
                        "              RAISE EXCEPTION 'Invalid financial lock request';\n"
                        '            END IF;\n'
                        "            IF kind='visit' THEN\n"
                        '              SELECT ARRAY(SELECT id FROM \x00I.visits WHERE id=ANY(ids) ORDER BY '
                        'id FOR UPDATE NOWAIT) INTO result;\n'
                        "            ELSIF kind='encounter' THEN\n"
                        '              SELECT ARRAY(SELECT id FROM \x00I.encounters WHERE id=ANY(ids) ORDER '
                        'BY id FOR UPDATE NOWAIT) INTO result;\n'
                        "            ELSIF kind='invoice' THEN\n"
                        '              SELECT ARRAY(SELECT id FROM \x00I.payment_invoices WHERE id=ANY(ids) '
                        'ORDER BY id FOR UPDATE NOWAIT) INTO result;\n'
                        "            ELSE RAISE EXCEPTION 'Invalid financial lock kind'; END IF;\n"
                        '            RETURN result;\n'
                        '          END\n'
                        '        ',
 'financial_probe_group': '\n'
                          '          DECLARE members integer[]; lines integer[]; invoices integer[]; links '
                          'integer[];\n'
                          '                  pending integer[]; history boolean; policy_safe boolean; '
                          'triggers_safe boolean;\n'
                          '          BEGIN\n'
                          '            IF encounter_id_input IS NULL OR encounter_id_input<=0 THEN RAISE '
                          "EXCEPTION 'Invalid encounter'; END IF;\n"
                          '            LOCK TABLE \x00I.visits, \x00I.encounters, \x00I.visit_services,\n'
                          '              \x00I.payment_invoices, \x00I.payment_invoice_visits, '
                          '\x00I.payments,\n'
                          '              \x00I.payment_visits, \x00I.payment_webhooks, '
                          '\x00I.payment_transactions,\n'
                          '              \x00I.invoices, \x00I.provider_active_visit_reservations,\n'
                          '              \x00I.provider_attempt_visits, '
                          '\x00I.provider_reconciliation_events,\n'
                          '              \x00I.all_free_requests IN ACCESS SHARE MODE;\n'
                          '            -- A role-visible policy is required for every RLS table. An extra\n'
                          '            -- restrictive policy or a removed policy is a closed failure.\n'
                          '            SELECT count(*)=14 AND COALESCE(bool_and(NOT c.relrowsecurity OR (\n'
                          '              EXISTS (SELECT 1 FROM pg_catalog.pg_policy p\n'
                          '                WHERE p.polrelid=c.oid AND p.polpermissive AND p.polcmd IN '
                          "('r','*')\n"
                          '                  AND (SELECT oid FROM pg_catalog.pg_roles WHERE '
                          'rolname=CURRENT_USER)=ANY(p.polroles)\n'
                          "                  AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')\n"
                          '              AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p\n'
                          '                WHERE p.polrelid=c.oid AND NOT p.polpermissive AND p.polcmd IN '
                          "('r','*')\n"
                          '                  AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) '
                          'role_id\n'
                          '                    WHERE CASE WHEN role_id=0 THEN true ELSE '
                          "pg_catalog.pg_has_role(CURRENT_USER,role_id,'MEMBER') END))\n"
                          '            )),false) INTO policy_safe\n'
                          '            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON '
                          'n.oid=c.relnamespace\n'
                          '            WHERE n.oid=(SELECT relnamespace FROM pg_catalog.pg_class\n'
                          "                         WHERE oid='\x00L.encounters'::pg_catalog.regclass)\n"
                          '              AND c.relname IN '
                          "('visits','encounters','visit_services','payment_invoices',\n"
                          '                '
                          "'payment_invoice_visits','payments','payment_visits','payment_webhooks','payment_transactions',\n"
                          '                '
                          "'invoices','provider_active_visit_reservations','provider_attempt_visits',\n"
                          "                'provider_reconciliation_events','all_free_requests');\n"
                          "            IF policy_safe IS NOT TRUE THEN RAISE EXCEPTION 'Incomplete financial "
                          "capability visibility'; END IF;\n"
                          "            SELECT count(*)=7 AND COALESCE(bool_and(t.tgenabled IN ('O','A')\n"
                          "              AND NOT t.tgisinternal AND t.tgqual IS NULL AND t.tgattr::text=''\n"
                          '              AND t.tgtype=expected.trigger_type AND '
                          'p.proname=expected.function_name\n'
                          '              AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles WHERE '
                          'rolname=CURRENT_USER)\n'
                          '              AND p.prosecdef AND pg_catalog.cardinality(p.proconfig)=2\n'
                          "              AND 'search_path=pg_catalog'=ANY(p.proconfig) AND "
                          "'row_security=on'=ANY(p.proconfig)\n"
                          '              AND NOT EXISTS (SELECT 1 FROM '
                          "pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) "
                          'a\n'
                          "                WHERE a.grantee=0 AND a.privilege_type='EXECUTE')),false) INTO "
                          'triggers_safe\n'
                          '            FROM (VALUES\n'
                          '              '
                          "('encounters','trg_financial_encounter_generation',23,'financial_encounter_generation_fence'),\n"
                          '              '
                          "('visits','trg_financial_visit_membership',29,'financial_visit_membership_fence'),\n"
                          '              '
                          "('payment_invoice_visits','trg_financial_invoice_link',29,'financial_visit_reference_fence'),\n"
                          '              '
                          "('payments','trg_financial_payment',29,'financial_visit_reference_fence'),\n"
                          '              '
                          "('payment_visits','trg_financial_payment_link',29,'financial_visit_reference_fence'),\n"
                          '              '
                          "('payment_invoices','trg_financial_invoice',25,'financial_visit_reference_fence'),\n"
                          '              '
                          "('invoices','trg_financial_billing_invoice',29,'financial_visit_reference_fence')\n"
                          '            ) AS expected(table_name, trigger_name, trigger_type, function_name)\n'
                          '            JOIN pg_catalog.pg_class c ON c.relnamespace=(SELECT relnamespace '
                          'FROM pg_catalog.pg_class\n'
                          "                  WHERE oid='\x00L.encounters'::pg_catalog.regclass) AND "
                          'c.relname=expected.table_name\n'
                          '            JOIN pg_catalog.pg_trigger t ON t.tgrelid=c.oid AND '
                          't.tgname=expected.trigger_name\n'
                          '            JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid;\n'
                          '            IF triggers_safe IS NOT TRUE OR '
                          "pg_catalog.current_setting('session_replication_role')<>'origin' THEN\n"
                          "              RAISE EXCEPTION 'Financial writer fence is unavailable';\n"
                          '            END IF;\n'
                          '            SELECT ARRAY(SELECT id FROM \x00I.visits WHERE '
                          'encounter_id=encounter_id_input ORDER BY id) INTO members;\n'
                          '            SELECT ARRAY(SELECT id FROM \x00I.visit_services WHERE '
                          'visit_id=ANY(members) ORDER BY id) INTO lines;\n'
                          '            SELECT ARRAY(SELECT DISTINCT invoice_id FROM '
                          '\x00I.payment_invoice_visits WHERE visit_id=ANY(members) ORDER BY invoice_id) '
                          'INTO invoices;\n'
                          '            SELECT ARRAY(SELECT id FROM \x00I.payment_invoice_visits WHERE '
                          'invoice_id=ANY(invoices) ORDER BY id) INTO links;\n'
                          '            PERFORM id FROM \x00I.all_free_requests WHERE visit_id=ANY(members) '
                          "AND status='pending' ORDER BY id FOR UPDATE NOWAIT;\n"
                          '            SELECT ARRAY(SELECT id FROM \x00I.all_free_requests WHERE '
                          "visit_id=ANY(members) AND status='pending' ORDER BY id) INTO pending;\n"
                          '            SELECT EXISTS (SELECT 1 FROM \x00I.payments p WHERE '
                          'p.visit_id=ANY(members)\n'
                          '                OR EXISTS (SELECT 1 FROM \x00I.payment_visits pv WHERE '
                          'pv.payment_id=p.id AND pv.visit_id=ANY(members)))\n'
                          '              OR EXISTS (SELECT 1 FROM \x00I.payment_webhooks WHERE '
                          'visit_id=ANY(members))\n'
                          '              OR EXISTS (SELECT 1 FROM \x00I.payment_transactions WHERE '
                          'visit_id=ANY(members))\n'
                          '              OR EXISTS (SELECT 1 FROM \x00I.invoices WHERE '
                          'visit_id=ANY(members))\n'
                          '              OR EXISTS (SELECT 1 FROM \x00I.provider_active_visit_reservations '
                          'WHERE visit_id=ANY(members))\n'
                          '              OR EXISTS (SELECT 1 FROM \x00I.provider_attempt_visits WHERE '
                          'visit_id_snapshot=ANY(members))\n'
                          '              OR EXISTS (SELECT 1 FROM \x00I.provider_reconciliation_events r\n'
                          '                WHERE r.invoice_id_snapshot=ANY(invoices) OR '
                          "r.target_kind='unmatched') INTO history;\n"
                          '            RETURN '
                          "pg_catalog.jsonb_build_object('members',members,'lines',lines,'invoices',invoices,\n"
                          '                                                  '
                          "'links',links,'pending',pending,'history',history);\n"
                          '          END\n'
                          '        ',
 'financial_visit_membership_fence': '      DECLARE old_enc integer; new_enc integer; locked_count integer;\n'
                                     '      BEGIN\n'
                                     "        IF TG_OP = 'UPDATE' AND ROW(OLD.encounter_id, OLD.patient_id)\n"
                                     '          IS NOT DISTINCT FROM ROW(NEW.encounter_id, NEW.patient_id) '
                                     'THEN RETURN NEW; END IF;\n'
                                     "        IF TG_OP <> 'INSERT' THEN old_enc := OLD.encounter_id; END "
                                     'IF;\n'
                                     "        IF TG_OP <> 'DELETE' THEN new_enc := NEW.encounter_id; END "
                                     'IF;\n'
                                     "        EXECUTE pg_catalog.format('SELECT count(*) FROM (SELECT id "
                                     'FROM %I.encounters WHERE id IN ($1,$2) ORDER BY id FOR UPDATE NOWAIT) '
                                     "locked', TG_TABLE_SCHEMA)\n"
                                     '          INTO locked_count USING old_enc, new_enc;\n'
                                     '        IF locked_count <> (SELECT count(DISTINCT x) FROM '
                                     'pg_catalog.unnest(ARRAY[old_enc,new_enc]) x WHERE x IS NOT NULL) THEN\n'
                                     "          RAISE EXCEPTION 'Encounter membership changed';\n"
                                     '        END IF;\n'
                                     "        EXECUTE pg_catalog.format('UPDATE %I.encounters SET "
                                     "generation=pg_catalog.nextval(pg_catalog.format(''%%I.encounter_financial_generation_seq'', "
                                     "$3)::pg_catalog.regclass) WHERE id IN ($1,$2)', TG_TABLE_SCHEMA)\n"
                                     '          USING old_enc, new_enc, TG_TABLE_SCHEMA;\n'
                                     "        IF TG_OP='DELETE' THEN RETURN OLD; END IF;\n"
                                     '        RETURN NEW;\n'
                                     '      END',
 'financial_visit_reference_fence': '      DECLARE old_visit integer; new_visit integer; old_invoice '
                                    'integer; new_invoice integer;\n'
                                    '              ids integer[]; locked_count integer;\n'
                                    '      BEGIN\n'
                                    "        IF TG_TABLE_NAME = 'payment_invoices' THEN\n"
                                    "          EXECUTE pg_catalog.format('SELECT COALESCE(array_agg(DISTINCT "
                                    'visit_id ORDER BY visit_id), ARRAY[]::integer[]) FROM '
                                    "%I.payment_invoice_visits WHERE invoice_id=$1', TG_TABLE_SCHEMA)\n"
                                    '            INTO ids USING OLD.id;\n'
                                    '        ELSE\n'
                                    "          IF TG_OP <> 'INSERT' THEN old_visit := OLD.visit_id; END IF;\n"
                                    "          IF TG_OP <> 'DELETE' THEN new_visit := NEW.visit_id; END IF;\n"
                                    '          SELECT COALESCE(array_agg(DISTINCT x ORDER BY x), '
                                    'ARRAY[]::integer[])\n'
                                    '            INTO ids FROM pg_catalog.unnest(ARRAY[old_visit,new_visit]) '
                                    'x WHERE x IS NOT NULL;\n'
                                    '        END IF;\n'
                                    "        EXECUTE pg_catalog.format('SELECT count(*) FROM (SELECT id FROM "
                                    "%I.visits WHERE id = ANY($1) ORDER BY id FOR UPDATE NOWAIT) locked', "
                                    'TG_TABLE_SCHEMA)\n'
                                    '          INTO locked_count USING ids;\n'
                                    '        IF locked_count <> pg_catalog.cardinality(ids) THEN RAISE '
                                    "EXCEPTION 'Visit reference changed'; END IF;\n"
                                    "        IF TG_TABLE_NAME = 'payment_invoice_visits' THEN\n"
                                    "          IF TG_OP <> 'INSERT' THEN old_invoice := OLD.invoice_id; END "
                                    'IF;\n'
                                    "          IF TG_OP <> 'DELETE' THEN new_invoice := NEW.invoice_id; END "
                                    'IF;\n'
                                    "          EXECUTE pg_catalog.format('SELECT count(*) FROM (SELECT id "
                                    'FROM %I.payment_invoices WHERE id IN ($1,$2) ORDER BY id FOR UPDATE '
                                    "NOWAIT) locked', TG_TABLE_SCHEMA)\n"
                                    '            INTO locked_count USING old_invoice, new_invoice;\n'
                                    '          IF locked_count <> (SELECT count(DISTINCT x) FROM '
                                    'pg_catalog.unnest(ARRAY[old_invoice,new_invoice]) x WHERE x IS NOT '
                                    'NULL) THEN\n'
                                    "            RAISE EXCEPTION 'Invoice reference changed';\n"
                                    '          END IF;\n'
                                    '        END IF;\n'
                                    "        IF TG_OP='DELETE' THEN RETURN OLD; END IF;\n"
                                    '        RETURN NEW;\n'
                                    '      END'}


def expected_financial_bodies(quoted_schema: str) -> dict[str, str]:
    if not isinstance(quoted_schema, str) or not quoted_schema or "\x00" in quoted_schema:
        raise ValueError("A quoted financial schema is required")
    escaped = quoted_schema.replace("'", "''")
    return {name: body.replace("\x00L", escaped).replace("\x00I", quoted_schema).strip()
            for name, body in _BODY_TEMPLATES.items()}


_TRIGGER_BINDINGS = {
    ("encounters", "trg_financial_encounter_generation"): (23, "financial_encounter_generation_fence"),
    ("visits", "trg_financial_visit_membership"): (29, "financial_visit_membership_fence"),
    ("payment_invoice_visits", "trg_financial_invoice_link"): (29, "financial_visit_reference_fence"),
    ("payments", "trg_financial_payment"): (29, "financial_visit_reference_fence"),
    ("payment_visits", "trg_financial_payment_link"): (29, "financial_visit_reference_fence"),
    ("payment_invoices", "trg_financial_invoice"): (25, "financial_visit_reference_fence"),
    ("invoices", "trg_financial_billing_invoice"): (29, "financial_visit_reference_fence"),
}


def financial_contract_is_valid(db, *, schema: str, private: str, quoted_schema: str,
                                backend_oid: int, allowed_owner_oids: tuple[int, ...] | None = None) -> bool:
    """Check frozen bodies, signatures, owners, grants and trigger bindings."""
    expected = expected_financial_bodies(quoted_schema)
    rows = db.execute(text("""
      SELECT p.oid,p.proname,p.pronargs,p.proowner,p.prosecdef,p.prokind,p.provolatile,p.proconfig,p.prosrc,
        p.prorettype,p.proargtypes[0] AS arg0,p.proargtypes[1] AS arg1,p.provariadic,p.pronargdefaults,l.lanname,
        NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,
          pg_catalog.acldefault('f',p.proowner))) a WHERE a.grantee<>p.proowner AND NOT
          (p.proname IN ('financial_lock_rows','financial_probe_group') AND a.grantee=:backend
           AND a.privilege_type='EXECUTE' AND NOT a.is_grantable)) AS acl_safe
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        JOIN pg_catalog.pg_language l ON l.oid=p.prolang
      WHERE n.nspname=:private AND p.proname=ANY(:names)
    """), {"private": private, "names": list(expected), "backend": backend_oid}).mappings().all()
    if len(rows) != len(expected) or {row["proname"] for row in rows} != set(expected):
        return False
    owners = {row["proowner"] for row in rows}
    if len(owners) != 1 or (allowed_owner_oids is not None and not owners.issubset(set(allowed_owner_oids))):
        return False
    types = db.execute(text("""
      SELECT 'pg_catalog.trigger'::pg_catalog.regtype::oid AS trigger_type,
        'pg_catalog.text'::pg_catalog.regtype::oid AS text_type,
        'pg_catalog.int4'::pg_catalog.regtype::oid AS int_type,
        'pg_catalog.int4[]'::pg_catalog.regtype::oid AS int_array_type,
        'pg_catalog.jsonb'::pg_catalog.regtype::oid AS json_type
    """)).mappings().one()
    for row in rows:
        name = row["proname"]
        if name == "financial_lock_rows":
            args, result = [types["text_type"], types["int_array_type"]], types["int_array_type"]
        elif name == "financial_probe_group":
            args, result = [types["int_type"]], types["json_type"]
        else:
            args, result = [], types["trigger_type"]
        if (not row["prosecdef"] or row["prokind"] != "f" or row["provolatile"] != "v"
                or row["lanname"] != "plpgsql" or not row["acl_safe"]
                or row["pronargs"] != len(args) or [row["arg0"], row["arg1"]][:row["pronargs"]] != args
                or row["prorettype"] != result or row["provariadic"] != 0 or row["pronargdefaults"] != 0
                or set(row["proconfig"] or []) != {"search_path=pg_catalog", "row_security=on"}
                or not isinstance(row["prosrc"], str) or row["prosrc"].strip() != expected[name]):
            return False
    functions = {row["proname"]: row["oid"] for row in rows}
    triggers = db.execute(text("""
      SELECT t.tgname,t.tgtype,t.tgenabled,t.tgqual IS NULL AS no_condition,
        t.tgoldtable IS NULL AND t.tgnewtable IS NULL AS no_transition,t.tgattr::text AS columns,
        c.relname,n.nspname,p.oid AS function_oid
      FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
      WHERE NOT t.tgisinternal AND ((n.nspname=:schema AND t.tgname=ANY(:names)) OR p.oid=ANY(:functions))
    """), {"schema": schema, "names": [name for _, name in _TRIGGER_BINDINGS],
            "functions": list(functions.values())}).mappings().all()
    found = {(row["relname"], row["tgname"]): row for row in triggers}
    if len(triggers) != len(_TRIGGER_BINDINGS) or set(found) != set(_TRIGGER_BINDINGS):
        return False
    for key, (expected_type, function) in _TRIGGER_BINDINGS.items():
        row = found[key]
        if (row["nspname"] != schema or row["function_oid"] != functions[function]
                or row["tgtype"] != expected_type or row["tgenabled"] not in {"O", "A"}
                or not row["no_condition"] or not row["no_transition"] or row["columns"]):
            return False
    return True


def financial_all_free_lock_role(
    db, *, schema: str, private: str, quoted_schema: str, backend_role: str | None = None,
) -> int | None:
    """Identify the isolated owner permitted to lock All Free rows via 0118."""
    profile = db.execute(text("""
      SELECT cap.oid AS capability_oid, backend.oid AS backend_oid
      FROM pg_catalog.pg_proc probe
      JOIN pg_catalog.pg_namespace private_ns ON private_ns.oid=probe.pronamespace
      JOIN pg_catalog.pg_roles cap ON cap.oid=probe.proowner
      JOIN pg_catalog.pg_roles backend
        ON backend.rolname=COALESCE(CAST(:backend AS text),CURRENT_USER::text)
      JOIN pg_catalog.pg_namespace app_ns ON app_ns.nspname=:schema
      JOIN pg_catalog.pg_class requests ON requests.relnamespace=app_ns.oid
        AND requests.relname='all_free_requests'
      WHERE private_ns.nspname=:private AND probe.proname='financial_probe_group'
        AND probe.proargtypes='23'::oidvector AND private_ns.nspowner=app_ns.nspowner
        AND requests.relrowsecurity AND cap.oid NOT IN (requests.relowner, backend.oid)
        AND NOT (cap.rolcanlogin OR cap.rolsuper OR cap.rolbypassrls OR cap.rolcreaterole
          OR cap.rolcreatedb OR cap.rolreplication)
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles other WHERE other.oid<>cap.oid
          AND (pg_catalog.pg_has_role(cap.oid,other.oid,'MEMBER') OR
            (NOT other.rolsuper AND pg_catalog.pg_has_role(other.oid,cap.oid,'MEMBER'))))
        AND pg_catalog.has_function_privilege(backend.oid,probe.oid,'EXECUTE')
        AND pg_catalog.has_table_privilege(cap.oid,requests.oid,'SELECT')
        AND pg_catalog.has_column_privilege(cap.oid,requests.oid,'id','UPDATE')
        AND (SELECT count(*)=2 AND COALESCE(bool_and(policy.polpermissive
               AND policy.polroles=ARRAY[cap.oid]::oid[]
               AND pg_catalog.pg_get_expr(policy.polqual,requests.oid) IS NOT DISTINCT FROM 'true'
               AND CASE policy.polname WHEN 'financial_cap_select' THEN
                 policy.polcmd='r' AND policy.polwithcheck IS NULL
               ELSE policy.polcmd='w'
                 AND pg_catalog.pg_get_expr(policy.polwithcheck,requests.oid) IS NOT DISTINCT FROM 'false' END),false)
             FROM pg_catalog.pg_policy policy WHERE policy.polrelid=requests.oid
               AND policy.polname IN ('financial_cap_select','financial_cap_update'))
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy policy
          WHERE policy.polrelid=requests.oid AND policy.polname<>'financial_cap_update'
            AND policy.polcmd IN ('a','w','d','*') AND policy.polpermissive
            AND (0=ANY(policy.polroles) OR cap.oid=ANY(policy.polroles)))
    """), {"schema": schema, "private": private, "backend": backend_role}).mappings().one_or_none()
    if profile is None or not financial_contract_is_valid(
        db, schema=schema, private=private, quoted_schema=quoted_schema,
        backend_oid=profile["backend_oid"], allowed_owner_oids=(profile["capability_oid"],),
    ):
        return None
    return profile["capability_oid"]
