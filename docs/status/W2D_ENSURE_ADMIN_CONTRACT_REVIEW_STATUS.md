# W2D Ensure Admin Contract Review Status

Status: completed

What changed:

- `C:/final/backend/app/scripts/ensure_admin.py` now requires
  `ADMIN_ALLOW_UPDATE=1` before mutating an existing matched user
- create-if-missing behavior remains available without extra flags
- password reset remains explicit through `ADMIN_RESET_PASSWORD=1`
  and now only applies during an allowed update

Tests added:

- `C:/final/backend/tests/unit/test_ensure_admin_script.py`

Docs/config updated:

- `C:/final/README.md`
- `C:/final/ops/README.md`
- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`
- `C:/final/backend/.env.example`
- `C:/final/ops/.env.example`
- `C:/final/ops/docker-compose.yml`

Validation:

- `cd C:\final\backend && pytest tests/unit/test_ensure_admin_script.py -q`
- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`
- `cd C:\final\backend && $env:PYTHONIOENCODING='utf-8'; python test_server_startup.py`

Result:

- bootstrap remains explicit and available
- existing-user mutation is no longer the default helper behavior
- startup hardening and admin-helper hardening now align around the same
  operator-first model

Next step:

- `C:/final/docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_ENSURE_ADMIN_CONTRACT_REVIEW.md`

