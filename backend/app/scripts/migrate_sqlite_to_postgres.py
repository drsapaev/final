from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, MetaData, Table, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_SQLITE_PATH = _BACKEND_DIR / "clinic.db"
DEFAULT_EXCLUDED_TABLES = {
    "alembic_version",
    "emr_migration_ledger",
    "users",
}
LEGACY_INCOMPATIBLE_SOURCE_TABLES = {
    "daily_queues": "legacy_queue_specialist_mapping_incompatible_with_current_doctors_schema",
    "queue_entries": "legacy_queue_entries_depend_on_incompatible_daily_queues_domain",
    "queue_join_sessions": "legacy_queue_join_sessions_depend_on_incompatible_daily_queues_domain",
    "queue_statistics": "legacy_queue_statistics_depend_on_incompatible_daily_queues_domain",
    "queue_tokens": "legacy_queue_tokens_depend_on_incompatible_daily_queues_domain",
}
SKIPPABLE_BROKEN_FOREIGN_KEYS = {
    ("appointments", "patient_id"): "missing_patient_reference",
    ("messages", "recipient_id"): "missing_recipient_reference",
    ("messages", "sender_id"): "missing_sender_reference",
}
SOURCE_NULL_OVERRIDES = {
    ("user_groups", "is_active"): True,
}
UPSERT_CONFLICT_TARGETS = {
    "emr_records": ("visit_id",),
    "emr_revisions": ("emr_id", "version"),
    "file_quotas": ("user_id",),
    "user_notification_settings": ("user_id",),
    "user_preferences": ("user_id",),
    "user_profiles": ("user_id",),
}


@dataclass(frozen=True)
class TablePlan:
    table_name: str
    primary_keys: tuple[str, ...]
    common_columns: tuple[str, ...]
    source_only_columns: tuple[str, ...]
    target_only_columns: tuple[str, ...]


