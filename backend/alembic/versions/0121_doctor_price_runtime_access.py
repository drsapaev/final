"""Add owner-only reviewed templates for doctor-price runtime policies.

No backend role is guessed or granted here. A trusted operator provisions the
existing dedicated LOGIN role separately after draining traffic. Runtime must
verify exact policies, ACLs, schema and role before relying on full visibility.
"""
from alembic import op

revision = "0121_doctor_price_access"
down_revision = "0120_allfree_decision"
branch_labels = None
depends_on = None

_TABLES = ("doctor_price_hmac_key_versions", "doctor_price_intents", "doctor_price_intent_keys", "doctor_price_intent_lines")


def _pin_schema():
    context = op.get_context()
    schema = context.version_table_schema
    if not schema and not context.as_sql:
        schema = op.get_bind().dialect.default_schema_name
    if not isinstance(schema, str) or not schema:
        raise RuntimeError("doctor-price capability requires an explicit trusted schema")
    quoted = context.dialect.identifier_preparer.quote_identifier(schema)
    literal = schema.replace("'", "''")
    tag = "$doctor_price_access_guard$"
    while tag in literal:
        tag = tag[:-1] + "_x$"
    table_names = ",".join("'" + name + "'" for name in _TABLES)
    op.execute(f"""DO {tag} DECLARE n integer; BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace s
        WHERE s.nspname='{literal}' AND pg_catalog.pg_has_role(current_user,s.nspowner,'USAGE')
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(
          COALESCE(s.nspacl,pg_catalog.acldefault('n',s.nspowner))) a
          WHERE a.privilege_type='CREATE' AND a.grantee<>s.nspowner))
      THEN RAISE EXCEPTION 'doctor-price capability schema is not trusted'; END IF;
      SELECT count(*) INTO n FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace s ON s.oid=c.relnamespace
      WHERE s.nspname='{literal}' AND c.relname IN ({table_names}) AND c.relkind IN ('r','p')
        AND c.relrowsecurity AND c.relowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user);
      IF n <> 4 THEN RAISE EXCEPTION 'doctor-price tables require one current owner and RLS'; END IF;
    END {tag}""")
    op.execute("SELECT pg_catalog.set_config('doctor_price_access.saved_path', pg_catalog.current_setting('search_path'), true)")
    op.execute(f"SET LOCAL search_path TO {quoted}, pg_catalog, pg_temp")
    return schema


def _restore_schema():
    op.execute("SELECT pg_catalog.set_config('search_path', pg_catalog.current_setting('doctor_price_access.saved_path'), true)")


def upgrade():
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported doctor-price capability dialect")
    _pin_schema()
    for table in _TABLES:
        op.execute(f"CREATE POLICY doctor_price_template_select ON {table} FOR SELECT TO CURRENT_USER USING (true)")
        op.execute(f"CREATE POLICY doctor_price_template_insert ON {table} FOR INSERT TO CURRENT_USER WITH CHECK (true)")
    _restore_schema()


def downgrade():
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported doctor-price capability dialect")
    _pin_schema()
    names = ",".join("'" + name + "'" for name in _TABLES)
    op.execute(f"""DO $doctor_price_downgrade$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
                 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                 WHERE n.nspname=pg_catalog.current_schema() AND c.relname IN ({names})
                   AND p.polname IN ('doctor_price_backend_select','doctor_price_backend_insert'))
      THEN RAISE EXCEPTION 'remove backend price policies before downgrade'; END IF;
    END $doctor_price_downgrade$""")
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY doctor_price_template_insert ON {table}")
        op.execute(f"DROP POLICY doctor_price_template_select ON {table}")
    _restore_schema()
