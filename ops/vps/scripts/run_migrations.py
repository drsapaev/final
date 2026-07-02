#!/usr/bin/env python3
from __future__ import annotations

from clinic_lifecycle_common import (
    backend_alembic_cmd,
    backend_dir,
    fail,
    load_clinic_env,
    parse_database_url,
    pass_message,
    require_env,
    run_command,
)


def main() -> int:
    load_clinic_env()
    parse_database_url(require_env("DATABASE_URL"))

    cmd = backend_alembic_cmd()
    run_command(cmd + ["upgrade", "head"], cwd=backend_dir())
    current = run_command(cmd + ["current"], cwd=backend_dir())
    if current.returncode != 0:
        fail("alembic current failed after upgrade")

    pass_message("run_migrations completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
