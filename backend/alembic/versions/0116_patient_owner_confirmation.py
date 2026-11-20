"""Invalidate patient confirmation capabilities when ownership changes.

Changing or deleting a user must not transfer already-issued patient links to
the new owner. Existing unaffected links are preserved on upgrade.
"""

import hashlib

from alembic import op

revision = "0116_patient_owner_confirmation"
down_revision = "0115_confirmation_trigger_path"
branch_labels = None
depends_on = None


def _capability_schema_name(schema: str) -> str:
    # Frozen v1 contract; migration must remain independent of runtime code.
    if not isinstance(schema, str) or not schema or "\0" in schema:
        raise ValueError("Invalid application schema")
    raw = schema.encode("utf-8")
    if len(raw) > 63:
        raise ValueError("Application schema exceeds PostgreSQL identifier limit")
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + raw).hexdigest()[:32]


def owner_function_body(qualified: str, private_schema: str) -> str:
    """Exact reviewed PL/pgSQL body, also checked by role provisioning."""
    patient_relation = f"{qualified}.patients".replace("'", "''")
    visit_relation = f"{qualified}.visits".replace("'", "''")
    sequence = f"{qualified}.visit_confirmation_generation_seq".replace("'", "''")
    private_literal = private_schema.replace("'", "''")
    return f"""
        BEGIN
          IF TG_RELID <> '{patient_relation}'::pg_catalog.regclass OR TG_OP <> 'UPDATE' THEN
            RAISE EXCEPTION 'invalid patient confirmation trigger context';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_namespace a JOIN pg_catalog.pg_namespace p
              ON p.nspowner=a.nspowner
            WHERE a.nspname=TG_TABLE_SCHEMA AND p.nspname='{private_literal}'
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(
                COALESCE(p.nspacl,pg_catalog.acldefault('n',p.nspowner))) x
                WHERE x.privilege_type='CREATE' AND x.grantee<>p.nspowner)
          ) THEN
            RAISE EXCEPTION 'patient confirmation private namespace is unavailable';
          END IF;
          IF NEW.user_id IS NOT DISTINCT FROM OLD.user_id
             AND NEW.is_deleted IS NOT DISTINCT FROM OLD.is_deleted THEN
            RETURN NEW;
          END IF;
          -- The provisioned NOLOGIN function owner must retain precisely the
          -- all-row policies on which this capability relies. DBA changes are
          -- coordinated with traffic drained; an unexpected restrictive policy
          -- fails this whole patient change rather than hiding a visit.
          IF pg_catalog.current_setting('row_security') = 'on' AND NOT (
            EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=CURRENT_USER
              AND NOT r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
              AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication)
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
              WHERE NOT r.rolsuper AND r.rolname<>CURRENT_USER AND
                (pg_catalog.pg_has_role(r.oid,CURRENT_USER,'MEMBER') OR pg_catalog.pg_has_role(CURRENT_USER,r.oid,'MEMBER')))
            AND NOT pg_catalog.has_schema_privilege(CURRENT_USER,TG_TABLE_SCHEMA,'CREATE')
            AND NOT pg_catalog.has_table_privilege(CURRENT_USER,'{visit_relation}'::pg_catalog.regclass,'TRIGGER')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
              LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
              WHERE n.nspname=TG_TABLE_SCHEMA AND a.privilege_type='CREATE' AND a.grantee<>n.nspowner)
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c,
              LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
              WHERE c.oid IN ('{visit_relation}'::pg_catalog.regclass, '{patient_relation}'::pg_catalog.regclass)
                AND a.privilege_type='TRIGGER' AND a.grantee NOT IN
                  (c.relowner, (SELECT nspowner FROM pg_catalog.pg_namespace WHERE nspname=TG_TABLE_SCHEMA)))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
              JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
              WHERE t.tgrelid IN ('{visit_relation}'::pg_catalog.regclass, '{patient_relation}'::pg_catalog.regclass)
                AND NOT t.tgisinternal AND p.proowner NOT IN
                  (c.relowner, (SELECT nspowner FROM pg_catalog.pg_namespace WHERE nspname=TG_TABLE_SCHEMA),
                   (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)))
            AND
            EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid='{visit_relation}'::pg_catalog.regclass
              AND p.polname='owner_confirmation_role_select' AND p.polcmd='r' AND p.polpermissive
              AND p.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)]::pg_catalog.oid[]
              AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true' AND p.polwithcheck IS NULL)
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid='{visit_relation}'::pg_catalog.regclass
              AND p.polname='owner_confirmation_role_update' AND p.polcmd='w' AND p.polpermissive
              AND p.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)]::pg_catalog.oid[]
              AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true'
              AND pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)='true')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid='{visit_relation}'::pg_catalog.regclass
              AND NOT p.polpermissive AND (0=ANY(p.polroles) OR (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)))
          ) THEN
            RAISE EXCEPTION 'patient confirmation visibility policy is unavailable';
          END IF;
          PERFORM 1 FROM {qualified}.visits WHERE patient_id=NEW.id
            AND (confirmation_token IS NOT NULL OR status IN ('pending_confirmation', 'confirmation_processing'))
            ORDER BY id FOR UPDATE;
          UPDATE {qualified}.visits SET
            confirmation_context_epoch=pg_catalog.nextval('{sequence}'::pg_catalog.regclass),
            confirmation_token=NULL, confirmation_expires_at=NULL,
            reminder_sent_at=NULL, reminder_generation=COALESCE(reminder_generation,0)+1
            WHERE patient_id=NEW.id AND (confirmation_token IS NOT NULL OR status IN ('pending_confirmation', 'confirmation_processing'));
          RETURN NEW;
        END """


