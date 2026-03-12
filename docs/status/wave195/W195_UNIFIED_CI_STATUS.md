# W1.95 Unified CI Status

Date: 2026-03-06  
Branch: `codex/w195-gate-recheck`  
Status: `partial`

## Current SHA

- `32e7ee04593319e072ca8ee9358830d5ac923481`

## Latest Unified CI Runs for Current SHA

Workflow: `ci-cd-unified.yml`

1. Run ID `22748643145` (2026-03-06) -> `failure`  
   URL: <https://github.com/drsapaev/final/actions/runs/22748643145>
2. Run ID `22717403048` (2026-03-05) -> `failure`  
   URL: <https://github.com/drsapaev/final/actions/runs/22717403048>

## Failure Reason (Latest Red Run)

From failed job `🎨 Frontend тесты` (`65977991241`):
- failing step: `🧪 Тесты frontend`
- error class: vitest module mock/export mismatch in `TwoFactorManager` test path
- key symptom: missing mocked export for `tokenManager`

## Is Fix Required?

Yes.

Minimal required fix path:
1. Ensure Wave 1.5 frontend test-mock fix for `TwoFactorManager` is present on the tested `main` SHA.
2. Re-run unified CI on `main` for the updated SHA.
3. Confirm one fresh green `ci-cd-unified.yml` run as gate evidence.

No broad refactor is required for this blocker; this is a targeted CI-signal proof gap.

