# BFF-lite Decision Checkpoint

**Status:** Accepted checkpoint  
**Date:** 2026-05-24  
**Scope:** Registrar, QR QueueJoin, DisplayBoard  
**Base evidence:** `62a28de3` (`fix(registrar): prefer service department contract (#1228)`)

## Decision

Do not add BFF-lite endpoints now.

The current target architecture remains:

- React renders backend facts and submits backend-owned commands.
- Existing FastAPI endpoints are extended first when a screen needs a stronger read contract.
- `/api/v1/ui/*` screen/read-model endpoints are allowed later only after a fresh re-measure proves existing endpoints still leave fragile screen assembly.
- A separate BFF service is not justified.

## Current Evidence

RegistrarPanel:

- Initial load uses existing metadata endpoints: `/registrar/doctors`, `/registrar/services`, `/registrar/departments?active_only=true`, and `/registrar/queues/today`.
- Refresh, auto-refresh, and load-more delegate to `/registrar/queues/today`.
- Payment, cancel, status, and start-visit commands use `POST /registrar/records/actions`.
- Command availability is backend-owned through `available_actions` and `can_*`.
- Normal queue rows use backend patient display fields; `/patients/{id}` remains only for the explicit URL patient workflow or legacy missing-DTO fallback.
- Service filtering now prefers backend `service_details.department_key` / service `department_key`; local code-prefix rules are legacy fallback only.

QueueJoin:

- The active page uses `fetchQrTokenInfo`, `startQueueJoinSession`, and `completeQueueJoinSession`.
- Specialist selection is driven by backend `selectable_specialists`.
- Unavailable queue messaging is rendered from backend `status/message`; React does not recreate time, limit, or reception-open policy text.

DisplayBoard:

- `/board/state` is intentionally a stats/settings snapshot.
- Live rows, current calls, and announcements are owned by the display-board WebSocket `initial_state` / update stream.
- This is documented by frontend and backend contract tests.

## Verification Performed

Focused frontend contract run:

```powershell
npm --prefix frontend run test:run -- RegistrarPanel.contract registrarAggregation QueueJoin.accessibility DisplayBoardUnified.contract
```

Result at this checkpoint:

- 4 test files passed.
- 29 tests passed.

Repository search found no runtime `/api/v1/ui/*` implementation. Existing mentions are skills, rules, and negative contract assertions.

## Remaining Assembly Classification

Presentation-only:

- Registrar row adaptation for table rendering.
- Tab, search, status, and local form state.
- UI sorting by backend-provided `queue_time`.
- All-departments visual grouping in `registrarAggregation`.
- Display labels and empty/error UI.

Existing endpoint extension candidates:

- Registrar metadata could be bundled later if the four initial metadata calls become a measured performance or fragility problem.
- DisplayBoard `/board/state` could be expanded later only if WebSocket-only initial display state proves insufficient for refresh/offline recovery.

True BFF-lite candidates:

- None justified by current evidence.

Contract leaks in targeted active paths:

- None found in the measured Registrar, QueueJoin, or DisplayBoard paths.

## No-Go Rules

Do not add:

- `/api/v1/ui/*` just to align architecture.
- A separate BFF service.
- Generic command wrappers.
- Frontend-owned queue, payment, visit, role, or action decisions.
- Duplicate queue/payment/visit/audit business rules in read-model code.
- Broad RegistrarPanel rewrites under a BFF-lite label.

## Future BFF-lite Gate

Before adding any `/api/v1/ui/*` endpoint, perform a fresh screen-specific re-measure and prove all of the following:

1. SSOT/contract leaks for that screen are already repaired or explicitly out of scope.
2. Existing endpoint extension is insufficient or would make the existing endpoint unstable.
3. The proposed endpoint is read-only unless it delegates to an existing core command service.
4. Core rules remain in backend services, not the read-model endpoint.
5. Backend tests prove DTO shape, redaction, ordering, permissions, and action availability.
6. Frontend tests prove orchestration is simplified without moving business decisions into React.

Allowed future examples, only with fresh evidence:

- `GET /api/v1/ui/registrar/workbench`
- `GET /api/v1/ui/queue/board`

These endpoints must be screen DTOs, not second sources of truth.

## Next Step

Keep repairing concrete SSOT contract leaks as they are found. Do not plan or implement BFF-lite until a later re-measure contradicts this checkpoint.
