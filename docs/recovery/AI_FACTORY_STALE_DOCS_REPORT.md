# AI Factory Stale Docs Report

| Doc path | What is outdated | What current main actually does | Action |
|---|---|---|---|
| `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` | Old sender-service / Celery notification architecture | Current main uses the notification platform service, notification inbox context, and websocket normalization | Archive / deprecated |
| `docs/runbooks/MESSAGING_CONTRACT.md` | It is historical evidence, not the live product SSOT | Current main owns the chat contract in code (`backend/app/core/messaging_contract.py`, `backend/app/ws/chat_ws.py`) | Keep as historical evidence only |
| `docs/runbooks/MESSAGING_QA_CHECKLIST.md` | It is a messaging rollout history artifact, not the primary clinic-wide acceptance runbook | Current main uses `docs/PANEL_QA_CHECKLIST.md` plus active role runbooks for operator truth | Keep as historical evidence only |
| `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md` | Early online-queue implementation narrative | Current main uses the queue SSOT docs and current queue code (`DailyQueue`, `OnlineQueueEntry`, `QueueToken`) | Archive / deprecated |
| `docs/QUEUE_ARCHITECTURE_FIX_PLAN.md` | Historical queue fix plan | Current main already has the queue SSOT and the old fix plan is superseded | Archive / deprecated |
| `docs/QUEUE_MIGRATION_REPORT.md` | Migration report for older queue evolution | Current main uses the current queue SSOT and current runbooks | Archive / deprecated |
| `docs/QUEUE_SYSTEM_FIXES.md` | Superseded queue-fix summary | Current main already contains the queue SSOT and current acceptance references | Archive / deprecated |
| `docs/QUEUE_SYSTEM_IMPROVEMENTS.md` | Superseded queue-improvement summary | Current main uses `docs/QUEUE_SYSTEM_ARCHITECTURE.md` and `docs/ONLINE_QUEUE_SYSTEM_V2.md` as the live docs | Archive / deprecated |
| `docs/archives/QUEUE_*` bundle | Old queue reports / plans / implementations | Current main has current queue SSOT docs and runtime code | Archive / deprecated |
| `docs/archives/UNIFIED_PANELS_IMPROVEMENT_PLAN.md` | Old panel-improvement plan | Current main uses the panel QA checklist and current panel code paths | Archive / deprecated |
| `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md` | Initial findings are no longer current | Current main now contains `broadcast_event`, `notify_messages_read`, and the versioned WS contract | Keep as historical evidence only |
| `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md` | It is execution history, not current operator truth | Current main uses `docs/PANEL_QA_CHECKLIST.md` and the current acceptance contour | Keep as historical evidence only |

## Current SSOT Replacements

- Notifications: `backend/app/api/v1/endpoints/notifications.py`, `backend/app/services/notification_platform_service.py`, `frontend/src/contexts/NotificationCenterContext.jsx`
- Messaging: `backend/app/core/messaging_contract.py`, `backend/app/ws/chat_ws.py`, `backend/app/api/v1/endpoints/messages.py`
- Queue: `backend/app/models/online_queue.py`, `backend/app/services/queue_service.py`, `docs/QUEUE_SYSTEM_ARCHITECTURE.md`
- Panel QA: `docs/PANEL_QA_CHECKLIST.md`
- EMR cutover: `docs/runbooks/EMR_V2_HARD_CUTOVER_RUNBOOK.md`, `backend/app/api/v1/endpoints/appointment_flow.py`

