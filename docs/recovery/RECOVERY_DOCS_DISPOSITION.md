# Recovery Docs Disposition

## Keep Current
These are still current operator-facing docs or active acceptance references.

| document | why |
|---|---|
| `docs/runbooks/EMR_V2_HARD_CUTOVER_RUNBOOK.md` | Current EMR v2 cutover and verification reference. |
| `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | Current local staging contour and acceptance flow. |
| `docs/PANEL_QA_CHECKLIST.md` | Current panel smoke / acceptance checklist. |
| `.ai-factory/plans/feat-unified-notifications-strong.md` | Current notifications plan that matches main. |

## Keep As Historical Evidence
These files are useful as audit history, but they are not the active runtime SSOT.

| document | why |
|---|---|
| `.ai-factory/plans/messaging-stack-modernization.md` | Historical messaging plan now superseded by current notifications implementation. |
| `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md` | Evidence log for the messaging recovery path. |
| `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md` | Evidence log for panel QA work. |
| `frontend/docs/NOTIFICATION_ADAPTER.md` | Precursor adapter note; useful as history, not as the active contract. |
| `docs/reports/NOTIFICATION_FUNCTION_ANALYSIS_ALL_PANELS_2026-03-23.md` | Historical notifications analysis report. |
| `docs/reports/NOTIFICATION_TASKS_PROGRESS_2026-03-25.md` | Historical notifications progress report. |
| `docs/runbooks/MESSAGING_CONTRACT.md` | Historical messaging contract reference. |
| `docs/runbooks/MESSAGING_QA_CHECKLIST.md` | Historical messaging QA checklist. |

## Update To Current Architecture
These should be refreshed to match current main, not archived as-is.

| document | why |
|---|---|
| `docs/QUEUE_SYSTEM_ARCHITECTURE.md` | Still the queue SSOT, but wording should match current main and the current staging contour. |

## Archive / Deprecated
These are pre-main narratives or architecture descriptions that conflict with current main.

| document | why |
|---|---|
| `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` | Describes the older sender-service/Celery style architecture, not current main. |
| `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md` | Historical online-queue implementation guide, now superseded. |
| `docs/QUEUE_ARCHITECTURE_FIX_PLAN.md` | Pre-main fix plan, now evidence only. |
| `docs/QUEUE_MIGRATION_REPORT.md` | Historical migration report, superseded by later queue truth. |
| `docs/QUEUE_SYSTEM_FIXES.md` | Older queue fixes report, superseded. |
| `docs/QUEUE_SYSTEM_IMPROVEMENTS.md` | Older queue improvements report, superseded. |
| `docs/ONLINE_QUEUE_SYSTEM_GUIDE.md` | Older queue guide, superseded by current SSOT docs and runbooks. |
| `docs/ONLINE_QUEUE_SYSTEM_V2.md` | Older queue guide variant, superseded. |

## Notes
- Notifications: archive the architecture doc, keep the plan/logs as evidence, and keep the current notifications plan only because it matches main.
- Queue: update the SSOT doc, archive the old implementation/report docs.
- Messaging: keep the contract/QA docs only as historical evidence.
- Runbooks and panel QA: keep them current.
