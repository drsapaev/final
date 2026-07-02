# AI Factory Domain Summary

## 1. EMR

- **Docs promised / claimed:** EMR v2 hard cutover, canonical `visit_id`, legacy write freeze, backfill, local staging rehearsal, specialist-panel routing.
- **Current main evidence:** `backend/app/api/v1/endpoints/appointment_flow.py`, `backend/app/api/v1/api.py`, `docs/runbooks/EMR_V2_HARD_CUTOVER_RUNBOOK.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`, `.ai-factory/ROADMAP.md`.
- **What is real now:** EMR v2, canonical visit handling, and the hard-cutover runbook are present.
- **What is partial:** the acceptance flow is documented and evidenced, but it is still an operator process rather than a runtime subsystem.
- **Stale docs:** old queue/notification docs are not the source of truth for EMR, and old legacy EMR references should stay historical.
- **Do not continue:** any attempt to re-open the old appointment-based EMR architecture as if it were current truth.

## 2. Notifications / Messaging

- **Docs promised / claimed:** backend-owned inbox, server-authoritative read state, WS compatibility, versioned chat contract, reliable events, read receipts, Telegram/notification surfaces, no direct panel-level toasts.
- **Current main evidence:** `backend/app/api/v1/endpoints/notifications.py`, `backend/app/services/notification_platform_service.py`, `frontend/src/contexts/NotificationCenterContext.jsx`, `frontend/src/contexts/NotificationWebSocketContext.jsx`, `backend/app/core/messaging_contract.py`, `backend/app/ws/chat_ws.py`, `backend/app/api/v1/endpoints/messages.py`.
- **What is real now:** the inbox platform, websocket normalization, and chat contract are present in current main.
- **What is partial:** historical messaging QA docs and audit logs are evidence-only, not live SSOT.
- **Stale docs:** `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md`, `docs/runbooks/MESSAGING_CONTRACT.md`, `docs/runbooks/MESSAGING_QA_CHECKLIST.md`.
- **Do not continue:** the old sender-service / Celery architecture and any claim that the historical messaging QA log is current truth.

## 3. Queue

- **Docs promised / claimed:** realtime QR queue, live display board, specialist-based queue SSOT, and legacy OnlineDay deprecation.
- **Current main evidence:** `backend/app/models/online_queue.py`, `backend/app/services/queue_service.py`, `backend/app/api/v1/api.py`, `docs/QUEUE_SYSTEM_ARCHITECTURE.md`, `docs/ONLINE_QUEUE_SYSTEM_V2.md`.
- **What is real now:** the current SSOT queue model and realtime wiring are implemented.
- **What is partial:** the old migration/fix-plan docs remain useful only as historical context.
- **Stale docs:** `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`, `docs/QUEUE_ARCHITECTURE_FIX_PLAN.md`, `docs/QUEUE_MIGRATION_REPORT.md`, `docs/QUEUE_SYSTEM_FIXES.md`, `docs/QUEUE_SYSTEM_IMPROVEMENTS.md`, plus the archive bundle.
- **Do not continue:** any workflow that treats `OnlineDay` or the archived queue plans as current implementation guidance.

## 4. Panel QA / Acceptance

- **Docs promised / claimed:** resumable panel QA checklist, role-by-role smoke, canonical local acceptance contour, and release evidence.
- **Current main evidence:** `docs/PANEL_QA_CHECKLIST.md`, `.ai-factory/PLAN.md`, `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`.
- **What is real now:** the runbook and evidence trail exist, and the role flows are reflected in current code and acceptance docs.
- **What is partial:** the execution discipline is manual and doc-driven, not a runtime QA orchestrator.
- **Stale docs:** old panel/improvement plans inside `docs/archives/*`.
- **Do not continue:** treating the historical QA log as a live execution state machine.

## 5. CI / Recovery / Security

- **Docs promised / claimed:** strict merge gates, backend/frontend tests, parity checks, RBAC checks, bandit/safety/pip-audit, load testing, observability, and recovery evidence.
- **Current main evidence:** `docs/CI_GUARDRAILS.md`, `.github/workflows/ci-cd-unified.yml`, `.github/workflows/security-scan.yml`, `.github/workflows/load-testing.yml`, `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md`, `docs/PRODUCTION_SECURITY.md`.
- **What is real now:** the CI guardrail and security scan workflows are present, and load/observability runbooks exist.
- **What is partial:** load/capacity enforcement and observability loops are documented, but the audit did not find a single proof chain for every budget/alert path.
- **Stale docs:** historical recovery logs and plan snapshots.
- **Do not continue:** treating the recovery logs as product truth or assuming the load/SLA story is fully closed without separate validation.

## 6. Other / Architecture / Ops

- **Docs promised / claimed:** modular monolith boundaries, Postgres/Alembic SSOT, and a VPS staging promotion path.
- **Current main evidence:** `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`, `.ai-factory/ROADMAP.md`, `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md`, `docs/PRODUCTION_SECURITY.md`.
- **What is real now:** the architecture and data-source rules are consistent in current main.
- **What is partial:** the VPS promotion path is documented but not proven as completed.
- **Stale docs:** none of the core architecture docs are stale, but older deployment notes should remain evidence only.
- **Do not continue:** rewriting current architecture docs to reintroduce SQLite-first or legacy deployment assumptions.

