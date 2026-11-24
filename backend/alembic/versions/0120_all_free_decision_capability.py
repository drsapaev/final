"""Add a narrowly granted all-free decision primitive.

This primitive is not an HTTP authorization or financial fence. The trusted
backend must validate the signed session, hold the complete group and receipt
locks, check the request baseline and atomically requote before committing.
No runtime role is granted access by this migration.
"""
from __future__ import annotations

import hashlib
import json

from alembic import context as alembic_context
from alembic import op

revision = "0120_allfree_decision"
down_revision = "0119_click_receipt"
branch_labels = None
depends_on = None


def _private_name(schema: str) -> str:
    # Frozen v1 algorithm: migration history must not depend on runtime code.
    if not isinstance(schema, str) or not schema or "\0" in schema:
        raise ValueError("Invalid application schema")
    raw = schema.encode("utf-8")
    if len(raw) > 63:
        raise ValueError("Invalid application schema")
    return "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + raw).hexdigest()[:32]


def _schemas():
    context = op.get_context()
    schema = context.version_table_schema
    if not schema and not context.as_sql:
        schema = op.get_bind().dialect.default_schema_name
    if not isinstance(schema, str) or not schema:
        raise RuntimeError("An explicit trusted application schema is required")
    quote = context.dialect.identifier_preparer.quote_identifier
    return schema, _private_name(schema), quote(schema), quote(_private_name(schema))


def _trusted_owner_members() -> tuple[str, ...]:
    value = op.get_context().opts.get("trusted_capability_owner_members")
    if value is None:
        try:
            values = [arg.partition("=")[2] for arg in alembic_context.get_x_argument()
                      if arg.partition("=")[0] == "capability_owner_members"]
            if len(values) > 1:
                raise RuntimeError("Invalid capability owner-member allowlist")
            value = values[0] if values else None
        except (AttributeError, NameError):
            value = None
    if value is None:
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            raise RuntimeError("Invalid capability owner-member allowlist") from None
    if not isinstance(value, (list, tuple)):
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
    if len(set(names)) != len(names):
        raise RuntimeError("Invalid capability owner-member allowlist")
    return tuple(names)


def _check_namespace(schema: str, private: str, qp: str) -> None:
    # This migration requires maintenance provisioning to have been drained
    # first: do not guess a previously provisioned role profile. 0112 created
    # these owner-only identity tables in the same trusted schema boundary.
    app_literal = schema.replace("'", "''")
    private_literal = private.replace("'", "''")
    members = [name.replace("'", "''") for name in _trusted_owner_members()]
    member_array = "ARRAY[" + ",".join("'" + name + "'" for name in members) + "]::text[]"
    tag = "$allfree_namespace$"
    while tag in app_literal or any(tag in name for name in members):
        tag = tag[:-1] + "_x$"
    op.execute("SELECT pg_catalog.set_config('allfree_0120.saved_strings', pg_catalog.current_setting('standard_conforming_strings'), true)")
    op.execute("SET LOCAL standard_conforming_strings=on")
    op.execute(f"""DO {tag}
    DECLARE owner_id oid; namespace_id oid; n integer;
    BEGIN
      SELECT nspowner INTO STRICT owner_id FROM pg_catalog.pg_namespace WHERE nspname='{app_literal}';
      SELECT oid INTO STRICT namespace_id FROM pg_catalog.pg_namespace
        WHERE nspname='{private_literal}' AND nspowner=owner_id;
      IF NOT pg_catalog.pg_has_role(CURRENT_USER, owner_id, 'USAGE') THEN
        RAISE EXCEPTION 'Untrusted capability owner';
      END IF;
      IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid<>owner_id
                   AND pg_catalog.pg_has_role(r.oid,owner_id,'MEMBER')
                   AND (r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication
                     OR NOT EXISTS (SELECT 1 FROM pg_catalog.unnest({member_array}) expected(name)
                       WHERE pg_catalog.convert_to(r.rolname::text,'UTF8')=pg_catalog.convert_to(expected.name,'UTF8'))))
         OR EXISTS (SELECT 1 FROM pg_catalog.unnest({member_array}) expected(name)
              WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid<>owner_id
                AND pg_catalog.pg_has_role(r.oid,owner_id,'MEMBER')
                AND pg_catalog.convert_to(r.rolname::text,'UTF8')=pg_catalog.convert_to(expected.name,'UTF8')))
         OR EXISTS (SELECT 1 FROM pg_catalog.pg_namespace ns,
             LATERAL pg_catalog.aclexplode(COALESCE(ns.nspacl,pg_catalog.acldefault('n',ns.nspowner))) a
             WHERE ns.oid=namespace_id AND a.grantee<>owner_id)
         OR EXISTS (SELECT 1 FROM pg_catalog.pg_class c,
             LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
             WHERE c.relnamespace=namespace_id AND c.relname IN ('clinic_capability_namespace','clinic_capability_role_profile')
               AND (c.relowner<>owner_id OR a.grantee<>owner_id))
         OR EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
             WHERE c.relnamespace=namespace_id AND c.relname IN ('clinic_capability_namespace','clinic_capability_role_profile')
               AND a.attacl IS NOT NULL)
      THEN RAISE EXCEPTION 'Capability namespace is not owner-only'; END IF;
      SELECT count(*) INTO n FROM pg_catalog.pg_class c WHERE c.relnamespace=namespace_id
        AND c.relname IN ('clinic_capability_namespace','clinic_capability_role_profile')
        AND c.relkind='r' AND c.relowner=owner_id;
      IF n<>2 OR (SELECT count(*) FROM {qp}.clinic_capability_namespace)<>1
        OR NOT EXISTS (SELECT 1 FROM {qp}.clinic_capability_namespace
          WHERE id=1 AND format_version=1 AND application_schema='{app_literal}' AND private_schema='{private_literal}')
        OR EXISTS (SELECT 1 FROM {qp}.clinic_capability_role_profile)
      THEN RAISE EXCEPTION 'Capability namespace identity or role profile mismatch'; END IF;
    END {tag}""")


