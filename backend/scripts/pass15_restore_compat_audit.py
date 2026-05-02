from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import sqlite as sqlite_dialect

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DB_PATH = BACKEND_ROOT / "restore_data" / "clinic.db"
LEGACY_BACKEND_ROOT = Path("/mnt/c/final/restored_clinic_from_ubuntuproof/backend")
REPORT_DIR = Path("/mnt/c/final/final777/reports")
REPORT_PATH = REPORT_DIR / "UBUNTUPROOF_LATEST_GITHUB_COMPAT_AUDIT_PASS15.md"
JSON_PATH = REPORT_DIR / "UBUNTUPROOF_LATEST_GITHUB_COMPAT_AUDIT_PASS15.json"

sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import Base


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def sqlite_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table_name}")')}


def compile_add_column(table_name: str, column: Any) -> str:
    # Recovery shims intentionally add columns as nullable. This avoids SQLite
    # table rebuilds and prevents NOT NULL failures on restored tables that
    # already contain rows. Application-level defaults still populate new rows.
    column_type = column.type.compile(dialect=sqlite_dialect.dialect())
    return f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {column_type}'


def is_safe_add_column(column: Any) -> bool:
    if column.primary_key:
        return False
    if column.nullable:
        return True
    if column.default is not None or column.server_default is not None:
        return True
    return False


def normalize_file_paths(conn: sqlite3.Connection, *, apply: bool) -> list[dict[str, Any]]:
    tables = sqlite_tables(conn)
    if "files" not in tables or "file_path" not in sqlite_columns(conn, "files"):
        return []

    rows = conn.execute(
        "SELECT id, file_path FROM files WHERE file_path LIKE ?",
        ("%" + chr(92) + "%",),
    ).fetchall()
    changes: list[dict[str, Any]] = []
    for file_id, old_path in rows:
        new_path = (old_path or "").replace(chr(92), "/")
        changes.append({"id": file_id, "old_path": old_path, "new_path": new_path})
        if apply:
            conn.execute("UPDATE files SET file_path=? WHERE id=?", (new_path, file_id))
    if apply and changes:
        conn.commit()
    return changes


def copy_missing_referenced_uploads(conn: sqlite3.Connection, *, apply: bool) -> list[dict[str, Any]]:
    tables = sqlite_tables(conn)
    if "files" not in tables or "file_path" not in sqlite_columns(conn, "files"):
        return []

    rows = conn.execute("SELECT id, file_path FROM files WHERE file_path IS NOT NULL").fetchall()
    copies: list[dict[str, Any]] = []
    for file_id, raw_path in rows:
        relative = (raw_path or "").replace(chr(92), "/")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            continue
        latest_path = BACKEND_ROOT / relative
        if latest_path.exists():
            continue
        legacy_path = LEGACY_BACKEND_ROOT / relative
        record: dict[str, Any] = {
            "id": file_id,
            "relative_path": relative,
            "legacy_exists": legacy_path.exists(),
            "copied": False,
        }
        if legacy_path.exists() and legacy_path.is_file():
            record["source_size"] = legacy_path.stat().st_size
            if apply:
                latest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_path, latest_path)
                record["destination_size"] = latest_path.stat().st_size
                record["hash_match"] = sha256(legacy_path) == sha256(latest_path)
                record["copied"] = True
        copies.append(record)
    return copies


def schema_audit_and_apply(*, apply: bool) -> dict[str, Any]:
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    inspector = inspect(engine)
    report: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "db_path": str(DB_PATH),
        "apply": apply,
        "missing_tables": [],
        "created_tables": [],
        "missing_columns_added": [],
        "missing_columns_skipped": [],
        "file_path_normalizations": [],
        "upload_copies": [],
    }

    existing_tables = set(inspector.get_table_names())
    metadata_tables = Base.metadata.tables

    for table_name, table in sorted(metadata_tables.items()):
        if table_name not in existing_tables:
            report["missing_tables"].append(table_name)
            if apply:
                table.create(bind=engine, checkfirst=True)
                report["created_tables"].append(table_name)

    # Re-inspect after creating tables.
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with sqlite3.connect(DB_PATH) as conn:
        for table_name, table in sorted(metadata_tables.items()):
            if table_name not in existing_tables:
                continue
            existing_columns = sqlite_columns(conn, table_name)
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                item = {
                    "table": table_name,
                    "column": column.name,
                    "type": str(column.type),
                    "nullable": bool(column.nullable),
                    "primary_key": bool(column.primary_key),
                    "safe": is_safe_add_column(column),
                }
                if not is_safe_add_column(column):
                    report["missing_columns_skipped"].append(item)
                    continue
                sql = compile_add_column(table_name, column)
                item["sql"] = sql
                if apply:
                    conn.execute(sql)
                    conn.commit()
                    item["applied"] = True
                else:
                    item["applied"] = False
                report["missing_columns_added"].append(item)

        report["file_path_normalizations"] = normalize_file_paths(conn, apply=apply)
        report["upload_copies"] = copy_missing_referenced_uploads(conn, apply=apply)

    return report


