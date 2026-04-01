# PR #145 Contamination Report

## Baseline
- Exact `origin/main` SHA: `22da512420a605f94b419e8e5994818e1e88d2fa`
- Exact local `main` SHA: `959d457b8c1f9883a310f12b790c72e1dd4c1c19`
- Surgical rebuild branch target: `codex/recovery-main-surgical`

## Cause hypothesis
PR #145 is contaminated because the earlier recovery execution branch inherited historical runtime content and later accumulated unrelated runtime edits outside the approved recovery packet. The diff shows branch-base drift plus accidental inclusion of historical feature files and status artifacts that are unrelated to the recovery-only scope.

## Approved whitelist for the surgical rebuild
Only the following path classes are allowed in the new PR:
- `docs/recovery/**`
- approved recovery-packet reconciliation docs:
  - `docs/QUEUE_SYSTEM_ARCHITECTURE.md`
  - `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md`
  - `docs/ONLINE_QUEUE_SYSTEM_GUIDE.md`
  - `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`
  - `docs/ONLINE_QUEUE_SYSTEM_V2.md`
  - `docs/QUEUE_ARCHITECTURE_FIX_PLAN.md`
  - `docs/QUEUE_MIGRATION_REPORT.md`
  - `docs/QUEUE_SYSTEM_FIXES.md`
  - `docs/QUEUE_SYSTEM_IMPROVEMENTS.md`
  - `docs/README.md`
  - `docs/runbooks/MESSAGING_CONTRACT.md`
  - `docs/runbooks/MESSAGING_QA_CHECKLIST.md`
  - `.ai-factory/plans/messaging-stack-modernization.md`
  - `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md`
  - `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md`
- workflow/dependency constraint files required for the validated recovery changes:
  - `.github/workflows/ci-cd-unified.yml`
  - `.github/workflows/load-testing.yml`
  - `.github/workflows/monitoring.yml`
  - `.github/workflows/security-scan.yml`
  - `backend/pyproject.toml`
  - `backend/requirements.txt`

## Blacklist examples found in PR #145
These areas are explicitly out of scope and must not be imported:
- `frontend/src/components/emr-v2/*`
- `frontend/src/pages/PatientPanel.jsx`
- `backend/app/services/*`
- `frontend/src/components/cashier/RefundRequestsTable.jsx`
- `frontend/src/components/payment/PaymentManager.jsx`
- `docs/status/*`
- broad `frontend/src/*` runtime UI content

## Recommendation
Rebuild a new narrow PR from exact `origin/main` using whitelist-only reconstruction. Do not merge PR #145.