def _restore_strings() -> None:
    op.execute("SELECT pg_catalog.set_config('standard_conforming_strings', pg_catalog.current_setting('allfree_0120.saved_strings'), true)")


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported all-free decision dialect")
    schema, private, qa, qp = _schemas()
    _check_namespace(schema, private, qp)
    # The caller's outer transaction owns authorization, locking and audit.
    # The function rechecks the live identity and performs one CAS + event.
    op.execute(f"""
      CREATE FUNCTION {qp}.decide_all_free(
        p_request_id integer, p_action text, p_kind text, p_actor_id integer,
        p_auth_epoch bigint, p_visit_id integer, p_patient_id integer,
        p_encounter_id integer, p_request_epoch bigint, p_encounter_generation bigint,
        p_final_visit_epoch bigint
      ) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog SET row_security=on AS $$
      DECLARE actor_role text; actor_super boolean; req {qa}.all_free_requests%ROWTYPE;
              next_status text; event_id bigint;
      BEGIN
        IF p_request_id IS NULL OR p_request_id<=0 OR p_actor_id IS NULL OR p_actor_id<=0
           OR p_auth_epoch IS NULL OR p_auth_epoch<0 OR p_visit_id IS NULL OR p_visit_id<=0
           OR p_patient_id IS NULL OR p_patient_id<=0 OR p_encounter_id IS NULL OR p_encounter_id<=0
           OR p_request_epoch IS NULL OR p_request_epoch<=0 OR p_encounter_generation IS NULL OR p_encounter_generation<=0
           OR p_final_visit_epoch IS NULL OR p_final_visit_epoch<=0
           OR p_action IS NULL OR p_action NOT IN ('approve','reject')
           OR p_kind IS NULL OR p_kind NOT IN ('admin','policy')
           OR (p_kind='policy' AND p_action<>'approve') THEN
          RAISE EXCEPTION 'Invalid all-free decision';
        END IF;
        SELECT pg_catalog.lower(pg_catalog.btrim(u.role)), u.is_superuser INTO actor_role, actor_super
          FROM {qa}.users u WHERE u.id=p_actor_id AND u.is_active IS TRUE AND u.auth_epoch=p_auth_epoch;
        IF NOT FOUND THEN RAISE EXCEPTION 'All-free actor unavailable'; END IF;
        IF p_kind='admin' AND actor_super IS NOT TRUE AND COALESCE(actor_role,'') NOT IN ('admin','superadmin') THEN
          RAISE EXCEPTION 'All-free actor forbidden';
        END IF;
        SELECT * INTO req FROM {qa}.all_free_requests r WHERE r.id=p_request_id FOR UPDATE NOWAIT;
        IF NOT FOUND OR req.status<>'pending' OR req.visit_id IS DISTINCT FROM p_visit_id
          OR req.patient_id IS DISTINCT FROM p_patient_id OR req.encounter_id IS DISTINCT FROM p_encounter_id
          OR req.visit_id_snapshot IS DISTINCT FROM p_visit_id OR req.patient_id_snapshot IS DISTINCT FROM p_patient_id
          OR req.encounter_id_snapshot IS DISTINCT FROM p_encounter_id
          OR req.visit_context_epoch IS DISTINCT FROM p_request_epoch
          OR req.encounter_generation IS DISTINCT FROM p_encounter_generation
          OR (p_kind='policy' AND (req.policy_auto_approve IS NOT TRUE OR req.requested_by_user_id IS DISTINCT FROM p_actor_id))
          OR NOT EXISTS (SELECT 1 FROM {qa}.visits v JOIN {qa}.encounters e ON e.id=v.encounter_id
               JOIN {qa}.patients p ON p.id=v.patient_id
             WHERE v.id=p_visit_id AND v.patient_id=p_patient_id AND v.encounter_id=p_encounter_id
               AND v.confirmation_context_epoch=p_final_visit_epoch AND e.patient_id=p_patient_id
               AND e.generation=p_encounter_generation AND p.is_deleted IS NOT TRUE)
        THEN RAISE EXCEPTION 'All-free decision context changed'; END IF;
        next_status := CASE p_action WHEN 'approve' THEN 'approved' ELSE 'rejected' END;
        UPDATE {qa}.all_free_requests SET status=next_status, decision_kind=p_kind,
          decision_context_epoch=p_final_visit_epoch, decided_by_user_id=p_actor_id,
          decided_by_user_id_snapshot=p_actor_id, decided_by_role_snapshot=actor_role,
          decided_at=pg_catalog.clock_timestamp() WHERE id=p_request_id AND status='pending';
        IF NOT FOUND THEN RAISE EXCEPTION 'All-free decision context changed'; END IF;
        INSERT INTO {qa}.all_free_request_events
          (request_id,event_type,actor_user_id,actor_user_id_snapshot,actor_role_snapshot)
          VALUES (p_request_id,next_status,p_actor_id,p_actor_id,actor_role) RETURNING id INTO event_id;
        RETURN event_id;
      END $$
    """)
    signature = "integer,text,text,integer,bigint,integer,integer,integer,bigint,bigint,bigint"
    op.execute(f"REVOKE ALL ON FUNCTION {qp}.decide_all_free({signature}) FROM PUBLIC")
    app_literal = schema.replace("'", "''")
    tag = "$allfree_owner$"
    while tag in app_literal:
        tag = tag[:-1] + "_x$"
    op.execute(f"""DO {tag} DECLARE owner_name name; BEGIN
      SELECT r.rolname INTO STRICT owner_name FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{app_literal}';
      EXECUTE pg_catalog.format('ALTER FUNCTION %I.decide_all_free({signature}) OWNER TO %I', '{private}', owner_name);
    END {tag}""")
    _restore_strings()


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported all-free decision dialect")
    schema, private, qa, qp = _schemas()
    _check_namespace(schema, private, qp)
    op.execute("SET LOCAL row_security=off")
    op.execute(f"""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM {qa}.all_free_requests WHERE status IN ('approved','rejected')) THEN
        RAISE EXCEPTION 'All-free decisions exist; downgrade refused';
      END IF;
    END $$""")
    op.execute(f"DROP FUNCTION {qp}.decide_all_free(integer,text,text,integer,bigint,integer,integer,integer,bigint,bigint,bigint)")
    _restore_strings()
