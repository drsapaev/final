"""Keep confirmation invalidation compatible with the provisioned 0118 fence.

An already-provisioned function must be replaced by the migration
administrator who can alter that function without changing its owner.
"""

import importlib.util
from pathlib import Path

from alembic import op

revision = "0141_confirmation_finance"
down_revision = "0140_booking_patient_lock"
branch_labels = None
depends_on = None

# SHA-256 of the stripped 0118 financial_visit_membership_fence function body.
_MEMBERSHIP_BODY_SHA256 = "1a556c210d6e0194873adb4e866669bde98096bf5d72890dd13641d8013c807f"
_TRIGGER_OWNER_CHECK_END = "                   (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)))"


def reviewed_financial_trigger(qualified: str, private: str) -> str:
    """Identify one approved AFTER trigger using the surrounding t and p aliases."""
    visits = f"{qualified}.visits".replace("'", "''")
    # The capability namespace is derived from the application schema as lowercase hex.
    signature = f"{private}.financial_visit_membership_fence()"
    return f"""
      t.tgrelid='{visits}'::pg_catalog.regclass
      AND t.tgname='trg_financial_visit_membership' AND t.tgtype=29
      AND t.tgenabled IN ('O','A') AND t.tgqual IS NULL AND t.tgnargs=0
      AND t.tgattr::text='' AND t.tgoldtable IS NULL AND t.tgnewtable IS NULL
      AND p.oid=pg_catalog.to_regprocedure('{signature}')
      AND p.prokind='f' AND p.provolatile='v' AND p.prosecdef AND NOT p.proretset
      AND p.prorettype='pg_catalog.trigger'::pg_catalog.regtype
      AND p.prolang=(SELECT oid FROM pg_catalog.pg_language WHERE lanname='plpgsql')
      AND pg_catalog.cardinality(p.proconfig)=2
      AND p.proconfig @> ARRAY['search_path=pg_catalog','row_security=on']::text[]
      AND pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.btrim(p.prosrc, E' \\t\\r\\n'), 'UTF8'))
        =pg_catalog.decode('{_MEMBERSHIP_BODY_SHA256}', 'hex')
      AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) acl
        WHERE acl.grantee<>p.proowner
      )
      AND EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles owner WHERE owner.oid=p.proowner
          AND NOT (owner.rolcanlogin OR owner.rolsuper OR owner.rolbypassrls
            OR owner.rolcreaterole OR owner.rolcreatedb OR owner.rolreplication)
          AND NOT pg_catalog.has_schema_privilege(owner.oid,p.pronamespace,'CREATE')
          AND NOT pg_catalog.has_table_privilege(owner.oid,t.tgrelid,'TRIGGER')
          AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles member WHERE member.oid<>owner.oid
              AND (pg_catalog.pg_has_role(owner.oid,member.oid,'MEMBER')
                OR (NOT member.rolsuper AND pg_catalog.pg_has_role(member.oid,owner.oid,'MEMBER')))
          )
      )"""


def owner_function_body(original: str, qualified: str, private: str) -> str:
    if original.count(_TRIGGER_OWNER_CHECK_END) != 1:
        raise RuntimeError("Reviewed confirmation trigger owner check is unavailable")
    # The 0118 body exits for confirmation-only updates before touching encounters.
    # Any additional trigger or changed body still fails the original owner check.
    return original.replace(
        _TRIGGER_OWNER_CHECK_END,
        _TRIGGER_OWNER_CHECK_END[:-1]
        + f"\n                AND NOT COALESCE(({reviewed_financial_trigger(qualified, private)}),false))",
    )


def _reviewed_bodies(qualified: str, schema: str) -> tuple[str, str, str]:
    # Reuse the immutable predecessor's template without importing runtime code.
    spec = importlib.util.spec_from_file_location(
        "confirmation_0116", Path(__file__).with_name("0116_patient_owner_confirmation.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Reviewed confirmation migration is unavailable")
    original_migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original_migration)
    private = original_migration._capability_schema_name(schema)
    original = original_migration.owner_function_body(qualified, private)
    return private, original, owner_function_body(original, qualified, private)


def _replace_function(*, upgrade: bool) -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported confirmation trigger dialect")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted confirmation schema required")
    qualified = context.dialect.identifier_preparer.quote_schema(schema)
    private, original, revised = _reviewed_bodies(qualified, schema)
    old, new = (original, revised) if upgrade else (revised, original)
    outer_tag, body_tag = "$confirmation_replace$", "$confirmation_body$"
    while outer_tag in old or outer_tag in new:
        outer_tag = outer_tag[:-1] + "_x$"
    while body_tag in old or body_tag in new:
        body_tag = body_tag[:-1] + "_x$"

    # CREATE OR REPLACE keeps the function OID, owner, trigger binding and ACL.
    # Preserve the unprovisioned and provisioned configurations where installed.
    op.execute(f"""
      DO {outer_tag}
      DECLARE existing_body text; is_definer boolean; settings_match boolean;
      BEGIN
        SELECT p.prosrc, p.prosecdef, pg_catalog.cardinality(p.proconfig)=3
          AND p.proconfig @> ARRAY['search_path=pg_catalog','standard_conforming_strings=on',
            CASE WHEN p.prosecdef THEN 'row_security=on' ELSE 'row_security=off' END]::text[]
          INTO STRICT existing_body, is_definer, settings_match
        FROM pg_catalog.pg_proc p
        WHERE p.oid=pg_catalog.to_regprocedure('{private}.invalidate_patient_owner_confirmations()')
          AND p.prokind='f' AND p.provolatile='v' AND NOT p.proretset
          AND p.prorettype='pg_catalog.trigger'::pg_catalog.regtype
          AND p.prolang=(SELECT oid FROM pg_catalog.pg_language WHERE lanname='plpgsql');
        IF existing_body IS DISTINCT FROM {body_tag}{old}{body_tag} OR settings_match IS NOT TRUE THEN
          RAISE EXCEPTION 'Confirmation trigger differs from the reviewed revision';
        END IF;
        EXECUTE pg_catalog.format(
          'CREATE OR REPLACE FUNCTION %I.invalidate_patient_owner_confirmations() '
          'RETURNS pg_catalog.trigger LANGUAGE plpgsql SECURITY %s '
          'SET search_path=pg_catalog SET row_security=%s SET standard_conforming_strings=on AS %L',
          '{private}', CASE WHEN is_definer THEN 'DEFINER' ELSE 'INVOKER' END,
          CASE WHEN is_definer THEN 'on' ELSE 'off' END, {body_tag}{new}{body_tag}
        );
      END {outer_tag}
    """)


def upgrade() -> None:
    _replace_function(upgrade=True)


def downgrade() -> None:
    _replace_function(upgrade=False)
