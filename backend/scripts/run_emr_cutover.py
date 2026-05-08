from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse


COMMON_PG_DUMP_PATHS = (
    r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
    r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
    "/usr/bin/pg_dump",
    "/usr/local/bin/pg_dump",
)


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full EMR v2 hard-cutover workflow with backup, freeze, and verification."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional batch limit passed to dry-run and live cutover commands.",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip pg_dump backup creation.",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Directory for pg_dump backups. Defaults to backend/backups.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON payloads from cutover steps.",
    )
    return parser.parse_args()


def _load_dotenv_defaults(env: dict[str, str]) -> None:
    env_path = _backend_root() / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env.setdefault(key, value)


def _find_pg_dump() -> str:
    configured = os.environ.get("PG_DUMP_PATH")
    if configured and Path(configured).exists():
        return configured

    discovered = shutil.which("pg_dump")
    if discovered:
        return discovered

    for candidate in COMMON_PG_DUMP_PATHS:
        if Path(candidate).exists():
            return candidate

    raise RuntimeError(
        "pg_dump not found. Install PostgreSQL client tools or set PG_DUMP_PATH."
    )


def _parse_database_url(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url)
    if not parsed.scheme.startswith("postgresql"):
        raise RuntimeError(
            "run_emr_cutover.py only supports PostgreSQL DATABASE_URL values."
        )

    db_name = parsed.path.lstrip("/")
    if not db_name:
        raise RuntimeError("DATABASE_URL must include a database name.")

    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "db_name": unquote(db_name),
    }


def _run_checked(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    capture_json: bool = False,
) -> dict | None:
    printable = " ".join(command)
    print(f"$ {printable}", file=sys.stderr)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {printable}"
        )
    if not capture_json:
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Command did not return valid JSON: {printable}"
        ) from exc


def _run_backup(env: dict[str, str], backup_dir: Path) -> Path:
    database_url = env.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to create a pg_dump backup.")

    parsed = _parse_database_url(database_url)
    pg_dump = _find_pg_dump()

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{parsed['db_name']}_emr_cutover_{timestamp}.dump"

    backup_env = env.copy()
    if parsed["password"]:
        backup_env["PGPASSWORD"] = parsed["password"]

    command = [
        pg_dump,
        "--format=custom",
        "--host",
        parsed["host"],
        "--port",
        parsed["port"],
        "--username",
        parsed["user"],
        "--file",
        str(backup_path),
        parsed["db_name"],
    ]
    _run_checked(command, env=backup_env, cwd=_backend_root())
    print(
        json.dumps(
            {
                "backup_created": True,
                "backup_path": str(backup_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return backup_path


def _ops_command(mode: str, *, pretty: bool, limit: int | None) -> list[str]:
    command = [sys.executable, "scripts/emr_cutover_ops.py", mode]
    if limit is not None and mode in {"dry-run", "live"}:
        command.extend(["--limit", str(limit)])
    if pretty:
        command.append("--pretty")
    return command


def main() -> int:
    args = _parse_args()
    if os.getenv("CONFIRM_RUN_EMR_CUTOVER") != "1":
        raise RuntimeError(
            "Refusing to run full EMR cutover workflow. "
            "Set CONFIRM_RUN_EMR_CUTOVER=1 only for an explicit operator-approved cutover run."
        )
    backend_root = _backend_root()
    env = os.environ.copy()
    _load_dotenv_defaults(env)
    env["EMR_LEGACY_WRITE_FREEZE"] = "1"

    backup_path: Path | None = None
    try:
        if not args.skip_backup:
            backup_dir = (
                Path(args.backup_dir)
                if args.backup_dir
                else backend_root / "backups"
            )
            backup_path = _run_backup(env, backup_dir)

        _run_checked(["alembic", "upgrade", "head"], env=env, cwd=backend_root)

        preflight = _run_checked(
            _ops_command("verify", pretty=args.pretty, limit=args.limit),
            env=env,
            cwd=backend_root,
            capture_json=True,
        )
        dry_run = _run_checked(
            _ops_command("dry-run", pretty=args.pretty, limit=args.limit),
            env=env,
            cwd=backend_root,
            capture_json=True,
        )
        live_run = _run_checked(
            _ops_command("live", pretty=args.pretty, limit=args.limit),
            env=env,
            cwd=backend_root,
            capture_json=True,
        )
        final_verify = _run_checked(
            _ops_command("verify", pretty=args.pretty, limit=args.limit),
            env=env,
            cwd=backend_root,
            capture_json=True,
        )

        if not final_verify.get("passed", False):
            raise RuntimeError("Final EMR cutover verification did not pass.")

        print(
            json.dumps(
                {
                    "success": True,
                    "backup_path": str(backup_path) if backup_path else None,
                    "preflight_passed": bool(preflight.get("passed")),
                    "dry_run": dry_run,
                    "live_run": live_run,
                    "final_verify": final_verify,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return 0
    except Exception as exc:  # pragma: no cover - operational guardrail
        print(
            json.dumps(
                {
                    "success": False,
                    "backup_path": str(backup_path) if backup_path else None,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
