"""Daily encrypted backup of the production PostgreSQL database.

Run by Task Scheduler "Final Supabase Backup" (daily 03:00) or manually:
    C:\\final\\backend\\.venv\\Scripts\\python.exe C:\\final\\backups\\backup_supabase.py

After the local database cutover, use --source local --schema public. This
checks the database identity and keeps local archives separate from Supabase
archives and their retention window.
Add --offsite-r2 to upload only the encrypted local public archive and verify
its size and SHA-256 through R2 HeadObject.

The custom-format pg_dump archive stays in memory. Only its Fernet-encrypted
form is written to the backup directory. The newest 14 backups are retained.
"""
from __future__ import annotations

import argparse
import binascii
import ipaddress
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ROOT = Path(r"C:\final")
PG_DUMP = r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
PG_RESTORE = r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe"
KEEP = 14


def _ssl_mode(host: str) -> str:
    if host.lower() == "localhost":
        return "disable"
    try:
        return "disable" if ipaddress.ip_address(host).is_loopback else "require"
    except ValueError:
        return "require"


def _dump_failure_category(stderr: bytes) -> str:
    details = stderr.lower()
    if b"permission denied" in details or b"must be owner" in details:
        return "permission"
    if b"authentication failed" in details or b"password authentication" in details:
        return "authentication"
    if b"timed out" in details or b"timeout" in details:
        return "timeout"
    if b"too many connections" in details or b"remaining connection slots" in details:
        return "connection_limit"
    if any(
        marker in details
        for marker in (
            b"could not connect",
            b"connection refused",
            b"connection reset",
            b"server closed the connection",
            b"broken pipe",
            b"ssl syscall",
        )
    ):
        return "connection"
    if b"out of memory" in details or b"no space left" in details:
        return "resource"
    return "other"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / "backend" / ".env")
    parser.add_argument("--backup-dir", type=Path, default=ROOT / "backups")
    parser.add_argument("--schema", help="Back up only this schema (default: all schemas)")
    parser.add_argument("--source", choices=("supabase", "local"), default="supabase")
    parser.add_argument("--offsite-r2", action="store_true")
    args = parser.parse_args(argv)

    if not args.backup_dir.is_dir():
        print("BACKUP FAILED: backup directory does not exist")
        return 1
    if args.schema is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.schema):
        print("BACKUP FAILED: schema name must be a simple identifier")
        return 1
    if args.offsite_r2 and (args.source != "local" or args.schema != "public"):
        print("BACKUP FAILED: offsite upload requires the local public schema")
        return 1

    try:
        env = dotenv_values(args.env_file)
        url = make_url(env["DATABASE_URL"])
        fernet = Fernet(env["ENCRYPTION_KEY"])
        host = url.host or "localhost"
        if not url.username:
            raise ValueError("database user is missing")
    except (KeyError, TypeError, ValueError, OSError, ArgumentError, binascii.Error):
        print("BACKUP FAILED: invalid backup configuration")
        return 1

    if args.source == "local":
        if (host, url.port, url.username, url.database) != (
            "127.0.0.1", 5432, "clinic_local_app", "clinic_prod_local"
        ):
            print("BACKUP FAILED: local database identity mismatch")
            return 1
    elif not host.lower().endswith(".supabase.com"):
        print("BACKUP FAILED: Supabase source identity mismatch")
        return 1
    if args.offsite_r2 and not all(
        (env.get(key) or "").strip()
        for key in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    ):
        print("BACKUP FAILED: offsite configuration is missing")
        return 1

    sub_env = os.environ.copy()
    sub_env["PGPASSWORD"] = url.password or ""
    sub_env["PGSSLMODE"] = _ssl_mode(host)
    t0 = time.monotonic()
    dump_command = [
        PG_DUMP,
        "-h", host,
        "-p", str(url.port or 5432),
        "-U", url.username,
        "-d", url.database or "postgres",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
    ]
    if args.schema is not None:
        dump_command.append(f"--schema={args.schema}")
    try:
        result = subprocess.run(
            dump_command,
            env=sub_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        print("BACKUP FAILED: pg_dump could not start")
        return 1

    if result.returncode != 0:
        category = _dump_failure_category(result.stderr or b"")
        print(f"BACKUP FAILED: pg_dump rc={result.returncode} category={category}")
        return 1
    if not result.stdout.startswith(b"PGDMP"):
        print("BACKUP FAILED: pg_dump returned an invalid archive")
        return 1
    archive = result.stdout
    del result
    dump_secs = time.monotonic() - t0

    try:
        check = subprocess.run(
            [PG_RESTORE, "--list"],
            input=archive,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        print("BACKUP FAILED: pg_restore could not start")
        return 1
    if check.returncode != 0:
        print(f"BACKUP FAILED: archive verification rc={check.returncode}")
        return 1

    encrypted = fernet.encrypt(archive)
    del archive
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if args.source == "local":
        backup_prefix = (
            "local_prod" if args.schema is None else f"local_prod_schema_{args.schema}"
        )
    else:
        backup_prefix = (
            "supabase_prod" if args.schema is None else f"supabase_schema_{args.schema}"
        )
    enc = args.backup_dir / f"{backup_prefix}_{ts}.dump.enc"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{enc.name}.",
            suffix=".tmp",
            dir=args.backup_dir,
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(encrypted)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, enc)
        temporary = None
    except OSError:
        print("BACKUP FAILED: encrypted backup could not be published")
        return 1
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        older = sorted(
            (
                path for path in args.backup_dir.glob(f"{backup_prefix}_*.dump.enc")
                if path != enc
            ),
            key=lambda path: path.stat().st_mtime,
        )
        for stale in older[:-(KEEP - 1)]:
            stale.unlink()
        kept = min(len(older), KEEP - 1) + 1
    except OSError:
        print(f"BACKUP SAVED: {enc.name}; retention cleanup failed")
        return 1

    if args.offsite_r2:
        try:
            sys.path.insert(0, str(ROOT / "backend"))
            from app.services import r2_uploader

            for key in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
                os.environ[key] = (env[key] or "").strip()
            if env.get("R2_BUCKET"):
                os.environ["R2_BUCKET"] = env["R2_BUCKET"].strip()
            else:
                os.environ.pop("R2_BUCKET", None)
            r2_key = f"daily/encrypted-public/{enc.name}"
            r2_uploader.upload_file(key=r2_key, filepath=enc)
        except Exception as exc:
            # Manifest is intentionally NOT updated on failure: health reads
            # it as "the whole chain (dump -> local archive -> R2 verify)
            # succeeded", so a broken upload must age the old manifest out
            # and keep the stale alarm active.
            print(f"BACKUP SAVED: {enc.name}; offsite verification failed ({type(exc).__name__})")
            return 1

        # Success manifest — written ONLY after the full chain succeeded
        # (identity check -> dump -> archive verify -> encrypt -> retention
        # -> R2 upload with size+SHA-256 HeadObject verification).
        # /health/detailed reads this file instead of scanning archive
        # mtimes, so a broken upload keeps the stale alarm active.
        import hashlib as _hashlib
        import json as _json

        manifest = {
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": args.source,
            "schema": args.schema,
            "archive": enc.name,
            "size_bytes": enc.stat().st_size,
            "sha256": _hashlib.sha256(enc.read_bytes()).hexdigest(),
            "r2_verified": True,
            "r2_key": r2_key,
        }
        manifest_path = args.backup_dir / "last_backup_report.json"
        try:
            tmp_manifest = manifest_path.with_suffix(".json.tmp")
            tmp_manifest.write_text(
                _json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(tmp_manifest, manifest_path)
        except OSError as exc:
            print(f"backup ok: {enc.name}; manifest write failed ({type(exc).__name__}: {exc})")
            return 1

    print(
        f"backup ok: {enc.name} | {enc.stat().st_size} bytes | "
        f"dump {dump_secs:.0f}s | total kept {kept}"
        + (" | offsite verified" if args.offsite_r2 else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
