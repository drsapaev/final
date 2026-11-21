"""Provision one explicit trusted backend LOGIN role for 0117.

Run only as the trusted schema/table owner (or a DBA), after draining traffic
while ACLs and policies are inspected. This script is never invoked on startup.
"""
from __future__ import annotations

import argparse
import hashlib
import os

from sqlalchemy import create_engine, text

_EXPECTED_TRIGGER_BODY = """
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'invitation evidence is immutable'; END IF;
          IF ROW(NEW.visit_id_snapshot, NEW.patient_id_snapshot, NEW.owner_generation,
                 NEW.context_epoch, NEW.token_digest, NEW.channel, NEW.telegram_link_id,
                 NEW.telegram_link_epoch, NEW.issuer_actor_id, NEW.issuer_key_digest, NEW.issuer_fingerprint, NEW.created_at)
             IS DISTINCT FROM ROW(OLD.visit_id_snapshot, OLD.patient_id_snapshot, OLD.owner_generation,
                 OLD.context_epoch, OLD.token_digest, OLD.channel, OLD.telegram_link_id,
                 OLD.telegram_link_epoch, OLD.issuer_actor_id, OLD.issuer_key_digest, OLD.issuer_fingerprint, OLD.created_at)
             OR (NEW.visit_id IS DISTINCT FROM OLD.visit_id AND NEW.visit_id IS NOT NULL)
             OR (NEW.patient_id IS DISTINCT FROM OLD.patient_id AND NEW.patient_id IS NOT NULL)
             OR (NEW.state IS DISTINCT FROM OLD.state AND NOT
               ((OLD.state='pending' AND NEW.state IN ('unknown','sent','cancelled'))
                OR (OLD.state='unknown' AND NEW.state='sent')))
             OR (NEW.dispatch_nonce_digest IS DISTINCT FROM OLD.dispatch_nonce_digest AND NOT
               ((OLD.state='pending' AND NEW.state='unknown' AND OLD.dispatch_nonce_digest IS NULL AND NEW.dispatch_nonce_digest IS NOT NULL)
                OR (OLD.state='unknown' AND NEW.state='unknown' AND OLD.dispatch_nonce_digest IS NOT NULL AND NEW.dispatch_nonce_digest IS NULL)))
             OR (OLD.state='unknown' AND NEW.state='sent' AND OLD.dispatch_nonce_digest IS NOT NULL) THEN
            RAISE EXCEPTION 'invalid invitation transition';
          END IF;
          RETURN NEW;
        END
""".strip()

_EXPECTED_ISSUER_TRIGGER_BODY = """
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'invitation issuer evidence is immutable'; END IF;
          IF ROW(NEW.delivery_id,NEW.actor_user_id_snapshot,NEW.actor_auth_epoch,NEW.requester_type,
                 NEW.doctor_id_snapshot,NEW.doctor_generation,NEW.expires_at,NEW.cipher_version,NEW.jti_ciphertext)
             IS DISTINCT FROM ROW(OLD.delivery_id,OLD.actor_user_id_snapshot,OLD.actor_auth_epoch,OLD.requester_type,
                 OLD.doctor_id_snapshot,OLD.doctor_generation,OLD.expires_at,OLD.cipher_version,OLD.jti_ciphertext)
             OR (NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id AND NEW.actor_user_id IS NOT NULL)
             OR (NEW.doctor_id IS DISTINCT FROM OLD.doctor_id AND NEW.doctor_id IS NOT NULL) THEN
            RAISE EXCEPTION 'invalid invitation issuer mutation';
          END IF;
          RETURN NEW;
        END
""".strip()


class ProvisionError(RuntimeError):
    pass


def _require(value, message):
    if not value:
        raise ProvisionError(message)


