"""Protect recorded benefit evidence and permanent quota keys."""

from alembic import op

revision = "0133_benefit_ledger_immutability"
down_revision = "0132_cashier_refund_receipts"
branch_labels = None
depends_on = None

_APPLICATION = "encounter_benefit_applications"
_ALLOCATION = "encounter_benefit_allocations"
_EVENT = "encounter_benefit_events"
_QUOTA = "encounter_benefit_quota_anchors"
_VISIT_EVIDENCE = "encounter_benefit_visit_snapshots"
_TABLES = (_APPLICATION, _ALLOCATION, _EVENT, _QUOTA, _VISIT_EVIDENCE)
_NULLABLE_LINKS = {
    _APPLICATION: ("patient_id", "patient_benefit_id", "benefit_id", "approved_by_user_id"),
    _ALLOCATION: ("visit_id", "visit_service_id"),
    _EVENT: ("actor_user_id",),
    _QUOTA: (),
    _VISIT_EVIDENCE: ("visit_id", "patient_id"),
}
_IMMUTABLE_COLUMNS = {
    _APPLICATION: (
        "id", "encounter_id", "patient_id_snapshot", "patient_benefit_id_snapshot", "benefit_id_snapshot",
        "approved_by_user_id_snapshot", "approved_by_role_snapshot", "approved_at", "period_timezone",
        "period_month", "period_year", "encounter_generation", "percentage", "max_discount",
        "monthly_limit", "yearly_limit", "monthly_used_before", "yearly_used_before", "gross_total",
        "benefit_total", "net_total",
    ),
    _ALLOCATION: (
        "id", "application_id", "visit_id_snapshot", "visit_service_id_snapshot", "service_id_snapshot",
        "visit_context_epoch", "quantity", "unit_price", "gross_amount", "benefit_amount", "net_amount",
    ),
    _EVENT: (
        "id", "application_id", "event_type", "actor_user_id_snapshot", "actor_role_snapshot",
        "reason_code", "created_at",
    ),
    _QUOTA: ("patient_id", "benefit_id", "created_at"),
    _VISIT_EVIDENCE: ("id", "application_id", "encounter_id", "visit_id_snapshot", "visit_context_epoch"),
}
_UNIQUE_KEYS = {
    _APPLICATION: (("id",), ("encounter_id",)),
    _ALLOCATION: (("id",), ("application_id", "visit_service_id_snapshot")),
    _EVENT: (("id",),),
    _QUOTA: (("patient_id", "benefit_id"),),
    _VISIT_EVIDENCE: (("id",), ("application_id", "visit_id_snapshot")),
}
_PARENT_TABLES = {
    "patient_id": "patients", "patient_benefit_id": "patient_benefits", "benefit_id": "benefits",
    "approved_by_user_id": "users", "visit_id": "visits", "visit_service_id": "visit_services",
    "actor_user_id": "users",
}


def _postgres_target() -> tuple[str, str]:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    quoted = context.dialect.identifier_preparer.quote_schema(schema)
    delimiter = "$benefit_ledger$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"
    return quoted, delimiter


