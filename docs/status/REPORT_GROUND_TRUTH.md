# Ground Truth Report

Date: 2026-03-06  
Task: W1-T2  
Contract used: `.ai-factory/contracts/verify-docs-vs-code.contract.json` (narrowed by Wave 1 hard rules)  
Status: `partial`

## Scope and Hard Rule Check

- Scope executed: verification and reporting against docs/code/CI artifacts.
- Hard rule enforced: if mismatch found, report only; no auto-refactor of app code.
- No backend/frontend behavior edits were applied by this task.

## Verified Facts

1. `main` currently has failed unified CI runs (`22748643145`, `22717403048`) on SHA `32e7ee04593319e072ca8ee9358830d5ac923481`.
2. Failure reason is deterministic in frontend tests: missing `tokenManager` export in `TwoFactorManager` test mock.
3. OpenAPI generation succeeds and produces:
   - `paths=971`
   - `operations=1112`
4. `tests/test_openapi_contract.py` passes (`10 passed`).
5. RBAC parity frontend test passes (`4 passed`).
6. Latest parity report rebuild passes gate but shows low total coverage:
   - `coverage_pct=11.51`
   - `missing_in_frontend=990`
   - `critical_flows failed=0`
7. Docs optimism drift remains significant:
   - `46` matches of patterns like `100%`, `fully integrated`, `ready`.

## Mismatch Inventory (No Auto-Refactor Applied)

- Documentation claims full readiness/integration in multiple files (examples):
  - `docs/AI_MCP_IMPLEMENTATION_SUMMARY.md`
  - `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md`
  - `docs/DOCUMENTATION_UPDATE_REPORT.md`
- Runtime CI reality contradicts blanket completion statements while `main` is red.
- Contract parity gate can pass critical flows while broad operation coverage remains low, so "fully aligned" wording is unsafe.

## Commands Executed

- `python generate_openapi.py`
- `pytest tests/test_openapi_contract.py -q`
- `npm run test:run -- src/test/parity/rbacRouteParity.test.js`
- `python ops/scripts/extract_frontend_api_usage.py --log-level INFO`
- `python ops/scripts/build_frontend_backend_parity.py --log-level INFO`
- `python ops/scripts/check_frontend_backend_parity.py --min-correctness 4.0 --min-usability 4.0 --log-level INFO`
- docs-claim scan:
  - `Select-String` over `docs/**` with patterns `100%|production ready|fully integrated|...`

## Why Status Is Partial

- Verification is complete and evidence is captured.
- Full normalization of legacy docs claims was intentionally not done in this task to avoid broad docs churn.
- Follow-up cleanup is explicitly queued (see `WAVE1_SAFE_FOLLOWUP_TASKS.md`).
