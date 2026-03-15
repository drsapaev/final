# W2D Operator Runbook Command Normalization Status

Status: completed

What changed:

- added canonical command map in
  `C:/final/docs/OPERATOR_STARTUP_COMMANDS.md`
- aligned root, ops, and production docs to the same explicit operator flow

Docs updated:

- `C:/final/docs/OPERATOR_STARTUP_COMMANDS.md`
- `C:/final/README.md`
- `C:/final/ops/README.md`
- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`

Validation:

- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`

Result:

- command examples no longer compete across root/ops/production docs
- the operator-first startup story now has one short canonical command map

Next step:

- `C:/final/docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_OPERATOR_RUNBOOK_COMMAND_NORMALIZATION.md`

