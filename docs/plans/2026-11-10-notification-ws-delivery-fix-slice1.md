# Notification WebSocket delivery — isolated fix slice 1 (implementation handoff)

**Date:** 2026-11-10. **Source pin:** `4f42f84f31266f7149cfb75d422adf2098e93425`. **Related audit:** [Draft PR #3961](https://github.com/drsapaev/final/pull/3961), finding **NOTIFYEVENT-FE-001** (round 36).

**STATUS: PLANNED — NOT FIXED.** This separate Draft PR currently contains **only this planning document**, not application code or tests. No claims of behavioral remediation, gate success, Vitest pass, CI pass or deployment are made. Complete the mandatory repo gate in a real Windows checkout before the first runtime edit; if gate cannot run, **stop implementation**.

## Selection and exact defect

- **Owner:** [`backend/app/services/notification_platform/_rest.py` L16–56](https://github.com/drsapaev/final/blob/4f42f84f31266f7149cfb75d422adf2098e93425/backend/app/services/notification_platform/_rest.py#L16-L56) provides authoritative transport envelopes. Most domain event types (e.g. `lab_results`, `new_appointment`, `message_received`) are broadcast as **top-level** `type: 'notification'` with `event_type` and a nested `notification` delivery record.
- **React consumer:** [`frontend/src/contexts/NotificationWebSocketContext.tsx` L85–109](https://github.com/drsapaev/final/blob/4f42f84f31266f7149cfb75d422adf2098e93425/frontend/src/contexts/NotificationWebSocketContext.tsx#L85-L109) prefers nested domain `event_type` when creating `normalized.type`; [L229–279](https://github.com/drsapaev/final/blob/4f42f84f31266f7149cfb75d422adf2098e93425/frontend/src/contexts/NotificationWebSocketContext.tsx#L229-L279) only enters its append/cache/toast branch for `notification`, `queue_update`, `diagnostics_return_needed`, `system_alert`. A legitimate `lab_results` notification does **not** enter that branch.
- **Existing test:** [`frontend/src/contexts/__tests__/NotificationWebSocketContext.test.tsx` L207–269](https://github.com/drsapaev/final/blob/4f42f84f31266f7149cfb75d422adf2098e93425/frontend/src/contexts/__tests__/NotificationWebSocketContext.test.tsx#L207-L269) tests only the alias cases `queue_changed` and `diagnostics_return`; it does not cover arbitrary backend domain events.
- **Scope:** Restore delivery of validated `type:'notification'` envelopes regardless of domain `event_type`, without making frontend a business-logic authority. Backend remains the SSOT for event taxonomy, recipient, role and delivery ID. Do **not** change server event schemas to compensate for consumer filtering.

## Mandatory gate and explicit scope before runtime edits

**Project instruction:** [`AGENTS.md`](https://github.com/drsapaev/final/blob/4f42f84f31266f7149cfb75d422adf2098e93425/AGENTS.md) requires a mandatory gate for frontend/backend contract work, and [`.agents/skills/final-ssot-contract-repair/SKILL.md`](https://github.com/drsapaev/final/blob/4f42f84f31266f7149cfb75d422adf2098e93425/.agents/skills/final-ssot-contract-repair/SKILL.md) requires backend SSOT and bounded regression. Selected prospective mode: **`gate_known_root_cause`** because the frontend root cause and its source file are source-pinned. **The gate has NOT been run** here: no accessible project checkout, PowerShell executable or test runtime; GitHub connector reads/writes files but does not execute the mandatory launcher.

On a real project checkout, from `ai/langgraph`, use the project's documented launcher, with exact scope and root cause:

```powershell
.\scripts\run_agent_gate.ps1 --known-root-cause frontend/src/contexts/NotificationWebSocketContext.tsx --scope frontend/src/contexts/NotificationWebSocketContext.tsx --scope frontend/src/contexts/__tests__/NotificationWebSocketContext.test.tsx
```

Read the **actual returned execution prompt**, and obey its first-touch/stop conditions before editing. If the gate fails, stop; if it misroutes, follow the repository's one-time retry and approved-override policy, not a bypass.

**Prospective allowed runtime files (only after gate passes):**
1. `frontend/src/contexts/NotificationWebSocketContext.tsx`
2. `frontend/src/contexts/__tests__/NotificationWebSocketContext.test.tsx`

**Reference-only:** `backend/app/services/notification_platform/_rest.py`, `frontend/src/contexts/NotificationCenterContext.tsx`, `frontend/src/utils/ws-schemas.ts`, notification schema and tests. **Denied:** backend auth, queue/board managers, database/Alembic, Redis config, environment/secrets, production, migrations, unrelated frontend modules, `main` merge, deployment.

## Fail-first synthetic regression contract

Extend the existing mocked `MockWebSocket` provider suite, using **synthetic delivery IDs only** and no PHI:

1. **Ordinary notification:** deliver `{type:'notification', event_type:'lab_results', delivery_id:'syn-lab-1', notification:{delivery_id:'syn-lab-1', event_type:'lab_results', title:'Synthetic result', message:'Synthetic message'}}`. Assert one `appendNotification`, one notification cache invalidation, one toast, stable delivery ID and `type='lab_results'` presented to the notification center.
2. **Representative taxonomy:** repeat for `new_appointment`, `message_received` and `security_alert`, preserving each domain event type. Backend's transport category, not an allowlist of domain types, authorizes processing.
3. **Backwards compatibility:** preserve passing `queue_changed → queue_update` and `diagnostics_return → diagnostics_return_needed` fixtures. Ensure top-level `queue_update` and `system_alert` transports still process correctly.
4. **Not a notification:** `connection_established`, `notification_read_ack`, `notification_sync_response`, `ping`/malformed frame must not create a new inbox row/toast. Existing actor/user privacy and audit behavior must remain unchanged.
5. **Dedup:** repeat the same synthetic `delivery_id` frame and assert no second persisted inbox entry. Whether a duplicate toast occurs is an existing adjacent concern; record separately rather than widening this slice without evidence.

## Minimal proposed repair (NOT IMPLEMENTED)

Preserve `normalizePayload` as the domain-event normalizer. Inside `handleMessageRef.current`, derive a **separate transport discriminator** from the validated **top-level** `data.type`. Then route a canonical `transportType === 'notification'` through the existing append/cache/notify branch **regardless of the normalized nested `event_type`**. Retain existing direct `queue_update`, `diagnostics_return_needed`, `system_alert` behavior and early returns for connection/sync/ack frames.

Do not introduce a list of permitted domain event names (`lab_results`, `new_appointment`, etc.) in the frontend. The backend source of truth may add new domain event types; the consumer should still accept the canonical notification transport envelope. Retain the original `normalized.type` value for role-specific rendering, rather than replacing it with the generic string `notification`.

**Code review caution:** A naive `if (normalized.type === 'notification' || data.type === 'notification')` must still follow the explicit handshake/ack early-return blocks and preserve the canonical parsed-message validation. Verify that nested payloads cannot override server-owned `recipient_id` or cause cross-user notification routing.

## Verification and stop criteria

**Red first:** Before the change, the new synthetic lab-results test should fail due to **zero** append calls, not because the socket mock, token, or route failed. Then run the smallest patch and watch the same test turn green.

```bash
cd frontend
npm run test:run -- src/contexts/__tests__/NotificationWebSocketContext.test.tsx
npm run type-check
npx eslint src/contexts/NotificationWebSocketContext.tsx src/contexts/__tests__/NotificationWebSocketContext.test.tsx
```

Check `git diff --check`, branch diff against fresh `origin/main`, PR template headings, review and CI. The browser WebSocket smoke and staging role-level validation remain needed before any production claim. **None of these commands has been executed by this planning PR.** Stop if backend event shape, canonical vs legacy ownership or test fixture differs from the pinned source, or if the mandatory gate cannot be completed.

## Follow-on PRs — do not combine with this slice

Keep separate: **NOTIFYAUTH-BE-001** (JWT all-user revocation), **NOTIFYSESSION-BE-001** (exceptional WS teardown), **NOTIFYSYNC-BE-001** (pagination cap), **NOTIFYREPLAY-FE-001** (post-reconnect resync), **NOTIFYDELIVERY-BE-001** (dead-socket pruning). Each requires its own dependency/test scope and gate as applicable.

## Status / rollback

- **Done:** confirmed canonical transport-vs-event contract; exact owner and test paths; bounded repair and fail-first specification; a dedicated separate Draft PR branch from `main`.
- **Not done:** mandatory gate, source code patch, tests, CI, smoke, deployment.
- **Rollback:** close this plan-only Draft PR or revert this Markdown commit; currently no runtime behavior changed.
