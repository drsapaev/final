"""Trusted backend visibility and transaction-bound Patient row lock.

Call after actor authorization and before Visit/Encounter locks. The caller
owns transaction completion and any subsequent subject/context rechecks.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.db.trusted_schema import TrustedSchemaUnavailable, pin_application_schema
from app.models.patient import Patient


class PatientSubjectLockError(RuntimeError):
    def __init__(self, *, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def require_patient_subject_visibility(db) -> None:
    """Prove full subject visibility for the trusted nonowner backend."""
    if db.get_bind().dialect.name == "postgresql":
        try:
            pin_application_schema(
                db, schema=settings.TRUSTED_DB_SCHEMA,
                expected_owner=settings.TRUSTED_DB_SCHEMA_OWNER,
                expected_runtime_role=settings.TRUSTED_DB_RUNTIME_ROLE,
                trusted_owner_members=settings.TRUSTED_DB_OWNER_MEMBERS,
                expected_auth_owner=settings.TRUSTED_AUTH_TABLE_OWNER,
                trusted_auth_owner_members=settings.TRUSTED_AUTH_OWNER_MEMBERS,
                trusted_auth_read_roles=settings.TRUSTED_AUTH_READ_ROLES,
                trusted_auth_write_roles=settings.TRUSTED_AUTH_WRITE_ROLES,
                expected_users_owner=settings.TRUSTED_AUTH_USERS_OWNER,
                trusted_users_owner_members=settings.TRUSTED_AUTH_USERS_OWNER_MEMBERS,
                trusted_users_write_roles=settings.TRUSTED_AUTH_USERS_WRITE_ROLES,
            )
            if db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
                raise TrustedSchemaUnavailable("Confirmation requires READ COMMITTED")
            db.execute(text("SET LOCAL lock_timeout='2s'"))
            schema = settings.TRUSTED_DB_SCHEMA
            quote = db.get_bind().dialect.identifier_preparer.quote_identifier
            qualified = quote(schema)
            private_name = capability_schema_name(schema)
            private = quote(private_name)
            db.execute(text("SET LOCAL row_security=on"))
            # Hold relation locks across policy proof and all subsequent reads.
            db.execute(text(f"LOCK TABLE {qualified}.patients, {qualified}.visits IN ACCESS SHARE MODE"))
            trusted = db.execute(text("""
              SELECT count(*)=2 AND COALESCE(bool_and(
                pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'SELECT') AND
                (NOT c.relrowsecurity OR (EXISTS (
                  SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
                    AND p.polpermissive AND p.polcmd IN ('r','*')
                    AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
                    AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
                  AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
                    AND NOT p.polpermissive AND p.polcmd IN ('r','*') AND
                    (0=ANY(p.polroles) OR (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)))))
              ),false) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname=:schema AND c.relname IN ('patients','visits') AND c.relkind IN ('r','p')
            """), {"schema": schema}).scalar_one()
            lock_safe = db.execute(text("""
              SELECT p.prosecdef AND p.prokind='f' AND p.provolatile='v'
                AND p.prorettype='pg_catalog.bool'::pg_catalog.regtype
                AND pg_catalog.cardinality(p.proconfig)=3
                AND 'search_path=pg_catalog'=ANY(p.proconfig)
                AND 'row_security=on'=ANY(p.proconfig)
                AND 'standard_conforming_strings=on'=ANY(p.proconfig)
                AND NOT owner.rolcanlogin AND NOT owner.rolsuper AND NOT owner.rolbypassrls
                AND NOT owner.rolcreaterole AND NOT owner.rolcreatedb AND NOT owner.rolreplication
                AND private_ns.nspowner=app_ns.nspowner
                AND pg_catalog.has_schema_privilege(CURRENT_USER,private_ns.oid,'USAGE')
                AND NOT pg_catalog.has_schema_privilege(CURRENT_USER,private_ns.oid,'CREATE')
                AND pg_catalog.has_function_privilege(CURRENT_USER,p.oid,'EXECUTE')
                AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(private_ns.nspacl,
                  pg_catalog.acldefault('n',private_ns.nspowner))) a
                  WHERE a.grantee=0 OR (a.privilege_type='CREATE' AND a.grantee<>private_ns.nspowner))
                AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,
                  pg_catalog.acldefault('f',p.proowner))) a
                  WHERE a.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
                    OR (a.grantee<>p.proowner AND (a.privilege_type<>'EXECUTE' OR a.is_grantable)))
                AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid<>owner.oid
                  AND (pg_catalog.pg_has_role(r.oid,owner.oid,'MEMBER') OR pg_catalog.pg_has_role(owner.oid,r.oid,'MEMBER')))
                AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.oid<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)
                  AND pg_catalog.pg_has_role(CURRENT_USER,r.oid,'MEMBER'))
                AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper
                  AND r.oid<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)
                  AND pg_catalog.pg_has_role(r.oid,CURRENT_USER,'MEMBER'))
              FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
                JOIN pg_catalog.pg_namespace private_ns ON private_ns.oid=p.pronamespace
                JOIN pg_catalog.pg_namespace app_ns ON app_ns.nspname=:schema
              WHERE p.oid=pg_catalog.to_regprocedure(:signature) AND private_ns.nspname=:private
            """), {"schema": schema, "private": private_name,
                   "signature": f"{private}.lock_confirmation_patient(pg_catalog.int4)"}).scalar_one_or_none()
            if trusted is not True or lock_safe is not True:
                raise TrustedSchemaUnavailable("Confirmation visibility is unavailable")
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            db.rollback()
            raise PatientSubjectLockError(status_code=409 if code in {"40P01", "55P03"} else 503,
                                               detail="Подтверждение временно недоступно") from None
        except (TrustedSchemaUnavailable, TypeError, ValueError):
            db.rollback()
            raise PatientSubjectLockError(status_code=503, detail="Подтверждение временно недоступно") from None


def lock_patient_subject(db, patient_id: int) -> bool:
    """Lock an active Patient in this transaction, returning false if absent.

    PostgreSQL uses a reviewed private capability; the backend never receives
    Patient UPDATE. SQLite reserves its writer before checking the row.
    """
    if type(patient_id) is not int or patient_id <= 0:
        raise PatientSubjectLockError(status_code=404, detail="Подтверждение временно недоступно")
    require_patient_subject_visibility(db)
    dialect = db.get_bind().dialect.name
    try:
        if dialect == "postgresql":
            private = db.get_bind().dialect.identifier_preparer.quote_identifier(
                capability_schema_name(settings.TRUSTED_DB_SCHEMA)
            )
            result = db.execute(text(f"SELECT {private}.lock_confirmation_patient(:subject_id)"),
                                {"subject_id": patient_id}).scalar_one()
            if type(result) is not bool:
                raise PatientSubjectLockError(status_code=503, detail="Подтверждение временно недоступно")
            return result
        if dialect == "sqlite":
            db.connection().exec_driver_sql("UPDATE patients SET id=id WHERE id=?", (patient_id,))
            patient = db.query(Patient.is_deleted).filter(Patient.id == patient_id).first()
            return patient is not None and patient.is_deleted is False
        raise PatientSubjectLockError(status_code=503, detail="Подтверждение временно недоступно")
    except DBAPIError as exc:
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        db.rollback()
        raise PatientSubjectLockError(status_code=409 if code in {"40P01", "55P03"} else 503,
                                      detail="Подтверждение временно недоступно") from None
