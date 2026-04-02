# Surgical Recovery PR Summary

## What this PR does
- Reconciles the recovery packet docs into a clean narrow branch from exact `origin/main`.
- Applies the validated dependency / CI recovery updates only.
- Preserves recovery execution, validation, and completion evidence in `docs/recovery/**`.

## Included scope
- `docs/recovery/**`
- Approved recovery-packet docs reconciliation files:
  - `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md`
  - `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md`
  - `.ai-factory/plans/messaging-stack-modernization.md`
  - `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md`
  - `docs/ONLINE_QUEUE_SYSTEM_GUIDE.md`
  - `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`
  - `docs/ONLINE_QUEUE_SYSTEM_V2.md`
  - `docs/QUEUE_ARCHITECTURE_FIX_PLAN.md`
  - `docs/QUEUE_MIGRATION_REPORT.md`
  - `docs/QUEUE_SYSTEM_ARCHITECTURE.md`
  - `docs/QUEUE_SYSTEM_FIXES.md`
  - `docs/QUEUE_SYSTEM_IMPROVEMENTS.md`
  - `docs/README.md`
  - `docs/runbooks/MESSAGING_CONTRACT.md`
  - `docs/runbooks/MESSAGING_QA_CHECKLIST.md`
- Dependency / CI recovery files:
  - `.github/workflows/ci-cd-unified.yml`
  - `.github/workflows/load-testing.yml`
  - `.github/workflows/monitoring.yml`
  - `.github/workflows/security-scan.yml`
  - `backend/pyproject.toml`
  - `backend/requirements.txt`

## What was intentionally not included
- No `frontend/**` runtime changes.
- No `backend/**` runtime service changes.
- No `docs/status/**` content.
- No EMR / patient / cashier / payment / queue feature content.
- No blind merge of PR #144 or PR #145 history.

## Validation performed
- `git diff --check`
- workflow YAML parse
- backend import smoke
- targeted backend pytest (`8 passed`)
- forbidden artifact scan

## Residual risk
- Dependency bumps are still subject to full CI and future package churn.
- Recovery docs remain evidence artifacts, not runtime behavior.

## No-blind-merge note
This PR was rebuilt from exact `origin/main` using whitelist-only reconstruction. No unrelated runtime history was imported.