def _upgrade_postgres() -> None:
    schema, delimiter = _postgres_target()
    link_checks = []
    for link, parent in _PARENT_TABLES.items():
        anonymized = f"NOT EXISTS (SELECT 1 FROM {schema}.{parent} WHERE id=old_id)"
        if link == "patient_id":
            anonymized += (f" OR EXISTS (SELECT 1 FROM {schema}.encounters "
                           "WHERE id=(previous->>'encounter_id')::integer AND patient_id IS NULL)")
        link_checks.append(f"WHEN '{link}' THEN {anonymized}")
    op.execute(f"""
      CREATE FUNCTION {schema}.protect_encounter_benefit_ledger() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog SET row_security=off AS {delimiter}
      DECLARE previous jsonb; proposed jsonb; link text; old_id integer;
      BEGIN
        IF TG_OP<>'UPDATE' THEN RAISE EXCEPTION 'encounter benefit evidence is immutable'; END IF;
        previous := pg_catalog.to_jsonb(OLD);
        proposed := pg_catalog.to_jsonb(NEW);
        IF TG_NARGS>0 AND pg_catalog.pg_trigger_depth()>1 THEN
          FOREACH link IN ARRAY TG_ARGV LOOP
            IF previous->link<>'null'::jsonb AND proposed->link='null'::jsonb THEN
              old_id := (previous->>link)::integer;
              IF (CASE link {' '.join(link_checks)} ELSE false END) THEN
                previous := previous-link;
                proposed := proposed-link;
              END IF;
            END IF;
          END LOOP;
        END IF;
        IF previous IS DISTINCT FROM proposed THEN RAISE EXCEPTION 'encounter benefit evidence is immutable'; END IF;
        RETURN NEW;
      END {delimiter}
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {schema}.protect_encounter_benefit_ledger() FROM PUBLIC")
    for table, links in _NULLABLE_LINKS.items():
        arguments = ",".join(f"'{name}'" for name in links)
        op.execute(f"""
          CREATE TRIGGER trg_encounter_benefit_ledger_row BEFORE UPDATE OR DELETE ON {schema}.{table}
          FOR EACH ROW EXECUTE FUNCTION {schema}.protect_encounter_benefit_ledger({arguments})
        """)
    for table in _TABLES:
        op.execute(f"""
          CREATE TRIGGER trg_encounter_benefit_ledger_truncate BEFORE TRUNCATE ON {schema}.{table}
          FOR EACH STATEMENT EXECUTE FUNCTION {schema}.protect_encounter_benefit_ledger()
        """)


def _sqlite_changed_link(column: str) -> str:
    parent = _PARENT_TABLES[column]
    anonymized = f"NOT EXISTS (SELECT 1 FROM {parent} WHERE id=OLD.{column})"
    if column == "patient_id":
        # The existing composite encounter FK also cascades anonymization.
        anonymized += " OR EXISTS (SELECT 1 FROM encounters WHERE id=OLD.encounter_id AND patient_id IS NULL)"
    return (f"(NEW.{column} IS NOT OLD.{column} AND NOT (OLD.{column} IS NOT NULL "
            f"AND NEW.{column} IS NULL AND ({anonymized})))")


def _upgrade_sqlite() -> None:
    for table, links in _NULLABLE_LINKS.items():
        guarded = [f"NEW.{column} IS NOT OLD.{column}" for column in _IMMUTABLE_COLUMNS[table]]
        guarded.extend(_sqlite_changed_link(link) for link in links)
        op.execute(f"""
          CREATE TRIGGER trg_{table}_guard_update BEFORE UPDATE ON {table}
          WHEN {' OR '.join(guarded)}
          BEGIN SELECT RAISE(ABORT,'encounter benefit evidence is immutable'); END
        """)
        op.execute(f"""
          CREATE TRIGGER trg_{table}_guard_delete BEFORE DELETE ON {table}
          BEGIN SELECT RAISE(ABORT,'encounter benefit evidence is immutable'); END
        """)
        # SQLite conflict replacement may skip delete triggers when recursive triggers are disabled.
        keys = ["(" + " AND ".join(f"existing.{column}=NEW.{column}" for column in key) + ")"
                for key in _UNIQUE_KEYS[table]]
        op.execute(f"""
          CREATE TRIGGER trg_{table}_guard_insert BEFORE INSERT ON {table}
          WHEN EXISTS (SELECT 1 FROM {table} AS existing WHERE {' OR '.join(keys)})
          BEGIN SELECT RAISE(ABORT,'encounter benefit evidence is immutable'); END
        """)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        _upgrade_postgres()
    elif dialect == "sqlite":
        _upgrade_sqlite()
    else:
        raise RuntimeError("Unsupported encounter benefit ledger dialect")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        schema, delimiter = _postgres_target()
        op.execute("SET LOCAL row_security=off")
        op.execute("LOCK TABLE " + ", ".join(f"{schema}.{table}" for table in _TABLES) + " IN ACCESS EXCLUSIVE MODE")
        populated = " OR ".join(f"EXISTS (SELECT 1 FROM {schema}.{table})" for table in _TABLES)
        op.execute(f"""DO {delimiter} BEGIN
          IF {populated} THEN RAISE EXCEPTION 'encounter benefit evidence prevents downgrade'; END IF;
        END {delimiter}""")
        for table in _NULLABLE_LINKS:
            op.execute(f"DROP TRIGGER trg_encounter_benefit_ledger_row ON {schema}.{table}")
        for table in _TABLES:
            op.execute(f"DROP TRIGGER trg_encounter_benefit_ledger_truncate ON {schema}.{table}")
        op.execute(f"DROP FUNCTION {schema}.protect_encounter_benefit_ledger()")
    elif dialect == "sqlite":
        op.execute(f"UPDATE {_QUOTA} SET patient_id=patient_id WHERE 0")
        op.execute("CREATE TEMP TABLE benefit_ledger_downgrade_guard (valid INTEGER NOT NULL CHECK(valid=1))")
        populated = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in _TABLES)
        op.execute(f"INSERT INTO benefit_ledger_downgrade_guard SELECT CASE WHEN {populated} THEN 0 ELSE 1 END")
        op.execute("DROP TABLE benefit_ledger_downgrade_guard")
        for table in _NULLABLE_LINKS:
            for event in ("update", "delete", "insert"):
                op.execute(f"DROP TRIGGER trg_{table}_guard_{event}")
    else:
        raise RuntimeError("Unsupported encounter benefit ledger dialect")
