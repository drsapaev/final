# W1-T2 Status

Date: 2026-03-06  
Task: docs vs code ground truth  
Contract: `.ai-factory/contracts/verify-docs-vs-code.contract.json` (Wave 1 narrowed)  
Status: `partial`

## Scope / Guardrails

- Hard rule enforced: if mismatch found, report only; do not auto-refactor code.
- Work performed as verification + reporting.
- No application behavior refactor executed for this task.

## Evidence

- OpenAPI regeneration completed: `paths=971`, `operations=1112`.
- Contract tests: `pytest tests/test_openapi_contract.py -q` -> `10 passed`.
- RBAC parity frontend test: `npm run test:run -- src/test/parity/rbacRouteParity.test.js` -> `4 passed`.
- Parity reports rebuilt; quality gate passed with low broad coverage (`coverage_pct=11.51`, `missing_in_frontend=990`).
- Docs drift scan found `46` optimistic-claim matches across `docs/**`.

## Required Artifacts

- `docs/status/REPORT_GROUND_TRUTH.md`
- `docs/status/WAVE1_FOUND_ISSUES.md`

## Acceptance Check

- Mismatch inventory delivered with evidence.
- No automatic code refactor applied.
- Status remains `partial` because broad docs normalization was intentionally deferred to follow-up slices.

