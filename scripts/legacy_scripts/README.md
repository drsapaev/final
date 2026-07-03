# Legacy scripts

One-off scripts that accumulated at the repo root during development:
- `create_*.py` — ad-hoc DB/table creation scripts (superseded by Alembic)
- `check_*.py` — debugging scripts to inspect specific records/state
- `fix_*.py` — one-shot data fixups
- `setup_*.py` — provider/AI setup helpers
- `restart_all.py`, `simple_test.py`, `start_mcp_test_server.py` — dev tools

These are kept for reference but **not wired into anything**. They are not
tested, not part of CI, and may have hard-coded paths that no longer exist.

## What to do with them

- **Do NOT run blindly** — many assume a specific DB state or env vars.
- **Do NOT add new files here.** New ops scripts go into `backend/scripts/`
  (Python) or `scripts/` (cross-cutting).
- **Delete aggressively** — same rule as legacy_tests.
- **Migration scripts**: anything that mutates the DB schema belongs in
  `backend/alembic/versions/`, not here.

## Why this matters

Same reasoning as `legacy_tests/README.md`. Root-level scripts confuse AI
agents (they look like first-class code) and shadow real ops tooling.