def patient_lock_function_body(qualified: str, private_schema: str) -> str:
    """Return only an active-subject bit while retaining the Patient row lock."""
    patient_relation = f"{qualified}.patients".replace("'", "''")
    private_literal = private_schema.replace("'", "''")
    return f"""
        DECLARE subject_deleted pg_catalog.bool; subject_found pg_catalog.bool;
        BEGIN
          IF subject_id IS NULL OR subject_id <= 0 THEN
            RAISE EXCEPTION 'invalid confirmation subject';
          END IF;
          SELECT p.is_deleted INTO subject_deleted FROM {qualified}.patients p
            WHERE p.id=subject_id FOR UPDATE;
          subject_found := FOUND;
          IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_namespace a JOIN pg_catalog.pg_namespace p
              ON p.nspowner=a.nspowner
            WHERE a.oid=(SELECT relnamespace FROM pg_catalog.pg_class WHERE oid='{patient_relation}'::pg_catalog.regclass)
              AND p.nspname='{private_literal}'
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(
                COALESCE(p.nspacl,pg_catalog.acldefault('n',p.nspowner))) x
                WHERE x.privilege_type='CREATE' AND x.grantee<>p.nspowner)
          ) THEN
            RAISE EXCEPTION 'patient confirmation private namespace is unavailable';
          END IF;
          IF pg_catalog.current_setting('row_security') = 'on' AND NOT (
            EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=CURRENT_USER
              AND NOT r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
              AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication)
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.rolname<>CURRENT_USER
              AND (pg_catalog.pg_has_role(r.oid,CURRENT_USER,'MEMBER') OR pg_catalog.pg_has_role(CURRENT_USER,r.oid,'MEMBER')))
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid='{patient_relation}'::pg_catalog.regclass
              AND p.polname='owner_confirmation_patient_select' AND p.polcmd='r' AND p.polpermissive
              AND p.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)]::pg_catalog.oid[]
              AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true' AND p.polwithcheck IS NULL)
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid='{patient_relation}'::pg_catalog.regclass
              AND p.polname='owner_confirmation_patient_lock' AND p.polcmd='w' AND p.polpermissive
              AND p.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)]::pg_catalog.oid[]
              AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true'
              AND pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)='false')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid='{patient_relation}'::pg_catalog.regclass
              AND NOT p.polpermissive AND (0=ANY(p.polroles) OR (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid='{patient_relation}'::pg_catalog.regclass
              AND p.polpermissive AND p.polcmd IN ('w','*') AND p.polname<>'owner_confirmation_patient_lock'
              AND (0=ANY(p.polroles) OR (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)))
          ) THEN
            RAISE EXCEPTION 'patient confirmation lock policy is unavailable';
          END IF;
          RETURN subject_found AND subject_deleted IS FALSE;
        END """


