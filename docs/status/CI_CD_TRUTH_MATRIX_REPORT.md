# CI/CD Truth Matrix Report

Date: 2026-03-06  
Task: W1-T1  
Contract: `.ai-factory/contracts/w1-ci-truth-matrix.contract.json`  
Status: `done`

## Scope Confirmation

- Code changes: none.
- Paths changed: docs/status only.
- Hard rule enforced: W1-T1 docs/reports only.

## Workflow Truth Snapshot

### Unified CI (`ci-cd-unified.yml`)

| Run ID | Date (UTC) | Branch | SHA | Event | Conclusion | Key note |
|---|---|---|---|---|---|---|
| `22748643145` | 2026-03-06 04:09 | `main` | `32e7ee04593319e072ca8ee9358830d5ac923481` | schedule | failure | `🎨 Frontend тесты` failed |
| `22717403048` | 2026-03-05 12:14 | `main` | `32e7ee04593319e072ca8ee9358830d5ac923481` | push | failure | same SHA, same failing slice |
| `22701910411` | 2026-03-05 04:11 | `main` | `e1c47dc80b62553e4c07a57ec72eb819963bc38b` | schedule | success | latest known green baseline on `main` |

### Failed Job Detail (run `22748643145`)

- Failing job: `🎨 Frontend тесты` (`job 65977991241`)
- Core error:
  - `[vitest] No "tokenManager" export is defined on the "../../../utils/tokenManager" mock`
  - source trace includes `src/api/client.js:287` and `src/components/security/TwoFactorManager.jsx:19`
- Side effect:
  - `🧱 Context Boundary Integrity` skipped
  - `🔄 Frontend-Backend Parity` skipped

### Role Integrity Workflow (`role-system-check.yml`)

- Latest run on `main`: `22717403106` (2026-03-05) → success.
- Recent main runs are green for this workflow.

### Security Scan Workflow (`security-scan.yml`)

- Latest scheduled run on `main`: `22749005093` (2026-03-06) → success.
- Security scan workflow is green, but this does not override unified CI failure.

## PR Backlog Snapshot

- Open PR count: `30`
- Palette PRs: `12`
- Dependabot PRs: `17`
- Draft PRs: `1`
- Merge-state risk:
  - `DIRTY`: `15`
  - `UNSTABLE`: `2`

## Commands Executed

- `gh run list --workflow ci-cd-unified.yml --limit 12 --json ...`
- `gh run view 22748643145 --json ...`
- `gh run view 22748643145 --job 65977991241 --log-failed`
- `gh run list --workflow role-system-check.yml --limit 12 --json ...`
- `gh run list --workflow security-scan.yml --limit 12 --json ...`
- `gh pr list --state open --limit 60 --json ...`

## Outcome

W1-T1 acceptance met. CI truth matrix is evidence-backed and current as of 2026-03-06.
