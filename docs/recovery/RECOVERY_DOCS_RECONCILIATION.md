# Recovery Docs Reconciliation

## Scope
- Stage executed: `Stage 1 - Docs reconciliation only`
- Runtime/code changes: `none`
- Basis: `docs/recovery/RECOVERY_DOCS_DISPOSITION.md`

## Changed Docs

| document | action taken | why | current source of truth replacement | risk if left stale |
|---|---|---|---|---|
| `docs/QUEUE_SYSTEM_ARCHITECTURE.md` | updated header and current-truth guidance | Packet classified this as the only queue doc to refresh, not archive | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`, `docs/PANEL_QA_CHECKLIST.md`, queue runtime on `main` | Engineers could keep treating old queue fix/migration docs as active implementation guidance |
| `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` | added deprecated/historical banner | Document describes older sender-service / Celery path that does not match current notifications platform | `.ai-factory/plans/feat-unified-notifications-strong.md`, `backend/app/api/v1/endpoints/notifications.py`, `backend/app/services/notification_platform_service.py` | Notification work could drift toward superseded architecture |
| `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md` | added deprecated/historical banner | Pre-main implementation narrative is not the current queue runtime contract | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | Queue work could follow a stale implementation narrative |
| `docs/ONLINE_QUEUE_SYSTEM_GUIDE.md` | added deprecated/historical banner | Old operator guide is no longer the current queue entry point | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | Users could start from deprecated queue guidance |
| `docs/ONLINE_QUEUE_SYSTEM_V2.md` | added deprecated/historical banner | Historical narrative conflicts with current main contour | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | Confusion between historical and current queue flows |
| `docs/QUEUE_ARCHITECTURE_FIX_PLAN.md` | marked as historical fix plan | Packet classified it as archive/deprecated, not current contract | `docs/QUEUE_SYSTEM_ARCHITECTURE.md` | Fix-plan TODOs could be mistaken for active backlog |
| `docs/QUEUE_MIGRATION_REPORT.md` | marked as historical migration report | Report remains useful as evidence, but not as current queue runtime guide | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | Migration-era assumptions could be reused incorrectly |
| `docs/QUEUE_SYSTEM_FIXES.md` | marked as historical fix report | Older fixes are superseded by current queue SSOT and runbooks | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/PANEL_QA_CHECKLIST.md` | Readers could treat partial historical fixes as full current truth |
| `docs/QUEUE_SYSTEM_IMPROVEMENTS.md` | marked as historical improvement report | Older improvements report is evidence-only now | `docs/QUEUE_SYSTEM_ARCHITECTURE.md` | Could inflate confidence in outdated behavior |
| `docs/runbooks/MESSAGING_CONTRACT.md` | relabeled as historical evidence | Packet classified messaging docs as historical evidence, not current global SSOT | current `main` code + active runbooks, especially `docs/PANEL_QA_CHECKLIST.md` for operator flow | Messaging lane docs could be misread as the primary current product contract |
| `docs/runbooks/MESSAGING_QA_CHECKLIST.md` | relabeled as historical evidence | Keep as evidence without presenting it as the live clinic-wide QA standard | `docs/PANEL_QA_CHECKLIST.md` plus active role runbooks | Operators could run stale messaging-only QA as if it were the main acceptance runbook |
| `.ai-factory/plans/messaging-stack-modernization.md` | added historical-plan note | Preserve planning evidence without implying this plan still governs implementation | current `main`, active runbooks, recovery packet | Historical plan could be mistaken for live execution contract |
| `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md` | added historical-log note | Preserve audit trail without promoting it to live SSOT | current `main`, recovery docs | Old log findings could be misread as current blockers |
| `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md` | added historical-log note | Preserve execution history while keeping `docs/PANEL_QA_CHECKLIST.md` as active runbook | `docs/PANEL_QA_CHECKLIST.md` | Historical execution state could be mistaken for the active checklist |
| `docs/README.md` | updated descriptions and quick-navigation order | Prevent docs index from surfacing stale queue/messaging docs as if they were current guidance | `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`, `docs/PANEL_QA_CHECKLIST.md` | Readers could continue entering the stale docs from the main index |

## Keep Current (No File Changes Needed)

| document | action taken | why |
|---|---|---|
| `docs/runbooks/EMR_V2_HARD_CUTOVER_RUNBOOK.md` | no-op | Already aligned with current `main` and still active |
| `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | no-op | Already current and referenced more prominently after reconciliation |
| `docs/PANEL_QA_CHECKLIST.md` | no-op | Already active SSOT for panel verification |
| `.ai-factory/plans/feat-unified-notifications-strong.md` | no-op | Packet already classified it as current and aligned to `main` |

## Historical Evidence / Path Drift Notes

| packet reference | observed state on execution branch | action taken | note |
|---|---|---|---|
| `frontend/docs/NOTIFICATION_ADAPTER.md` | path absent | no file created | Recorded as packet/reference-path drift; no safe reason to invent a historical file |
| `docs/reports/NOTIFICATION_FUNCTION_ANALYSIS_ALL_PANELS_2026-03-23.md` | path absent | no file created | Historical report path from packet not present on current execution branch |
| `docs/reports/NOTIFICATION_TASKS_PROGRESS_2026-03-25.md` | path absent | no file created | Historical report path from packet not present on current execution branch |

## Result
- Stale docs are now clearly marked as `historical` or `deprecated`.
- Current queue/operator docs remain the primary entry points.
- Evidence logs and historical plans were preserved, not rewritten as current truth.
