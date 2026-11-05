#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from clinic_lifecycle_common import (
    app_root,
    fail,
    load_clinic_env,
    parse_database_url,
    pass_message,
    run_command,
)

# BR-002: textual DSN equality proves nothing — two URLs can address the same
# database through host aliases (localhost vs 127.0.0.1, DNS names).
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _redact_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if not parsed.password:
        return database_url

    username = parsed.username or ""
    hostname = parsed.hostname or ""
    host = hostname
    if ":" in hostname and not hostname.startswith("["):
        host = f"[{hostname}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"

    netloc = f"{username}:***@{host}" if username else host
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )


def _script(name: str) -> Path:
    return Path(__file__).resolve().parent / name


def _extract_value(stdout: str, key: str) -> str | None:
    prefix = f"{key}="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _invoke(
    script_name: str,
    *,
    extra_env: dict[str, str] | None = None,
    drop_env: set[str] | None = None,
) -> str:
    env = os.environ.copy()
    # BR-002: the rehearsal must not inherit the restore script's explicit
    # live-restore confirmation bypass — a deliberate live-database restore
    # belongs to restore_db.py's own documented workflow, never to a rehearsal.
    for key in drop_env or ():
        env.pop(key, None)
    if extra_env:
        env.update(extra_env)
    result = run_command(
        [sys.executable, str(_script(script_name))], cwd=app_root(), env=env
    )
    return result.stdout


def _database_identity(database_url: str) -> tuple[str, int, str]:
    """Component identity of a PostgreSQL DSN with loopback aliases normalized."""

    target = parse_database_url(database_url)
    host = (target.host or "").strip("[]").lower()
    if host in _LOOPBACK_HOSTS:
        host = "loopback"
    return (host, target.port, target.name.lower())


def _require_separate_restore_target(restore_database_url: str) -> None:
    """BR-002: refuse a rehearsal whose restore target resolves to the runtime
    database. The historical raw ``DATABASE_URL == RESTORE_DATABASE_URL``
    comparison missed host aliases, and the restore script's
    ``CONFIRM_RESTORE_DB`` bypass could be silently inherited from the
    environment — together a misconfigured rehearsal could restore over the
    live database."""

    runtime_database_url = os.environ.get("DATABASE_URL")
    if not runtime_database_url:
        return
    if _database_identity(runtime_database_url) == _database_identity(
        restore_database_url
    ):
        fail(
            "RESTORE_DATABASE_URL resolves to the same database target as "
            "DATABASE_URL (host aliases normalized). The rehearsal only "
            "certifies restores into a separate target; for a deliberate "
            "live-database restore use restore_db.py directly with its "
            "documented confirmation workflow."
        )


def main() -> int:
    load_clinic_env()

    restore_database_url = os.environ.get("RESTORE_DATABASE_URL")
    if not restore_database_url:
        fail("RESTORE_DATABASE_URL is required")

    # BR-002: structural same-target refusal before any child runs.
    _require_separate_restore_target(restore_database_url)

    restore_backend_url = os.environ.get("RESTORE_BACKEND_URL")
    restore_public_url = os.environ.get("RESTORE_PUBLIC_URL")
    if not restore_backend_url or not restore_public_url:
        fail(
            "RESTORE_BACKEND_URL and RESTORE_PUBLIC_URL are required for restore smoke"
        )

    # BR-003: the HTTP smoke cannot prove that the probed backend serves the
    # restored RESTORE_DATABASE_URL — health/login endpoints expose no
    # database identity. The rehearsal therefore refuses to certify a restore
    # unless the operator consciously acknowledges this evidence boundary.
    if os.environ.get("RESTORE_SMOKE_BINDING_ACK") != "1":
        fail(
            "Restore smoke cannot prove that RESTORE_BACKEND_URL serves the "
            "restored RESTORE_DATABASE_URL (health/login endpoints expose no "
            "database identity). Run the runbook's binding verification and "
            "set RESTORE_SMOKE_BINDING_ACK=1 to acknowledge that the smoke "
            "verdict is not a database-binding proof."
        )

    backup_dir = os.environ.get("BACKUP_DIR")

    backup_stdout = _invoke(
        "backup_db.py",
        extra_env={"BACKUP_DIR": backup_dir} if backup_dir else None,
    )
    backup_file = _extract_value(backup_stdout, "BACKUP_FILE")
    if not backup_file:
        fail("backup_db did not report BACKUP_FILE")

    _invoke(
        "restore_db.py",
        extra_env={
            "BACKUP_FILE": backup_file,
            "RESTORE_DATABASE_URL": restore_database_url,
        },
        # BR-002: never inherit the live-restore confirmation bypass.
        drop_env={"CONFIRM_RESTORE_DB"},
    )
    _invoke(
        "health_check.py",
        extra_env={
            "BACKEND_URL": restore_backend_url,
            "PUBLIC_URL": restore_public_url,
            "EXPECTED_SETUP_INITIALIZED": "1",
            # BR-005: pin restore-scoped origin resolution for the smoke
            # children; LAN auto-detection must never override the explicit
            # RESTORE_PUBLIC_URL.
            "CLINIC_AUTO_DETECT_PUBLIC_URL": "0",
        },
    )
    _invoke(
        "smoke_post_update.py",
        extra_env={
            "BACKEND_URL": restore_backend_url,
            "PUBLIC_URL": restore_public_url,
            "EXPECTED_SETUP_INITIALIZED": "1",
            "SMOKE_REQUIRE_LOGIN": os.environ.get("SMOKE_REQUIRE_LOGIN", "1"),
            # BR-005: same restore-scoped origin pin as health_check above.
            "CLINIC_AUTO_DETECT_PUBLIC_URL": "0",
        },
    )

    # BR-003: keep the verdict honest — the smoke is an availability proof,
    # not a database-binding proof.
    print(
        "RESTORE_SMOKE_DB_BINDING=not-proven (acknowledged; runbook binding verification required)",
        flush=True,
    )
    print(f"RESTORE_BACKUP_FILE={backup_file}", flush=True)
    print(
        f"RESTORE_DATABASE_URL={_redact_database_url(restore_database_url)}", flush=True
    )
    print(f"RESTORE_BACKEND_URL={restore_backend_url}", flush=True)
    print(f"RESTORE_PUBLIC_URL={restore_public_url}", flush=True)
    pass_message(
        "run_backup_restore_rehearsal completed successfully (restore-scoped URLs pinned; smoke is not a DB-binding proof)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