def upgrade() -> None:
    context = op.get_context()
    dialect = context.dialect.name
    if dialect == "postgresql":
        schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
        if not schema:
            raise RuntimeError("Trusted migration schema required")
        op.execute("SELECT pg_catalog.set_config('patient_confirmation.saved_standard_strings', pg_catalog.current_setting('standard_conforming_strings'), true)")
        op.execute("SET LOCAL standard_conforming_strings=on")
        qualified = context.dialect.identifier_preparer.quote_schema(schema)
        private = _capability_schema_name(schema)
        private_qualified = context.dialect.identifier_preparer.quote_schema(private)
        body = owner_function_body(qualified, private)
        lock_body = patient_lock_function_body(qualified, private)
        tag_number = 0
        while True:
            dollar_tag = f"$owner_confirmation_{tag_number}$"
            if dollar_tag not in body and dollar_tag not in lock_body:
                break
            tag_number += 1
        # row_security=off is fail-closed: a restricted runtime role must see
        # and update every target or the entire patient change is rolled back.
        op.execute(f"""
        CREATE OR REPLACE FUNCTION {private_qualified}.invalidate_patient_owner_confirmations()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog SET row_security=off
          SET standard_conforming_strings=on AS {dollar_tag}{body}{dollar_tag}
        """)
        op.execute(f"""
        CREATE OR REPLACE FUNCTION {private_qualified}.lock_confirmation_patient(subject_id pg_catalog.int4)
        RETURNS pg_catalog.bool LANGUAGE plpgsql SET search_path=pg_catalog SET row_security=off
          SET standard_conforming_strings=on AS {dollar_tag}{lock_body}{dollar_tag}
        """)
        schema_literal = schema.replace("'", "''")
        private_literal = private.replace("'", "''")
        tag = "$owner_confirmation_owner$"
        while tag in schema_literal:
            tag = tag[:-1] + "_x$"
        op.execute(f"""DO {tag} DECLARE trusted_owner name; BEGIN
          SELECT r.rolname INTO STRICT trusted_owner FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{schema_literal}';
          EXECUTE pg_catalog.format('ALTER FUNCTION %I.invalidate_patient_owner_confirmations() OWNER TO %I',
            '{private_literal}', trusted_owner);
          EXECUTE pg_catalog.format('ALTER FUNCTION %I.lock_confirmation_patient(pg_catalog.int4) OWNER TO %I',
            '{private_literal}', trusted_owner);
        END {tag}""")
        op.execute(f"REVOKE ALL ON FUNCTION {private_qualified}.invalidate_patient_owner_confirmations() FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {private_qualified}.lock_confirmation_patient(pg_catalog.int4) FROM PUBLIC")
        op.execute(f"DROP TRIGGER IF EXISTS trg_patient_owner_confirmation_context ON {qualified}.patients")
        op.execute(f"""
        CREATE TRIGGER trg_patient_owner_confirmation_context
        AFTER UPDATE OF user_id, is_deleted ON {qualified}.patients
        FOR EACH ROW EXECUTE FUNCTION {private_qualified}.invalidate_patient_owner_confirmations()
        """)
        op.execute("SELECT pg_catalog.set_config('standard_conforming_strings', pg_catalog.current_setting('patient_confirmation.saved_standard_strings'), true)")
    elif dialect == "sqlite":
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_patient_owner_confirmation_context
        AFTER UPDATE OF user_id, is_deleted ON patients FOR EACH ROW
        WHEN OLD.user_id IS NOT NEW.user_id OR OLD.is_deleted IS NOT NEW.is_deleted
        BEGIN
          UPDATE visit_confirmation_generation_clock SET value=value+1 WHERE id=1;
          UPDATE visits SET
            confirmation_context_epoch=(SELECT value FROM visit_confirmation_generation_clock WHERE id=1),
            confirmation_token=NULL, confirmation_expires_at=NULL,
            reminder_sent_at=NULL, reminder_generation=COALESCE(reminder_generation,0)+1
          WHERE patient_id=NEW.id AND (confirmation_token IS NOT NULL OR status IN ('pending_confirmation','confirmation_processing'));
        END
        """)
    else:
        raise RuntimeError(f"Unsupported confirmation dialect: {dialect}")


def downgrade() -> None:
    # Keep the fence until 0102 is removed: restoring the vulnerable trigger
    # behaviour on ordinary 0116 rollback would make live links unsafe.
    pass
