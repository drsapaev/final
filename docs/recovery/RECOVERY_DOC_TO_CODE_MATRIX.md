# Recovery Doc-to-Code Matrix

## Evidence Summary
- Current notifications code paths in main: `backend/app/models/notification.py`, `backend/app/services/notification_platform_service.py`, `backend/app/api/v1/endpoints/notifications.py`, `frontend/src/contexts/NotificationCenterContext.jsx`, `frontend/src/components/notifications/RoleNotificationCenter.jsx`, `frontend/src/components/notifications/NotificationInbox.jsx`, `frontend/src/services/notify.js`.
- Current EMR / staging baseline docs: `docs/runbooks/EMR_V2_HARD_CUTOVER_RUNBOOK.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`, `docs/PANEL_QA_CHECKLIST.md`.
- Historical evidence docs: `.ai-factory/plans/*`, `.ai-factory/logs/*`, and older queue architecture reports.

| document | promised / described change | status in current main | gap | recommendation |
|---|---|---|---|---|
| `docs/QUEUE_SYSTEM_ARCHITECTURE.md` | Queue SSOT guide for DailyQueue / OnlineQueueEntry / QueueToken. | Current main still uses the same queue domain, but the wording is partially stale. | Queue model and operator language need refresh. | Update in place |
| `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` | Centralized NotificationSenderService + Celery architecture. | Current main now uses backend-owned persistent inbox/history and unified notify adapter paths instead. | Architecture is now different, not just renamed. | Archive |
| `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md` | Full implementation guide for the earlier online queue stack. | Current main has later SSOT docs and runbooks. | Historical implementation details only. | Archive |
| `docs/QUEUE_ARCHITECTURE_FIX_PLAN.md` | Queue architecture fix plan. | Current main has already moved beyond the original fix-plan framing. | Pre-main planning artifact. | Archive |
| `docs/QUEUE_MIGRATION_REPORT.md` | Queue migration report and steps. | Current main absorbed the important queue direction already. | Historical narrative only. | Archive |
| `docs/QUEUE_SYSTEM_FIXES.md` | Queue-system fixes writeup. | Current main has later queue truth and runbooks. | Older fixes are subsumed. | Archive |
| `docs/QUEUE_SYSTEM_IMPROVEMENTS.md` | Queue-system improvement notes. | Current main already contains the later queue platform direction. | Older improvement plan is stale. | Archive |
| `docs/runbooks/EMR_V2_HARD_CUTOVER_RUNBOOK.md` | EMR v2 cutover, backfill, verification, rollback. | Current main aligns with the cutover result and this remains operationally relevant. | None. | Keep current |
| `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` | Local staging acceptance flow. | Current main and the recovery audit both rely on this contour. | None. | Keep current |
| `docs/PANEL_QA_CHECKLIST.md` | Panel smoke and acceptance checklist. | Current main still uses the same acceptance gating pattern. | None. | Keep current |
| `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md` | Messaging audit evidence and status history. | Evidence-only log. | None. | Keep current |
| `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md` | Panel QA implementation status log. | Evidence-only log. | None. | Keep current |
| `.ai-factory/plans/feat-unified-notifications-strong.md` | Unified notifications platform plan. | Current main has the implementation that matches this plan. | None. | Keep current |
| `.ai-factory/plans/messaging-stack-modernization.md` | Earlier messaging-stack modernization plan. | Current notifications stack supersedes the older assumptions. | Historical but still useful. | Keep current as evidence |
| `docs/ONLINE_QUEUE_SYSTEM_GUIDE.md` | User-facing online queue guide. | Likely stale alongside the implementation docs. | Needs SSOT verification before reuse. | Archive after verification |
| `docs/ONLINE_QUEUE_SYSTEM_V2.md` | Version 2 online queue guide. | Likely stale alongside the implementation docs. | Needs SSOT verification before reuse. | Archive after verification |

## Triage Rules
- `Update` means the doc is still an active operational SSOT but needs wording refresh to match current runtime.
- `Archive` means the doc is historical evidence or a stale architecture description that conflicts with current main.
- `Keep current` means the doc still matches the current runtime and should remain the operator reference.