@dataclass(frozen=True)
class TableResult:
    table_name: str
    source_count: int
    inserted_count: int
    updated_count: int


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        return int(float(normalized))
    return int(value)


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        return float(normalized)
    return float(value)


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in (
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    parsed = datetime.strptime(normalized, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_json(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _convert_value(value: Any, target_column: dict[str, Any]) -> Any:
    type_name = target_column["type"].__class__.__name__.upper()
    if type_name in {"JSON", "JSONB"}:
        return _parse_json(value)
    if type_name in {"BOOLEAN", "BOOL"}:
        return _parse_bool(value)
    if type_name in {"INTEGER", "BIGINT", "SMALLINT"}:
        return _parse_int(value)
    if type_name in {"FLOAT", "REAL", "NUMERIC", "DECIMAL"}:
        return _parse_float(value)
    if "TIMESTAMP" in type_name or "DATETIME" in type_name or type_name == "DATE":
        return _parse_datetime(value) or value
    return value


def _build_legacy_role_id_map(connection: sqlite3.Connection) -> dict[int, int]:
    try:
        legacy_roles = {
            int(row[0]): row[1]
            for row in connection.execute(
                'SELECT id, name FROM "user_roles_legacy"'
            ).fetchall()
        }
        current_roles = {
            row[1]: int(row[0])
            for row in connection.execute(
                'SELECT id, name FROM "roles"'
            ).fetchall()
        }
    except sqlite3.OperationalError:
        return {}

    role_id_map: dict[int, int] = {}
    for legacy_id, role_name in legacy_roles.items():
        current_id = current_roles.get(role_name)
        if current_id is not None:
            role_id_map[legacy_id] = current_id
    return role_id_map


def _source_tables(connection: sqlite3.Connection) -> list[str]:
    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    return [row[0] for row in cursor.fetchall()]


def _source_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    cursor = connection.execute(f'PRAGMA table_info("{table_name}")')
    return {row[1] for row in cursor.fetchall()}


def _target_required_only_columns(table_columns: list[dict[str, Any]], common_columns: set[str]) -> list[str]:
    required = []
    for column in table_columns:
        name = column["name"]
        if name in common_columns:
            continue
        if name == "id" and column.get("autoincrement", False):
            continue
        if column.get("nullable", True):
            continue
        default = column.get("default")
        server_default = column.get("server_default")
        identity = column.get("identity")
        if default is not None or server_default is not None or identity is not None:
            continue
        required.append(name)
    return required


def _topological_order(inspector, table_names: list[str]) -> list[str]:
    selected = set(table_names)
    dependencies: dict[str, set[str]] = {}
    reverse_edges: dict[str, set[str]] = defaultdict(set)

    for table_name in table_names:
        deps = {
            fk["referred_table"]
            for fk in inspector.get_foreign_keys(table_name)
            if fk.get("referred_table") in selected and fk.get("referred_table") != table_name
        }
        dependencies[table_name] = deps
        for dep in deps:
            reverse_edges[dep].add(table_name)

    queue = deque(sorted(name for name, deps in dependencies.items() if not deps))
    ordered: list[str] = []

    while queue:
        table_name = queue.popleft()
        ordered.append(table_name)
        for dependent in sorted(reverse_edges.get(table_name, set())):
            remaining = dependencies[dependent]
            if table_name in remaining:
                remaining.remove(table_name)
            if not remaining and dependent not in ordered and dependent not in queue:
                queue.append(dependent)

    remaining_tables = [table for table in table_names if table not in ordered]
    return ordered + sorted(remaining_tables)


def plan_sqlite_to_postgres_migration(
    *,
    source_sqlite_path: Path,
    target_engine: Engine,
    include_users: bool = False,
    only_tables: set[str] | None = None,
) -> dict[str, Any]:
    source_connection = sqlite3.connect(source_sqlite_path)
    try:
        source_tables = _source_tables(source_connection)
    finally:
        source_connection.close()

    inspector = inspect(target_engine)
    target_tables = set(inspector.get_table_names())

    excluded_tables = set(DEFAULT_EXCLUDED_TABLES)
    if include_users:
        excluded_tables.discard("users")

    skipped_missing_target = sorted(
        table_name
        for table_name in source_tables
        if table_name not in target_tables
        and table_name not in LEGACY_INCOMPATIBLE_SOURCE_TABLES
        and (only_tables is None or table_name in only_tables)
    )
    skipped_legacy_incompatible = [
        {
            "table_name": table_name,
            "reason": LEGACY_INCOMPATIBLE_SOURCE_TABLES[table_name],
        }
        for table_name in sorted(source_tables)
        if table_name in LEGACY_INCOMPATIBLE_SOURCE_TABLES
        and (only_tables is None or table_name in only_tables)
    ]

    plans: list[TablePlan] = []
    skipped_incompatible: list[dict[str, Any]] = []

    source_connection = sqlite3.connect(source_sqlite_path)
    try:
        for table_name in source_tables:
            if only_tables is not None and table_name not in only_tables:
                continue
            if table_name in excluded_tables:
                continue
            if table_name in LEGACY_INCOMPATIBLE_SOURCE_TABLES:
                continue
            if table_name not in target_tables:
                continue

            source_columns = _source_columns(source_connection, table_name)
            target_columns = inspector.get_columns(table_name)
            target_column_names = {column["name"] for column in target_columns}
            common_columns = source_columns & target_column_names
            primary_keys = tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
            required_only_columns = _target_required_only_columns(target_columns, common_columns)

            if not primary_keys:
                skipped_incompatible.append(
                    {
                        "table_name": table_name,
                        "reason": "missing_primary_key",
                    }
                )
                continue

            if required_only_columns:
                skipped_incompatible.append(
                    {
                        "table_name": table_name,
                        "reason": "required_target_columns_missing_in_source",
                        "columns": required_only_columns,
                    }
                )
                continue

            plans.append(
                TablePlan(
                    table_name=table_name,
                    primary_keys=primary_keys,
                    common_columns=tuple(sorted(common_columns)),
                    source_only_columns=tuple(sorted(source_columns - target_column_names)),
                    target_only_columns=tuple(sorted(target_column_names - source_columns)),
                )
            )
    finally:
        source_connection.close()

    ordered_table_names = _topological_order(
        inspector,
        [plan.table_name for plan in plans],
    )
    plan_map = {plan.table_name: plan for plan in plans}
    ordered_plans = [plan_map[table_name] for table_name in ordered_table_names if table_name in plan_map]

    return {
        "ordered_tables": [plan.table_name for plan in ordered_plans],
        "plans": ordered_plans,
        "skipped_missing_target": skipped_missing_target,
        "skipped_legacy_incompatible": skipped_legacy_incompatible,
        "skipped_incompatible": skipped_incompatible,
    }


def migrate_sqlite_to_postgres(
    *,
    source_sqlite_path: Path,
    target_engine: Engine,
    dry_run: bool = False,
    include_users: bool = False,
    only_tables: set[str] | None = None,
) -> dict[str, Any]:
    migration_plan = plan_sqlite_to_postgres_migration(
        source_sqlite_path=source_sqlite_path,
        target_engine=target_engine,
        include_users=include_users,
        only_tables=only_tables,
    )
    plans: list[TablePlan] = migration_plan["plans"]

    sqlite_connection = sqlite3.connect(source_sqlite_path)
    sqlite_connection.row_factory = sqlite3.Row
    metadata = MetaData()
    table_objects = {
        plan.table_name: Table(plan.table_name, metadata, autoload_with=target_engine)
        for plan in plans
    }
    plan_by_table_name = {
        plan.table_name: plan
        for plan in plans
    }
    source_primary_key_cache: dict[str, set[Any]] = {}
    source_user_profile_id_by_user_id = {}
    if "user_profiles" in plan_by_table_name:
        source_user_profile_id_by_user_id = {
            int(row[1]): int(row[0])
            for row in sqlite_connection.execute(
                'SELECT id, user_id FROM "user_profiles" WHERE user_id IS NOT NULL'
            ).fetchall()
        }

    table_results: list[TableResult] = []
    table_errors: list[dict[str, Any]] = []
    repaired_foreign_keys: dict[tuple[str, str], int] = defaultdict(int)
    repaired_value_mappings: dict[tuple[str, str, str], int] = defaultdict(int)
    skipped_invalid_rows: dict[tuple[str, str], int] = defaultdict(int)
    foreign_key_presence_cache: dict[tuple[str, str, Any], bool] = {}
    legacy_role_id_map = _build_legacy_role_id_map(sqlite_connection)

    try:
        with target_engine.begin() as target_connection:
            for plan in plans:
                cursor = sqlite_connection.execute(
                    f'SELECT * FROM "{plan.table_name}" ORDER BY {", ".join(plan.primary_keys)}'  # nosec B608 — one-shot SQLite→PG migration script, hardcoded queries
                )
                rows = cursor.fetchall()
                source_count = len(rows)
                inserted_count = 0
                updated_count = 0
                table_object = table_objects[plan.table_name]
                target_columns_by_name = {
                    column["name"]: column
                    for column in inspect(target_engine).get_columns(plan.table_name)
                }
                foreign_keys = [
                    fk
                    for fk in inspect(target_engine).get_foreign_keys(plan.table_name)
                    if len(fk.get("constrained_columns") or []) == 1
                    and len(fk.get("referred_columns") or []) == 1
                ]

                if source_count == 0:
                    table_results.append(
                        TableResult(
                            table_name=plan.table_name,
                            source_count=0,
                            inserted_count=0,
                            updated_count=0,
                        )
                    )
                    continue

                existing_keys = {
                    tuple(row)
                    for row in target_connection.execute(
                        text(
                            f'SELECT {", ".join(plan.primary_keys)} FROM "{plan.table_name}"'  # nosec B608 — one-shot SQLite→PG migration script, hardcoded queries
                        )
                    ).fetchall()
                }

                for source_row in rows:
                    payload = {
                        column_name: _convert_value(
                            source_row[column_name],
                            target_columns_by_name[column_name],
                        )
                        for column_name in plan.common_columns
                    }

                    for (table_name, column_name), override_value in SOURCE_NULL_OVERRIDES.items():
                        if plan.table_name != table_name:
                            continue
                        if payload.get(column_name) is None:
                            payload[column_name] = override_value

                    if plan.table_name == "services" and isinstance(payload.get("category_code"), str):
                        normalized_category_code = payload["category_code"].strip()
                        if len(normalized_category_code) > 1:
                            payload["category_code"] = normalized_category_code[0].upper()

                    if plan.table_name in {"user_preferences", "user_notification_settings"}:
                        user_id = payload.get("user_id")
                        if user_id is not None and "profile_id" in payload:
                            target_profile_id = target_connection.execute(
                                text('SELECT id FROM "user_profiles" WHERE user_id = :user_id'),
                                {"user_id": user_id},
                            ).scalar()
                            if target_profile_id is not None:
                                payload["profile_id"] = target_profile_id
                            elif dry_run:
                                source_profile_id = source_user_profile_id_by_user_id.get(user_id)
                                if source_profile_id is not None:
                                    payload["profile_id"] = source_profile_id

                    if (
                        plan.table_name == "role_permissions"
                        and "role_id" in payload
                        and payload["role_id"] in legacy_role_id_map
                    ):
                        payload["role_id"] = legacy_role_id_map[payload["role_id"]]
                        repaired_value_mappings[
                            (plan.table_name, "role_id", "legacy_role_id_remap")
                        ] += 1

                    skip_row = False
                    for foreign_key in foreign_keys:
                        column_name = foreign_key["constrained_columns"][0]
                        referred_table = foreign_key["referred_table"]
                        referred_column = foreign_key["referred_columns"][0]

                        if column_name not in payload:
                            continue

                        value = payload[column_name]
                        if value is None or referred_table == plan.table_name:
                            continue

                        cache_key = (referred_table, referred_column, value)
                        if cache_key in foreign_key_presence_cache:
                            exists = foreign_key_presence_cache[cache_key]
                        else:
                            exists = False
                            referred_plan = plan_by_table_name.get(referred_table)
                            if (
                                dry_run
                                and referred_plan is not None
                                and len(referred_plan.primary_keys) == 1
                                and referred_column == referred_plan.primary_keys[0]
                            ):
                                if referred_table not in source_primary_key_cache:
                                    source_primary_key_cache[referred_table] = {
                                        row[0]
                                        for row in sqlite_connection.execute(
                                            f'SELECT "{referred_column}" FROM "{referred_table}"'  # nosec B608 — one-shot SQLite→PG migration script, hardcoded queries
                                        ).fetchall()
                                    }
                                exists = value in source_primary_key_cache[referred_table]

                            if not exists:
                                exists = (
                                    target_connection.execute(
                                        text(
                                            f'SELECT 1 FROM "{referred_table}" '  # nosec B608 — one-shot SQLite→PG migration script, hardcoded queries
                                            f'WHERE "{referred_column}" = :value LIMIT 1'
                                        ),
                                        {"value": value},
                                    ).first()
                                    is not None
                                )
                            foreign_key_presence_cache[cache_key] = exists

                        if exists:
                            continue

                        target_column = target_columns_by_name[column_name]
                        if target_column.get("nullable", True):
                            payload[column_name] = None
                            repaired_foreign_keys[(plan.table_name, column_name)] += 1
                            continue

                        skip_reason = SKIPPABLE_BROKEN_FOREIGN_KEYS.get(
                            (plan.table_name, column_name)
                        )
                        if skip_reason:
                            skipped_invalid_rows[(plan.table_name, skip_reason)] += 1
                            skip_row = True
                            break

                        raise ValueError(
                            "non_nullable_foreign_key_missing: "
                            f"{plan.table_name}.{column_name} -> "
                            f"{referred_table}.{referred_column} value={value}"
                        )

                    if skip_row:
                        continue

                    row_key = tuple(payload[pk] for pk in plan.primary_keys)

                    if row_key in existing_keys:
                        updated_count += 1
                    else:
                        inserted_count += 1
                        existing_keys.add(row_key)

                    if dry_run:
                        continue

                    insert_stmt = pg_insert(table_object).values(payload)
                    conflict_columns = UPSERT_CONFLICT_TARGETS.get(
                        plan.table_name,
                        plan.primary_keys,
                    )
                    update_columns = {
                        column_name: insert_stmt.excluded[column_name]
                        for column_name in plan.common_columns
                        if column_name not in set(plan.primary_keys)
                        and not (
                            conflict_columns != plan.primary_keys and column_name == "id"
                        )
                    }
                    if update_columns:
                        stmt = insert_stmt.on_conflict_do_update(
                            index_elements=list(conflict_columns),
                            set_=update_columns,
                        )
                    else:
                        stmt = insert_stmt.on_conflict_do_nothing(
                            index_elements=list(conflict_columns),
                        )
                    target_connection.execute(stmt)

                if not dry_run and plan.primary_keys == ("id",):
                    target_connection.execute(
                        text(
                            f"""
                            SELECT setval(
                                pg_get_serial_sequence('{plan.table_name}', 'id'),
                                COALESCE((SELECT MAX(id) FROM "{plan.table_name}"), 1),
                                true
                            )
                            """
                        )
                    )

                table_results.append(
                    TableResult(
                        table_name=plan.table_name,
                        source_count=source_count,
                        inserted_count=inserted_count,
                        updated_count=updated_count,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        table_errors.append(
            {
                "table_name": plan.table_name if "plan" in locals() else None,
                "message": str(exc),
                "type": exc.__class__.__name__,
            }
        )
        raise
    finally:
        sqlite_connection.close()

    return {
        "success": True,
        "dry_run": dry_run,
        "source_sqlite_path": str(source_sqlite_path),
        "target_url": _mask_engine_url(target_engine),
        "migrated_tables": [
            {
                "table_name": result.table_name,
                "source_count": result.source_count,
                "inserted_count": result.inserted_count,
                "updated_count": result.updated_count,
            }
            for result in table_results
        ],
        "skipped_missing_target": migration_plan["skipped_missing_target"],
        "skipped_legacy_incompatible": migration_plan["skipped_legacy_incompatible"],
        "skipped_incompatible": migration_plan["skipped_incompatible"],
        "errors": table_errors,
        "repaired_foreign_keys": [
            {
                "table_name": table_name,
                "column_name": column_name,
                "repaired_count": repaired_count,
            }
            for (table_name, column_name), repaired_count in sorted(repaired_foreign_keys.items())
        ],
        "repaired_value_mappings": [
            {
                "table_name": table_name,
                "column_name": column_name,
                "repair_kind": repair_kind,
                "repaired_count": repaired_count,
            }
            for (table_name, column_name, repair_kind), repaired_count in sorted(repaired_value_mappings.items())
        ],
        "skipped_invalid_rows": [
            {
                "table_name": table_name,
                "reason": reason,
                "skipped_count": skipped_count,
            }
            for (table_name, reason), skipped_count in sorted(skipped_invalid_rows.items())
        ],
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate supported data from SQLite clinic.db into PostgreSQL."
    )
    parser.add_argument(
        "--source-sqlite",
        type=Path,
        default=DEFAULT_SOURCE_SQLITE_PATH,
        help="Path to source SQLite database.",
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Optional SQLAlchemy URL for PostgreSQL target.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan migration and count inserts/updates without writing changes.",
    )
    parser.add_argument(
        "--include-users",
        action="store_true",
        help="Also migrate users. Disabled by default because users have a dedicated migrator.",
    )
    parser.add_argument(
        "--tables",
        default=None,
        help="Comma-separated list of tables to migrate.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser


def _require_live_migration_confirmation(*, dry_run: bool) -> None:
    if dry_run:
        return
    if os.getenv("CONFIRM_SQLITE_TO_POSTGRES_MIGRATION") != "1":
        raise SystemExit(
            "Refusing to run live SQLite to PostgreSQL migration without "
            "CONFIRM_SQLITE_TO_POSTGRES_MIGRATION=1. Use --dry-run for a read-only plan."
        )


def _mask_engine_url(engine: Engine) -> str:
    rendered = str(engine.url)
    password = engine.url.password
    if password:
        return rendered.replace(password, "***")
    return rendered


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()
    _require_live_migration_confirmation(dry_run=args.dry_run)

    if args.target_url:
        target_engine = create_engine(args.target_url)
    else:
        from app.core.config import settings

        target_engine = create_engine(settings.DATABASE_URL)

    only_tables = None
    if args.tables:
        only_tables = {
            table_name.strip()
            for table_name in args.tables.split(",")
            if table_name.strip()
        }

    result = migrate_sqlite_to_postgres(
        source_sqlite_path=args.source_sqlite,
        target_engine=target_engine,
        dry_run=args.dry_run,
        include_users=args.include_users,
        only_tables=only_tables,
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
