# W1.9-T1 Normalize Backend Pytest Entrypoint

Date: 2026-03-06  
Branch: `codex/w19-gate-blockers`  
Status: `done`

## Problem

`cd backend && pytest -q` was unstable and failed before running the real suite.

Observed blockers:
- `pytest.ini` section header was `"[tool:pytest]"`, so `testpaths=tests` was not applied as intended.
- Root-level script-like files (`backend/test_*.py`) were being collected.
- A collected script (`test_cart_error_debug.py`) executed network calls and exited during import.
- After config recognition, default `--cov*` options failed in this environment (`pytest-cov` plugin not installed), still breaking entrypoint.

## Changes Applied

1. `backend/pytest.ini`
- Changed section header from `[tool:pytest]` to `[pytest]`.
- Removed default `--cov*` flags from `addopts` to keep the root entrypoint deterministic in environments without `pytest-cov`.

2. `backend/test_cart_direct.py`
- Kept as import-safe standalone script (main guard + `SystemExit(main())`) so pytest import does not trigger runtime side effects.

## Scope Compliance

- No business logic changed.
- No integration tests removed.
- No auth/payment/queue/EMR runtime behavior changed.

## Must-Run Evidence

Command:

```bash
cd backend
pytest -q
```

Result:
- Exit code: `0`
- `645 passed, 3 skipped`
- Root entrypoint is stable.

## Diff Summary

- `backend/pytest.ini`: normalize pytest config section and remove coverage-only default arguments.
- `backend/test_cart_direct.py`: standalone script made import-safe for test discovery context.

