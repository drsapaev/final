# W1-T4 Status

Date: 2026-03-06  
Task: security housekeeping baseline  
Contract: `.ai-factory/contracts/w1-security-housekeeping.contract.json`  
Status: `done`

## Scope / Guardrails

- Hard rule enforced: dependency upgrades are out of scope.
- Analysis + remediation planning only.
- No mass patching and no protected-domain rewrites.

## Evidence

- Backend dependency audit: `pip-audit --format json`
  - `15` vulnerable packages, `33` vulnerability records.
- Backend static scan:
  - `bandit -r . -f json` (findings present)
  - `bandit -r app -lll` summary -> high `18`, medium `16`, low `127`.
- Frontend dependency audit: `npm audit --json`
  - total `16`, critical `2`, high `7`, moderate `7`.

## Required Artifacts

- `docs/security/SECURITY_HOUSEKEEPING_REPORT.md`
- `docs/status/WAVE1_FOUND_ISSUES.md`
- `docs/status/WAVE1_SAFE_FOLLOWUP_TASKS.md`
- `docs/status/WAVE1_PR_PATCH_TEST_SUMMARIES.md`

## Acceptance Check

- Vulnerability and static-analysis baseline captured.
- Prioritized remediation plan documented.
- No dependency upgrade executed in this task.

