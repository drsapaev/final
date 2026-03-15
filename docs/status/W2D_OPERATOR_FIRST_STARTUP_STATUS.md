# W2D Operator-First Startup Status

Status: completed

What changed:

- implicit schema bootstrap was removed from
  `C:/final/ops/backend.entrypoint.sh`
- `ENSURE_ADMIN` now defaults to `0`
- explicit admin bootstrap remains available through
  `python app/scripts/ensure_admin.py` and `ENSURE_ADMIN=1`
- startup/docs/config examples were updated to describe the new explicit flow

Runtime/config surfaces updated:

- `C:/final/ops/backend.entrypoint.sh`
- `C:/final/ops/docker-compose.yml`
- `C:/final/ops/.env.example`
- `C:/final/backend/.env.example`

Docs updated:

- `C:/final/README.md`
- `C:/final/ops/README.md`
- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`
- `C:/final/docs/architecture/W2D_OPERATOR_FIRST_STARTUP.md`

Validation:

- `& 'C:\Program Files\Git\bin\bash.exe' -n C:/final/ops/backend.entrypoint.sh`
- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`
- `cd C:\final\backend && $env:PYTHONIOENCODING='utf-8'; python test_server_startup.py`

Result:

- startup no longer mutates schema implicitly
- startup no longer mutates admin state by default
- explicit operator-controlled bootstrap remains available
- the repo now documents an operator-first startup order more honestly

Next step:

- `C:/final/docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_STARTUP_HARDENING.md`
