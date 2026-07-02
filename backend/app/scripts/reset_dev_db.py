from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

PRODUCTION_ENV_VALUES = {"prod", "production"}
POSTGRES_SCHEMES = {"postgresql", "postgres"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SUSPICIOUS_DB_NAMES = {
    "prod",
    "production",
    "clinic_prod",
    "live",
    "main",
}
DEFAULT_SCHEMA = "public"


class DevDatabaseSafetyError(RuntimeError):
    """Raised when reset/seed guardrails reject the target database."""


@dataclass(frozen=True)
class DatabasePreflight:
    env_name: str
    env_value: str
    driver: str
    host: str
    port: int | None
    database: str
    schema: str
    username: str
    mode: str
    seed_profile: str | None


def _normalize_env_value(value: str | None) -> str:
    return (value or "").strip().lower()


def _resolve_environment() -> tuple[str, str]:
    values = {
        "ENV": os.getenv("ENV"),
        "APP_ENV": os.getenv("APP_ENV"),
        "ENVIRONMENT": os.getenv("ENVIRONMENT"),
    }
    for name, value in values.items():
        if _normalize_env_value(value) in PRODUCTION_ENV_VALUES:
            raise DevDatabaseSafetyError(
                f"Refusing to run against production environment marker {name}={value!r}."
            )
    for name in ("ENV", "APP_ENV", "ENVIRONMENT"):
        value = values[name]
        if value and value.strip():
            return name, value.strip()
    return "ENV", "dev"


def get_database_url(explicit_database_url: str | None = None) -> str:
    database_url = (explicit_database_url or os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise DevDatabaseSafetyError("DATABASE_URL is required.")
    return database_url


def _base_driver(drivername: str) -> str:
    return drivername.split("+", 1)[0].lower()


def _is_postgres_url(url: URL) -> bool:
    return _base_driver(url.drivername) in POSTGRES_SCHEMES


def _is_sqlite_url(url: URL) -> bool:
    return _base_driver(url.drivername) == "sqlite"


def _is_suspicious_database_name(database: str) -> bool:
    name = database.strip().lower()
    return (
        name in SUSPICIOUS_DB_NAMES
        or name.endswith("_prod")
        or name.endswith("-prod")
        or "production" in name
    )


def build_preflight(
    database_url: str,
    *,
    mode: str,
    seed_profile: str | None = None,
    allow_remote_dev_db: bool = False,
    schema: str = DEFAULT_SCHEMA,
) -> DatabasePreflight:
    env_name, env_value = _resolve_environment()
    url = make_url(database_url)

    if _is_sqlite_url(url):
        raise DevDatabaseSafetyError("Refusing SQLite DATABASE_URL. Use PostgreSQL only.")
    if not _is_postgres_url(url):
        raise DevDatabaseSafetyError(
            f"Refusing non-PostgreSQL DATABASE_URL driver {url.drivername!r}."
        )
    if not url.database:
        raise DevDatabaseSafetyError("DATABASE_URL must include a database name.")
    if not url.host:
        raise DevDatabaseSafetyError("DATABASE_URL must include an explicit host.")
    if _is_suspicious_database_name(url.database):
        raise DevDatabaseSafetyError(
            f"Refusing suspicious database name {url.database!r}."
        )
    if url.host not in LOCAL_HOSTS and not allow_remote_dev_db:
        raise DevDatabaseSafetyError(
            "Refusing remote database host by default. "
            "Pass --allow-remote-dev-db only for an explicitly disposable dev DB."
        )
    if schema != DEFAULT_SCHEMA:
        raise DevDatabaseSafetyError("Only the public schema reset workflow is supported.")

    return DatabasePreflight(
        env_name=env_name,
        env_value=env_value,
        driver=url.drivername,
        host=url.host,
        port=url.port,
        database=url.database,
        schema=schema,
        username=url.username or "",
        mode=mode,
        seed_profile=seed_profile,
    )


def print_preflight(preflight: DatabasePreflight) -> None:
    print("Preflight summary")
    print(f"  ENV: {preflight.env_name}={preflight.env_value}")
    print(f"  driver: {preflight.driver}")
    print(f"  host: {preflight.host}")
    print(f"  port: {preflight.port or ''}")
    print(f"  database: {preflight.database}")
    print(f"  schema: {preflight.schema}")
    print(f"  user: {preflight.username}")
    print(f"  mode: {preflight.mode}")
    print(f"  seed profile: {preflight.seed_profile or ''}")
    sys.stdout.flush()


def require_confirm_db_name(preflight: DatabasePreflight, confirm_db_name: str | None) -> None:
    if confirm_db_name != preflight.database:
        raise DevDatabaseSafetyError(
            "Refusing reset without exact --confirm-db-name "
            f"{preflight.database!r}."
        )


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _quoted_identifier(engine, value: str) -> str:
    return engine.dialect.identifier_preparer.quote(value)


def reset_public_schema(database_url: str, *, username: str | None = None) -> None:
    engine = create_engine(database_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
            if username:
                quoted_username = _quoted_identifier(engine, username)
                conn.execute(text(f"GRANT ALL ON SCHEMA public TO {quoted_username}"))
    finally:
        engine.dispose()


def _maintenance_url(database_url: str, maintenance_database: str) -> str:
    url = make_url(database_url)
    return str(url.set(database=maintenance_database))


def recreate_database(
    database_url: str,
    *,
    database: str,
    owner: str | None,
    maintenance_database: str = "postgres",
) -> None:
    maintenance_url = _maintenance_url(database_url, maintenance_database)
    engine = create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database AND pid <> pg_backend_pid()"
                ),
                {"database": database},
            )
            quoted_database = _quoted_identifier(engine, database)
            conn.execute(text(f"DROP DATABASE IF EXISTS {quoted_database}"))
            if owner:
                quoted_owner = _quoted_identifier(engine, owner)
                conn.execute(text(f"CREATE DATABASE {quoted_database} OWNER {quoted_owner}"))
            else:
                conn.execute(text(f"CREATE DATABASE {quoted_database}"))
    finally:
        engine.dispose()


def run_alembic_upgrade(database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_backend_root(),
        env=env,
        check=True,
    )


def run_demo_seed(database_url: str, *, allow_remote_dev_db: bool) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    command = [
        sys.executable,
        "-m",
        "app.scripts.dev_seed",
        "--profile",
        "demo",
        "--confirm-dev-seed",
    ]
    if allow_remote_dev_db:
        command.append("--allow-remote-dev-db")
    subprocess.run(command, cwd=_backend_root(), env=env, check=True)


def reset_dev_database(args: argparse.Namespace) -> None:
    database_url = get_database_url(args.database_url)
    if not args.confirm_dev_reset:
        raise DevDatabaseSafetyError("Refusing reset without --confirm-dev-reset.")

    seed_profile = args.seed if args.seed != "none" else None
    if seed_profile and not args.confirm_dev_seed:
        raise DevDatabaseSafetyError(
            "Refusing reset+seed without --confirm-dev-seed."
        )

    preflight = build_preflight(
        database_url,
        mode=args.mode,
        seed_profile=seed_profile,
        allow_remote_dev_db=args.allow_remote_dev_db,
    )
    require_confirm_db_name(preflight, args.confirm_db_name)
    print_preflight(preflight)

    if args.mode == "schema":
        reset_public_schema(database_url, username=preflight.username)
    elif args.mode == "recreate-db":
        recreate_database(
            database_url,
            database=preflight.database,
            owner=preflight.username or None,
            maintenance_database=args.maintenance_db,
        )
    else:
        raise DevDatabaseSafetyError(f"Unsupported reset mode {args.mode!r}.")

    run_alembic_upgrade(database_url)

    if seed_profile == "demo":
        run_demo_seed(database_url, allow_remote_dev_db=args.allow_remote_dev_db)
    elif seed_profile:
        raise DevDatabaseSafetyError(f"Unsupported seed profile {seed_profile!r}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely reset a local PostgreSQL dev database and optionally seed demo data."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--mode",
        choices=("schema", "recreate-db"),
        default="schema",
        help="schema drops/recreates public schema; recreate-db drops/recreates DB.",
    )
    parser.add_argument(
        "--seed",
        choices=("none", "demo"),
        default="none",
        help="Optional seed profile to run after Alembic upgrade.",
    )
    parser.add_argument("--maintenance-db", default="postgres")
    parser.add_argument("--allow-remote-dev-db", action="store_true")
    parser.add_argument("--confirm-dev-reset", action="store_true")
    parser.add_argument("--confirm-dev-seed", action="store_true")
    parser.add_argument("--confirm-db-name", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        reset_dev_database(args)
    except DevDatabaseSafetyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
