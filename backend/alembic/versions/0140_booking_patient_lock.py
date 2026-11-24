"""Provide a private patient lock compatible with booking foreign keys."""

import hashlib

from alembic import op

revision = "0140_booking_patient_lock"
down_revision = "0139_deposit_receipt_truncate"
branch_labels = None
depends_on = None


def _schemas() -> tuple[str, str]:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not isinstance(schema, str) or not schema or "\0" in schema or len(schema.encode()) > 63:
        raise RuntimeError("Trusted booking schema required")
    # Frozen v1 namespace contract from revision 0116.
    digest = hashlib.sha256(b"clinic-capability-schema-v1\0" + schema.encode()).hexdigest()
    quote = context.dialect.identifier_preparer.quote_schema
    return quote(schema), quote("clinic_internal_" + digest[:32])


def booking_lock_function_body(schema: str) -> str:
    return f"""
      DECLARE active_subject pg_catalog.bool;
      BEGIN
        IF subject_id IS NULL OR subject_id <= 0 THEN
          RAISE EXCEPTION 'invalid booking subject';
        END IF;
        SELECT p.is_deleted IS FALSE INTO active_subject FROM {schema}.patients p
          WHERE p.id=subject_id FOR NO KEY UPDATE;
        RETURN active_subject IS TRUE;
      END """


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported booking lock dialect")

    schema, private = _schemas()
    body = booking_lock_function_body(schema)
    delimiter = "$booking_patient_lock$"
    while delimiter in body:
        delimiter = delimiter[:-1] + "_x$"
    op.execute(f"""
      CREATE FUNCTION {private}.lock_booking_patient(subject_id pg_catalog.int4)
      RETURNS pg_catalog.bool LANGUAGE plpgsql SECURITY INVOKER
      SET search_path=pg_catalog SET row_security=off SET standard_conforming_strings=on
      AS {delimiter}{body}{delimiter}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {private}.lock_booking_patient(pg_catalog.int4) FROM PUBLIC")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported booking lock dialect")

    _, private = _schemas()
    op.execute(f"DROP FUNCTION {private}.lock_booking_patient(pg_catalog.int4)")