def write_reports(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    added = report["missing_columns_added"]
    skipped = report["missing_columns_skipped"]
    created = report["created_tables"]
    copies = report["upload_copies"]
    copied = [row for row in copies if row.get("copied")]
    missing_uploads = [row for row in copies if not row.get("legacy_exists")]

    lines = [
        "# UbuntuProof Latest GitHub Compatibility Audit PASS15",
        "",
        "## Executive Summary",
        "",
        f"- Generated UTC: `{report['generated_at_utc']}`",
        f"- Isolated DB: `{report['db_path']}`",
        f"- Apply mode: `{report['apply']}`",
        f"- Missing tables created: `{len(created)}`",
        f"- Safe columns added: `{len(added)}`",
        f"- Unsafe columns skipped: `{len(skipped)}`",
        f"- File paths normalized: `{len(report['file_path_normalizations'])}`",
        f"- Missing referenced uploads copied from local UbuntuProof restore: `{len(copied)}`",
        f"- Referenced uploads still missing in local UbuntuProof restore: `{len(missing_uploads)}`",
        "",
        "## Safety Confirmation",
        "",
        "- Original UbuntuProof VHDX was not touched.",
        "- PASS12 protected DB artifacts were not modified.",
        "- Changes were applied only to the isolated latest GitHub restore contour.",
        "- No Alembic migrations were run.",
        "- No file contents or secrets were printed.",
        "",
        "## Created Tables",
        "",
    ]
    lines.extend(f"- `{name}`" for name in created[:200])
    if len(created) > 200:
        lines.append(f"- ... truncated, see `{JSON_PATH}`")

    lines += ["", "## Added Columns", ""]
    lines.extend(f"- `{row['table']}.{row['column']}` ({row['type']})" for row in added[:300])
    if len(added) > 300:
        lines.append(f"- ... truncated, see `{JSON_PATH}`")

    lines += ["", "## Skipped Unsafe Columns", ""]
    if skipped:
        lines.extend(
            f"- `{row['table']}.{row['column']}` ({row['type']}, nullable={row['nullable']}, primary_key={row['primary_key']})"
            for row in skipped[:200]
        )
    else:
        lines.append("- None.")

    lines += ["", "## Runtime Upload Repair", ""]
    if copied:
        lines.extend(
            f"- Copied `{row['relative_path']}` ({row.get('destination_size', row.get('source_size', 0))} bytes, hash_match={row.get('hash_match')})"
            for row in copied[:200]
        )
    else:
        lines.append("- No missing referenced uploads needed copying.")

    if missing_uploads:
        lines += ["", "## Still Missing Referenced Uploads", ""]
        lines.extend(f"- `{row['relative_path']}`" for row in missing_uploads[:200])
        if len(missing_uploads) > 200:
            lines.append(f"- ... truncated, see `{JSON_PATH}`")

    lines += [
        "",
        "## Recommended Next Step",
        "",
        "Run focused smoke checks for the main UI/API surfaces and repeat this script after any further GitHub code updates.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = schema_audit_and_apply(apply=args.apply)
    write_reports(report)
    print(json.dumps({
        "apply": report["apply"],
        "created_tables": len(report["created_tables"]),
        "added_columns": len(report["missing_columns_added"]),
        "skipped_columns": len(report["missing_columns_skipped"]),
        "normalized_paths": len(report["file_path_normalizations"]),
        "upload_copies": len([row for row in report["upload_copies"] if row.get("copied")]),
        "report": str(REPORT_PATH),
        "json": str(JSON_PATH),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