def provision(engine, schema: str, role: str) -> None:
    _require(engine.dialect.name == "postgresql" and schema and role, "Explicit PostgreSQL schema and role required")
    _require("\x00" not in schema + role and role.lower() not in {"anon", "authenticated", "public"}, "Invalid backend role")
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(role)
    table = f"{qs}.visit_invitation_deliveries"
    auth_table = f"{qs}.visit_invitation_issuer_auth"
    price_table = f"{qs}.visit_invitation_price_approval_auth"
    recovery_table = f"{qs}.visit_invitation_approval_recoveries"
    policies = {
        "invitation_backend_select": ("SELECT", "USING (true)"),
        "invitation_backend_insert": ("INSERT", "WITH CHECK (state='pending' AND dispatch_nonce_digest IS NULL)"),
        "invitation_backend_update": ("UPDATE", "USING (true) WITH CHECK (true)"),
    }
    with engine.begin() as db:
        db.execute(text("SET LOCAL search_path=pg_catalog"))
        target = db.execute(text("""
          SELECT oid,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
          FROM pg_catalog.pg_roles WHERE rolname=:role
        """), {"role": role}).mappings().first()
        _require(target is not None and target["rolcanlogin"] and not any(target[k] for k in
                 ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication")), "Backend must be a nonadministrative LOGIN role")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
          WHERE (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication)
          AND pg_catalog.pg_has_role(:target,r.oid,'MEMBER'))
        """), {"target": target["oid"]}).scalar_one(), "Backend has an elevated role membership")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid<>:target
          AND pg_catalog.pg_has_role(r.oid,:target,'MEMBER'))
        """), {"target": target["oid"]}).scalar_one(), "Other roles may not inherit backend privileges")
        namespace = db.execute(text("SELECT oid,nspowner FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).mappings().first()
        _require(namespace is not None and schema not in {"pg_catalog", "information_schema"}, "Trusted application schema required")
        _require(target["oid"] != namespace["nspowner"], "Backend must not own schema")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
          LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
          WHERE n.oid=:oid AND a.privilege_type='CREATE' AND a.grantee<>n.nspowner)
        """), {"oid": namespace["oid"]}).scalar_one(), "Schema CREATE is granted beyond its owner")
        db.exec_driver_sql(f"LOCK TABLE {table}, {auth_table}, {price_table}, {recovery_table} IN ACCESS EXCLUSIVE MODE")
        relation = db.execute(text("""
          SELECT c.oid,c.relowner,c.relrowsecurity,c.relforcerowsecurity,
                 pg_catalog.pg_get_userbyid(c.relowner) AS owner
          FROM pg_catalog.pg_class c WHERE c.oid=pg_catalog.to_regclass(:table) AND c.relkind='r'
        """), {"table": table}).mappings().first()
        _require(relation is not None and relation["relrowsecurity"], "RLS table required")
        _require(relation["relowner"] != target["oid"] and not db.execute(text(
            "SELECT pg_catalog.pg_has_role(:target,:owner,'MEMBER')"),
            {"target": target["oid"], "owner": relation["relowner"]}).scalar_one(), "Backend may not own or inherit the table")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper
            AND r.oid NOT IN (:schema_owner,:table_owner)
            AND (pg_catalog.pg_has_role(r.oid,:schema_owner,'MEMBER')
              OR pg_catalog.pg_has_role(r.oid,:table_owner,'MEMBER')))
        """), {"schema_owner": namespace["nspowner"], "table_owner": relation["relowner"]}).scalar_one(), "An untrusted role can assume ownership")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
            WHERE pg_catalog.lower(r.rolname) IN ('anon','authenticated')
              AND (r.rolsuper OR r.rolbypassrls OR pg_catalog.pg_has_role(r.oid,:target,'MEMBER')))
        """), {"target": target["oid"]}).scalar_one(), "Untrusted role can bypass or inherit backend privileges")
        caller = db.execute(text("SELECT current_user, rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user")).first()
        _require(caller and (caller.rolsuper or caller.current_user == relation["owner"]), "Provisioner must be trusted table owner or DBA")
        trigger = db.execute(text("""
          SELECT t.tgenabled,t.tgtype,p.proowner,p.prosecdef,p.proconfig,p.prosrc
          FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
          WHERE t.tgrelid=:oid AND t.tgname='trg_protect_visit_invitation' AND NOT t.tgisinternal
        """), {"oid": relation["oid"]}).mappings().first()
        _require(trigger and trigger["tgenabled"] == "O" and trigger["tgtype"] == 27
                 and trigger["proowner"] == relation["relowner"] and not trigger["prosecdef"]
                 and trigger["proconfig"] == ["search_path=pg_catalog"]
                 and trigger["prosrc"].strip() == _EXPECTED_TRIGGER_BODY,
                 "Invitation immutable evidence trigger is missing or changed")
        auth = db.execute(text("""
          SELECT c.oid,c.relowner,c.relrowsecurity FROM pg_catalog.pg_class c
          WHERE c.oid=pg_catalog.to_regclass(:table) AND c.relkind='r'
        """), {"table": auth_table}).mappings().first()
        _require(auth and auth["relowner"] == relation["relowner"] and auth["relrowsecurity"],
                 "Issuer evidence table owner/RLS is invalid")
        auth_trigger = db.execute(text("""
          SELECT t.tgenabled,t.tgtype,p.proowner,p.prosecdef,p.proconfig,p.prosrc
          FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
          WHERE t.tgrelid=:oid AND t.tgname='trg_protect_invitation_issuer_auth' AND NOT t.tgisinternal
        """), {"oid": auth["oid"]}).mappings().first()
        _require(auth_trigger and auth_trigger["tgenabled"] == "O" and auth_trigger["tgtype"] == 27
                 and auth_trigger["proowner"] == relation["relowner"] and not auth_trigger["prosecdef"]
                 and auth_trigger["proconfig"] == ["search_path=pg_catalog"]
                 and auth_trigger["prosrc"].strip() == _EXPECTED_ISSUER_TRIGGER_BODY,
                 "Issuer immutable evidence trigger is missing or changed")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c,
          LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
          WHERE c.oid=:oid AND (a.grantee NOT IN (c.relowner,:target)
            OR (a.grantee=:target AND (a.privilege_type NOT IN ('SELECT','INSERT') OR a.is_grantable))))
        """), {"oid": auth["oid"], "target": target["oid"]}).scalar_one(), "Unexpected issuer evidence ACL")
        _require(not db.execute(text("""
          SELECT pg_catalog.has_table_privilege(:role,:table,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
             OR pg_catalog.has_any_column_privilege(:role,:table,'UPDATE,REFERENCES')
        """), {"role": role, "table": auth_table}).scalar_one(), "Backend has unsafe issuer evidence privileges")
        _require(not db.execute(text("""
          SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_class c,
          LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
          WHERE c.oid=:oid AND a.grantee NOT IN (c.relowner,:target))
        """), {"oid": relation["oid"], "target": target["oid"]}).scalar_one(), "Unexpected existing table ACL")
        _require(not db.execute(text("""
          SELECT pg_catalog.has_table_privilege(:role,:table,'DELETE,TRUNCATE,REFERENCES,TRIGGER')
             OR pg_catalog.has_any_column_privilege(:role,:table,'REFERENCES')
        """), {"role": role, "table": table}).scalar_one(), "Backend has unsafe inherited table permissions")
        existing = db.execute(text("""
          SELECT p.polname,p.polcmd,p.polpermissive,p.polroles,
                 pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expr,
                 pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
          FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
        """), {"oid": relation["oid"]}).mappings().all()
        _require({row["polname"] for row in existing}.issubset(policies), "Unexpected existing invitation policy")
        # Generate a comparison policy under a savepoint, then compare the
        # database's own normalized expression to every pre-existing policy.
        for name, (command, predicate) in policies.items():
            old = next((row for row in existing if row["polname"] == name), None)
            if old:
                nested = db.begin_nested()
                db.exec_driver_sql(f"CREATE POLICY invitation_policy_probe ON {table} FOR {command} TO {qr} {predicate}")
                expected = db.execute(text("""
                  SELECT p.polcmd,p.polpermissive,p.polroles,
                         pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expr,
                         pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
                  FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid AND p.polname='invitation_policy_probe'
                """), {"oid": relation["oid"]}).mappings().one()
                nested.rollback()
                _require(all(old[key] == expected[key] for key in expected), "Existing policy differs from reviewed policy")
            else:
                db.exec_driver_sql(f"CREATE POLICY {quote(name)} ON {table} FOR {command} TO {qr} {predicate}")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {qs} TO {qr}")
        db.exec_driver_sql(f"GRANT SELECT,INSERT,UPDATE ON {table} TO {qr}")
        sequence = db.execute(text("SELECT pg_catalog.pg_get_serial_sequence(:table,'id')"), {"table": table}).scalar_one()
        _require(bool(sequence), "Invitation ID sequence missing")
        # pg_get_serial_sequence returns a catalog-quoted qualified name.
        db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {sequence} TO {qr}")
        auth_policies = {
            "invitation_issuer_backend_select": ("SELECT", "USING (true)"),
            "invitation_issuer_backend_insert": ("INSERT", "WITH CHECK (true)"),
        }
        existing_auth = db.execute(text("""
          SELECT p.polname,p.polcmd,p.polpermissive,p.polroles,
                 pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expr,
                 pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
          FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
        """), {"oid": auth["oid"]}).mappings().all()
        _require({row["polname"] for row in existing_auth}.issubset(auth_policies), "Unexpected issuer evidence policy")
        for name, (command, predicate) in auth_policies.items():
            old = next((row for row in existing_auth if row["polname"] == name), None)
            if old:
                nested = db.begin_nested()
                db.exec_driver_sql(f"CREATE POLICY issuer_policy_probe ON {auth_table} FOR {command} TO {qr} {predicate}")
                expected = db.execute(text("""
                  SELECT p.polcmd,p.polpermissive,p.polroles,
                         pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expr,
                         pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
                  FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid AND p.polname='issuer_policy_probe'
                """), {"oid": auth["oid"]}).mappings().one()
                nested.rollback()
                _require(all(old[key] == expected[key] for key in expected), "Existing issuer policy differs from reviewed policy")
            else:
                db.exec_driver_sql(f"CREATE POLICY {quote(name)} ON {auth_table} FOR {command} TO {qr} {predicate}")
        db.exec_driver_sql(f"GRANT SELECT,INSERT ON {auth_table} TO {qr}")
        for target_table, trigger_name, trigger_hash, can_update, policy_prefix in (
            (price_table, "trg_protect_invite_price_auth", "78a2afa2aa6eb4592c2c831b80677287c142aafe21931b5af515b39c2886520d", False, "invitation_price"),
            (recovery_table, "trg_protect_invite_recovery", "2ec8880405af4e862d93ec4865c80ab52e1edb35a2e11397a557e0284383e9b3", True, "invitation_recovery"),
        ):
            current = db.execute(text("""
              SELECT c.oid,c.relowner,c.relrowsecurity FROM pg_catalog.pg_class c
              WHERE c.oid=pg_catalog.to_regclass(:table) AND c.relkind='r'
            """), {"table": target_table}).mappings().first()
            _require(current and current["relowner"] == relation["relowner"] and current["relrowsecurity"], "Approval invitation owner/RLS invalid")
            trigger = db.execute(text("""
              SELECT t.tgenabled,t.tgtype,p.proowner,p.prosecdef,p.proconfig,p.prosrc
              FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
              WHERE t.tgrelid=:oid AND t.tgname=:name AND NOT t.tgisinternal
            """), {"oid": current["oid"], "name": trigger_name}).mappings().first()
            _require(trigger and trigger["tgenabled"] == "O" and trigger["tgtype"] == 27
                     and trigger["proowner"] == relation["relowner"] and not trigger["prosecdef"]
                     and trigger["proconfig"] == ["search_path=pg_catalog"]
                     and hashlib.sha256(trigger["prosrc"].strip().encode()).hexdigest() == trigger_hash,
                     "Approval invitation evidence trigger invalid")
            allowed_privileges = {"SELECT", "INSERT", "UPDATE"} if can_update else {"SELECT", "INSERT"}
            acl = db.execute(text("""
              SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_class c,
              LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
              WHERE c.oid=:oid
            """), {"oid": current["oid"]}).mappings().all()
            _require(all(a["grantee"] == relation["relowner"] or
                         (a["grantee"] == target["oid"] and a["privilege_type"] in allowed_privileges and not a["is_grantable"])
                         for a in acl), "Unexpected approval invitation ACL")
            forbidden = "DELETE,TRUNCATE,REFERENCES,TRIGGER" if can_update else "UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER"
            _require(not db.execute(text("SELECT pg_catalog.has_table_privilege(:role,:table,:priv)"),
                 {"role": role, "table": target_table, "priv": forbidden}).scalar_one(), "Unsafe approval invitation privileges")
            specifications = {
                f"{policy_prefix}_select": ("SELECT", "USING (true)"),
                f"{policy_prefix}_insert": ("INSERT", "WITH CHECK (true)" if not can_update else "WITH CHECK (state='pending')"),
            }
            if can_update:
                specifications[f"{policy_prefix}_update"] = ("UPDATE", "USING (true) WITH CHECK (true)")
            existing_policies = db.execute(text("""
              SELECT p.polname,p.polcmd,p.polpermissive,p.polroles,
                     pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expr,
                     pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
              FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
            """), {"oid": current["oid"]}).mappings().all()
            _require({p["polname"] for p in existing_policies}.issubset(specifications), "Unexpected approval invitation policy")
            for name, (command, predicate) in specifications.items():
                old = next((p for p in existing_policies if p["polname"] == name), None)
                if old:
                    nested = db.begin_nested()
                    db.exec_driver_sql(f"CREATE POLICY approval_policy_probe ON {target_table} FOR {command} TO {qr} {predicate}")
                    expected = db.execute(text("""
                      SELECT p.polcmd,p.polpermissive,p.polroles,pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expr,
                             pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
                      FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid AND p.polname='approval_policy_probe'
                    """), {"oid": current["oid"]}).mappings().one()
                    nested.rollback()
                    _require(all(old[key] == expected[key] for key in expected), "Existing approval invitation policy differs")
                else:
                    db.exec_driver_sql(f"CREATE POLICY {quote(name)} ON {target_table} FOR {command} TO {qr} {predicate}")
            db.exec_driver_sql(f"GRANT {','.join(sorted(allowed_privileges))} ON {target_table} TO {qr}")
            if can_update:
                sequence = db.execute(text("SELECT pg_catalog.pg_get_serial_sequence(:table,'id')"), {"table": target_table}).scalar_one()
                _require(bool(sequence), "Approval recovery sequence missing")
                db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {sequence} TO {qr}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    _require(bool(url), "DATABASE_URL is required")
    engine = create_engine(url)
    try:
        provision(engine, args.schema, args.role)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
