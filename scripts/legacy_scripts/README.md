# Legacy scripts

One-off scripts that accumulated at the repo root (and `backend/` root) during
development. They are kept for reference but **not wired into anything** — they
are not tested, not part of CI, and may have hard-coded paths that no longer
exist.

## Layout

```
scripts/legacy_scripts/
├── README.md         ← this file
├── root/             ← 37 files that were at repo root (P0.4)
│   ├── create_*.py   — ad-hoc DB/table creation (superseded by Alembic)
│   ├── check_*.py    — debugging scripts to inspect specific records
│   ├── fix_*.py      — one-shot data fixups
│   ├── setup_*.py    — provider/AI setup helpers
│   └── restart_all.py, simple_test.py, start_mcp_test_server.py — dev tools
└── backend/          ← 97 files that were at backend/ root (V5)
    ├── create_*.py   (19) — admin/user/table creation scripts
    ├── fix_*.py      (8)  — auth/DB/data fixups
    ├── ws_*.py       (5)  — WebSocket test scripts
    ├── update_*.py   (5)  — schema/data updates (should be Alembic)
    ├── run_*.py      (4)  — server launchers (use uvicorn directly)
    ├── quick_*.py    (4)  — quick smoke checks
    ├── final_*.py    (4)  — final integration tests
    ├── start_*.py    (3)  — server starters
    ├── simple_*.py   (3)  — minimal test scripts
    ├── setup_*.py    (3)  — provider/AI setup
    └── 39 others     — one-off debugging/migration scripts
```

## What to do with them

- **Do NOT run blindly** — many assume a specific DB state or env vars.
- **Do NOT add new files here.** New ops scripts go into `backend/app/scripts/`
  (production Python, imported by app code) or `backend/scripts/` (CLI-only).
- **Delete aggressively** — same rule as legacy_tests. If a script hasn't been
  touched in 6 months and doesn't reproduce a current bug, delete it.
- **Migration scripts**: anything that mutates the DB schema belongs in
  `backend/alembic/versions/`, not here.

## Why this matters

Same reasoning as `legacy_tests/README.md`. Root-level scripts confuse AI
agents (they look like first-class code) and shadow real ops tooling.

The pre-commit hook `no-stray-backend-root-scripts` (added in V5) now blocks
any new `.py` file at `backend/` root from being committed — they must go in
`backend/app/scripts/` (production) or `scripts/legacy_scripts/backend/`
(one-off).

## Counts after V5 cleanup

- Repo root: 0 stray `.py` files (was 37 before P0.4)
- `backend/` root: 0 stray `.py` files (was 97 before V5)
- `scripts/legacy_scripts/root/`: 37 archived files
- `scripts/legacy_scripts/backend/`: 97 archived files
- **Total archived**: 134 files
