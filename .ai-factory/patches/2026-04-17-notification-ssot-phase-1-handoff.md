# Handoff: Notification SSOT Phase 1 Alias / Type Normalization

Date: 2026-04-17
Source artifacts:
- `.ai-factory/dossiers/notification-system-audit-2026-04-17.md`
- `.ai-factory/plans/notification-ssot-hardening-2026-04-17.md`

## 1) Task brief

Normalize notification event types and aliases at the canonical contract boundary.

Phase 1 only:
- unify `diagnostics_return` -> `diagnostics_return_needed`
- fix the queue alias direction so `queue_update` remains canonical and `queue_changed` is legacy-only
- keep `all_free_approved` / `all_free_rejected` aligned with the canonical catalog

## 2) Scope boundaries

In scope:
- backend notification platform alias/type normalization
- frontend notification alias/type normalization
- catalog and slice1 tests needed to keep backend/frontend SSOT aligned

Out of scope:
- new producer wiring
- preference enforcement / quiet hours / anti-noise policy
- mobile legacy convergence
- broad docs rewrite
- webhook, bot, or unrelated notification business logic changes
- deep-link policy redesign unless it falls out of the same one-file normalization pass

## 3) Canonical anchors

- `.ai-factory/IMPLEMENTATION_NOTIFICATION_CATALOG_SSOT.md`
- `backend/app/services/notification_platform_service.py`
- `backend/app/services/notifications.py`
- `frontend/src/contexts/NotificationCenterContext.jsx`
- `frontend/src/contexts/NotificationWebSocketContext.jsx`
- `backend/tests/unit/test_notification_platform_contract.py`
- `backend/tests/unit/test_messages_notification_catalog_slice1.py`
- `backend/tests/integration/test_notification_catalog_slice1.py`

## 4) Allowed files to touch first

Start only with the smallest set that fixes alias/type drift:

- `.ai-factory/IMPLEMENTATION_NOTIFICATION_CATALOG_SSOT.md`
- `backend/app/services/notification_platform_service.py`
- `backend/app/services/notifications.py`
- `frontend/src/contexts/NotificationCenterContext.jsx`
- `frontend/src/contexts/NotificationWebSocketContext.jsx`
- `backend/tests/unit/test_notification_platform_contract.py`
- `backend/tests/unit/test_messages_notification_catalog_slice1.py`
- `frontend/src/contexts/__tests__/NotificationCenterContext.test.jsx`
- `frontend/src/contexts/__tests__/NotificationWebSocketContext.test.jsx`

If a file outside this set becomes necessary, stop and report before widening scope.

## 5) Files to read but not edit first

- `AGENTS.md`
- `.ai-factory/dossiers/notification-system-audit-2026-04-17.md`
- `.ai-factory/plans/notification-ssot-hardening-2026-04-17.md`
- `backend/app/api/v1/endpoints/notifications.py`
- `backend/tests/integration/test_notification_catalog_slice1.py`

## 6) Verification commands / checks

Run the narrowest relevant checks first:

```powershell
cd C:\final
python -m pytest backend/tests/unit/test_notification_platform_contract.py -q
python -m pytest backend/tests/unit/test_messages_notification_catalog_slice1.py -q
python -m pytest backend/tests/integration/test_notification_catalog_slice1.py -q
cd C:\final\frontend
npm run test:run -- src/contexts/__tests__/NotificationCenterContext.test.jsx src/contexts/__tests__/NotificationWebSocketContext.test.jsx
```

If the first two backend tests fail, do not move on to frontend work until the alias direction is fixed.

## 7) Assumptions requiring approval

- Confirm `queue_update` is the canonical event type and `queue_changed` is legacy-only.
- Confirm any remaining `diagnostics_return` references should normalize to `diagnostics_return_needed` everywhere in the canonical path.
- Confirm `all_free_approved` / `all_free_rejected` remain canonical event names and do not need a routing-policy redesign in this slice.
- Confirm deep-link recipient policy stays out of slice 1 unless a single-file alias normalization requires a direct fix.

## 8) Stop conditions

Stop if:
- backend and frontend SSOT disagree on the canonical queue alias direction
- the first safe patch slice would spill into producer wiring or policy enforcement
- an old alias is still treated as canonical by a test or runtime path outside the first-touch files
- fixing the mismatch would require webhook, bot, or mobile changes

## 9) First patch slice

First change:
- make backend persistence/transport normalize to the canonical notification types defined in the SSOT
- keep frontend ingress normalization aligned to the same canonical types
- update the smallest set of tests that prove the alias/type direction

Start source:
- `backend/app/services/notification_platform_service.py`

Secondary files if needed:
- `backend/app/services/notifications.py`
- `frontend/src/contexts/NotificationCenterContext.jsx`
- `frontend/src/contexts/NotificationWebSocketContext.jsx`

Hold back:
- do not expand into producer wiring, preferences enforcement, or anti-noise controls

## 10) Ready-to-send execution prompt

```text
You are working in C:\final.
Task brief: normalize notification event aliases/types for Phase 1 of notification SSOT hardening.

Scope boundaries:
- in scope: backend notification platform alias/type normalization, frontend alias/type normalization, and the minimal tests needed to prove SSOT alignment
- out of scope: new producer wiring, preference enforcement, anti-noise policy, mobile legacy convergence, webhook/bot changes, and broad docs rewrites

Canonical anchors:
- .ai-factory/IMPLEMENTATION_NOTIFICATION_CATALOG_SSOT.md
- backend/app/services/notification_platform_service.py
- backend/app/services/notifications.py
- frontend/src/contexts/NotificationCenterContext.jsx
- frontend/src/contexts/NotificationWebSocketContext.jsx

First-touch files:
- backend/app/services/notification_platform_service.py
- backend/app/services/notifications.py
- frontend/src/contexts/NotificationCenterContext.jsx
- frontend/src/contexts/NotificationWebSocketContext.jsx
- backend/tests/unit/test_notification_platform_contract.py
- backend/tests/unit/test_messages_notification_catalog_slice1.py

Read but do not edit first:
- AGENTS.md
- .ai-factory/dossiers/notification-system-audit-2026-04-17.md
- .ai-factory/plans/notification-ssot-hardening-2026-04-17.md
- backend/app/api/v1/endpoints/notifications.py

Verification checks:
- python -m pytest backend/tests/unit/test_notification_platform_contract.py -q
- python -m pytest backend/tests/unit/test_messages_notification_catalog_slice1.py -q
- python -m pytest backend/tests/integration/test_notification_catalog_slice1.py -q
- npm run test:run -- src/contexts/__tests__/NotificationCenterContext.test.jsx src/contexts/__tests__/NotificationWebSocketContext.test.jsx

Assumptions requiring approval:
- queue_update is canonical and queue_changed is legacy-only
- diagnostics_return should normalize to diagnostics_return_needed
- all_free_approved and all_free_rejected stay canonical and do not trigger a policy redesign in this slice

Stop conditions:
- stop if backend and frontend disagree on the canonical alias direction
- stop if the smallest safe patch would spill into producer wiring or policy enforcement
- stop if a legacy alias is still treated as canonical outside the first-touch files

First patch slice:
- make backend persistence/transport normalize to the canonical notification types
- keep frontend ingress normalization aligned
- update the smallest set of tests that prove the alias/type direction

Do not broaden scope.
```
