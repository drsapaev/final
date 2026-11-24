"""Align the unprovisioned booking lock with its capability namespace owner."""

import hashlib

import sqlalchemy as sa

from alembic import op

revision = "0161_booking_lock_owner"
down_revision = "0160_service_catalog_audit_acl"
branch_labels = None
depends_on = None

_LOCK_SIGNATURE = "lock_booking_patient(pg_catalog.int4)"


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError(
            "Booking lock ownership requires an online PostgreSQL catalog"
        )

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if (
        not isinstance(schema, str)
        or not schema
        or "\0" in schema
        or len(schema.encode()) > 63
    ):
        raise RuntimeError("Trusted booking schema required")
    digest = hashlib.sha256(
        b"clinic-capability-schema-v1\0" + schema.encode()
    ).hexdigest()
    private = "clinic_internal_" + digest[:32]
    preparer = context.dialect.identifier_preparer
    quoted_private = preparer.quote_schema(private)
    qualified_lock = f"{quoted_private}.{_LOCK_SIGNATURE}"
    patients = f"{preparer.quote_schema(schema)}.patients"
    # Frozen body from 0140. The provisioner changes ownership and execution
    # settings while retaining this definition.
    reviewed_body = f"""
      DECLARE active_subject pg_catalog.bool;
      BEGIN
        IF subject_id IS NULL OR subject_id <= 0 THEN
          RAISE EXCEPTION 'invalid booking subject';
        END IF;
        SELECT p.is_deleted IS FALSE INTO active_subject FROM {patients} p
          WHERE p.id=subject_id FOR NO KEY UPDATE;
        RETURN active_subject IS TRUE;
      END """

    connection = op.get_bind()
    lock = (
        connection.execute(
            sa.text("""
            SELECT p.proowner = app.nspowner AS schema_owned, schema_owner.rolname AS schema_owner,
                   routine_owner.rolname AS routine_owner, p.prosecdef, p.proconfig,
                   NOT (routine_owner.rolcanlogin OR routine_owner.rolsuper
                        OR routine_owner.rolbypassrls OR routine_owner.rolcreaterole
                        OR routine_owner.rolcreatedb OR routine_owner.rolreplication) AS scoped_role,
                   NOT EXISTS (
                       SELECT 1 FROM pg_catalog.aclexplode(
                           COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
                       ) acl WHERE acl.grantee <> p.proowner
                   ) AS owner_only_acl
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace private ON private.oid = p.pronamespace
            JOIN pg_catalog.pg_namespace app ON app.nspname = :schema
                AND private.nspowner = app.nspowner
            JOIN pg_catalog.pg_roles schema_owner ON schema_owner.oid = app.nspowner
            JOIN pg_catalog.pg_roles routine_owner ON routine_owner.oid = p.proowner
            JOIN pg_catalog.pg_language language ON language.oid = p.prolang
            WHERE private.nspname = :private AND p.oid = pg_catalog.to_regprocedure(:signature)
              AND p.prokind = 'f' AND p.provolatile = 'v' AND language.lanname = 'plpgsql'
              AND p.proargnames = ARRAY['subject_id'] AND p.prorettype = 'pg_catalog.bool'::pg_catalog.regtype
              AND p.prosrc = :body
        """),
            {
                "schema": schema,
                "private": private,
                "signature": qualified_lock,
                "body": reviewed_body,
            },
        )
        .mappings()
        .one_or_none()
    )
    if lock is None:
        raise RuntimeError("Booking lock differs from the reviewed function")

    settings = {"search_path=pg_catalog", "standard_conforming_strings=on"}
    if lock["prosecdef"]:
        registered = connection.scalar(
            sa.text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM {quoted_private}.clinic_capability_role_profile
                    WHERE role_name = :owner AND role_kind = 'capability_owner'
                )
            """),
            {"owner": lock["routine_owner"]},
        )
        if set(lock["proconfig"] or ()) != settings | {"row_security=on"} or not (
            not lock["schema_owned"] and lock["scoped_role"] and registered
        ):
            raise RuntimeError("Booking lock has an unrecognized capability profile")
        return

    if (
        set(lock["proconfig"] or ()) != settings | {"row_security=off"}
        or not lock["owner_only_acl"]
    ):
        raise RuntimeError("Booking lock has unexpected permissions or settings")
    if not lock["schema_owned"]:
        quoted_owner = preparer.quote_identifier(lock["schema_owner"])
        op.execute(f"ALTER FUNCTION {qualified_lock} OWNER TO {quoted_owner}")


def downgrade() -> None:
    """Keep the namespace owner alignment on rollback."""
