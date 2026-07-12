# ADR-0005: Unified WebSocket Manager

**Status:** ⚠️ Partially Implemented (2026-07-13) — auth + reconnect + heartbeat done, unified WSManager NOT done
**Date:** 2026-07-04
**Updated:** 2026-07-13
**Owner:** Frontend Platform
**Related:** `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-3, ADR-0004

## Update (2026-07-13)

ADR-0004 (queue WS enablement) is now ✅ Implemented (see ADR-0004 status).
However, this ADR (unified WSManager) is only **partially done**:

- ✅ **Auth** — all WS connections now use `Sec-WebSocket-Protocol: bearer.<token>` subprotocol via `websocketAuth.js` (PR-36)
- ✅ **Reconnect + heartbeat** — `useQueueWebSocket` hook implements exponential backoff + ping/pong
- ❌ **Unified WSManager** — `frontend/src/core/ws/WSManager.js` was NOT created. The number of WS systems has **increased** from 3 to 7 (see updated inventory below).

### Current WS Systems (7, was 3)

The frontend audit (PR-35 → PR-44) added new WS hooks without consolidating them. Updated inventory:

1. `openQueueWS` (`api/ws.js:15`) — **dead code** (disabled, never called). Candidate for removal.
2. `openDisplayBoardWS` (`api/ws.js:51`) — active. Display board WS with reconnect.
3. `NotificationWebSocketContext` (`contexts/`) — active. Notification WS.
4. `useQueueWebSocket` (new, `hooks/`) — active. Queue WS with exponential backoff + JWT subprotocol. ✅ Implements ADR-0004.
5. `useAIChat` (new, `hooks/`) — active. AI chat WS.
6. `useApi` (`hooks/useApi.js:253`) — active. Generic WS hook.
7. `ChatContext` (`contexts/ChatContext.jsx:357`) — active. Chat WS.

### What remains to be done

The unified `WSManager` class is still needed to:
1. Centralize connection lifecycle (connect/disconnect/reconnect) for all 7 systems
2. Provide a single `useWebSocket(channel, options)` hook that all consumers use
3. Enforce consistent auth (subprotocol), heartbeat, and backoff across all connections
4. Track connection state globally (for debugging + observability)

**Estimated effort:** 2-3 PRs. The migration is mechanical (replace each hook's internal `new WebSocket(...)` with `wsManager.connect(channel, options)`), but requires testing each consumer.

## Context

The frontend currently has **three independent WebSocket systems** with different APIs, different reconnect strategies, and different authentication patterns:

### 1. `openQueueWS` — `frontend/src/api/ws.js:15`
- **URL**: `/ws/queue?department=&date_str=`
- **Auth**: none (no token)
- **Reconnect**: none (`ws.onclose = () => {}`)
- **Heartbeat**: none
- **Status**: disabled by default (`VITE_ENABLE_WS=0`), never called by any code
- **ADR-0004** proposes to enable + add reconnect + auth + heartbeat

### 2. `openDisplayBoardWS` — `frontend/src/api/ws.js:51`
- **URL**: `/api/v1/display/ws/board/{board_id}?token=...`
- **Auth**: JWT in query param
- **Reconnect**: 5 attempts × 3s, then dies (no infinite retry)
- **Heartbeat**: ping every 30s
- **Status**: active, used by `DisplayBoardUnified.jsx`
- **Known issue**: after 5 failed reconnects, the display board goes stale silently until manual page reload

### 3. `NotificationWebSocketContext` — `frontend/src/contexts/NotificationWebSocketContext.jsx`
- **URL**: `/api/v1/ws/notifications/connect?token=...`
- **Auth**: JWT in query param
- **Reconnect**: infinite 3s retry (via `scheduleReconnect()`)
- **Heartbeat**: implicit (relies on server-side keepalive)
- **Status**: active, wraps the entire authenticated app
- **Known issue**: reconnect delay is fixed 3s — no backoff, so a long backend outage generates 1 request every 3s per client indefinitely

### The Problem

Three separate implementations means:

1. **Duplicated logic** — each system re-implements URL building, token handling, reconnect, and message parsing. ~150 lines of near-identical code across 3 files.
2. **Inconsistent resilience** — queue WS gives up instantly, display board gives up after 5 tries, notifications retry forever. No principled reason for the difference.
3. **No shared backoff** — when the backend recovers from an outage, all 3 systems reconnect simultaneously (thundering herd). With N doctors, that is 3N concurrent WS connections hitting the backend at the same moment.
4. **No shared connection state** — if the network drops, each system independently detects the failure and reconnects. The user sees 3 separate "reconnecting..." indicators (if any).
5. **Testing burden** — each system must be tested separately for reconnect, auth, and message handling. No shared test fixtures.

## Decision

**Create a single `WSManager` class that all three WebSocket use cases build on.**

### Principles

1. **One class, many channels** — `WSManager` manages a single WS connection to a given URL. Callers subscribe to channels/topics via `ws.subscribe(topic, handler)`.
2. **Configurable retry policy** — each `WSManager` instance accepts a `RetryPolicy` object: `{ strategy: 'fixed' | 'exponential', base: 1000, cap: 30000, maxAttempts: number | Infinity, jitter: 0.2 }`.
3. **Shared heartbeat** — `WSManager` sends `{type: 'ping'}` every 30s; if no pong within 10s, force reconnect. Configurable via `heartbeatIntervalMs`.
4. **Connection state observable** — `ws.onStateChange(callback)` emits `'connecting' | 'open' | 'closing' | 'closed' | 'reconnecting'`. UI can show a single "Connection lost, reconnecting..." indicator.
5. **Auth via query param OR subprotocol** — `WSManager` accepts `auth: { type: 'query', key: 'token', value: () => tokenManager.getAccessToken() }` or `auth: { type: 'subprotocol', value: () => ... }`. Phase 1 uses query param (matches existing pattern); Phase 2 can migrate to subprotocol for log safety.
6. **Backpressure** — if the message queue exceeds 100 unprocessed messages, drop the oldest (configurable). Prevents memory blowup if the handler is slow.

### Proposed API

```typescript
// frontend/src/core/ws/WSManager.js

class WSManager {
  constructor(options: {
    url: string | (() => string),
    auth?: { type: 'query' | 'subprotocol', key?: string, value: () => string },
    retry?: { strategy: 'fixed' | 'exponential', base?: number, cap?: number, maxAttempts?: number, jitter?: number },
    heartbeat?: { intervalMs?: number, timeoutMs?: number },
    backpressure?: { maxQueueSize?: number },
  });

  connect(): void;
  disconnect(code?: number, reason?: string): void;
  subscribe(topic: string, handler: (message: any) => void): () => void;  // returns unsubscribe
  send(message: object): void;
  onStateChange(handler: (state: WSState) => void): () => void;
  getState(): WSState;
}
```

### Migration Plan (4 phases, each a separate PR)

#### Phase 1: Create `WSManager` class + unit tests (No production change)
- New file `frontend/src/core/ws/WSManager.js`.
- New file `frontend/src/core/ws/__tests__/WSManager.test.js` — unit tests with a mock WebSocket.
- Tests cover: connect, disconnect, reconnect with fixed backoff, reconnect with exponential backoff, heartbeat, auth via query param, subscribe/unsubscribe, backpressure drop, state transitions.
- **No existing code changes** — `openQueueWS`, `openDisplayBoardWS`, `NotificationWebSocketContext` continue to work as-is.
- **Estimated diff**: ~300 lines new code (class + tests).
- **Testing**: Unit tests pass.

#### Phase 2: Migrate `openDisplayBoardWS` to `WSManager` (Low risk)
- Rewrite `openDisplayBoardWS` as a thin wrapper around `WSManager`:
  ```javascript
  export function openDisplayBoardWS(boardId, onMessage, onConnect, onDisconnect) {
    const ws = new WSManager({
      url: () => buildWsUrl(`/api/v1/display/ws/board/${boardId}`),
      auth: { type: 'query', key: 'token', value: () => tokenManager.getAccessToken() },
      retry: { strategy: 'exponential', base: 1000, cap: 30000, maxAttempts: Infinity, jitter: 0.2 },
      heartbeat: { intervalMs: 30000, timeoutMs: 10000 },
    });
    ws.subscribe('board_update', onMessage);
    ws.onStateChange((state) => {
      if (state === 'open') onConnect && onConnect();
      if (state === 'closed' || state === 'reconnecting') onDisconnect && onDisconnect();
    });
    ws.connect();
    return () => ws.disconnect(1000, 'bye');
  }
  ```
- **Benefit over current**: infinite reconnect (was: 5 attempts then die). Exponential backoff (was: fixed 3s).
- **Estimated diff**: ~80 lines deleted, ~30 lines added.
- **Testing**: Existing `DisplayBoardUnified.contract.test.jsx` passes; manual test — kill backend, verify reconnect.

#### Phase 3: Migrate `NotificationWebSocketContext` to `WSManager` (Medium risk)
- Replace the bespoke WS logic in `NotificationWebSocketContext.jsx` with `WSManager`.
- The context still owns the message-routing logic (notification_seen_ack, queue_update, etc.) — it just delegates transport to `WSManager`.
- **Benefit over current**: exponential backoff (was: fixed 3s, no jitter → thundering herd).
- **Estimated diff**: ~100 lines deleted, ~40 lines added.
- **Testing**: Existing `NotificationCenterContext.test.jsx` passes; manual test — verify notifications still arrive, unread count converges after reconnect.

#### Phase 4: Migrate `openQueueWS` to `WSManager` + enable (Medium risk, depends on ADR-0004)
- Rewrite `openQueueWS` as a `WSManager` wrapper (same pattern as Phase 2).
- Set `VITE_ENABLE_WS=1` in production env.
- Wire into `useDoctorQueue` per ADR-0004 Phase 3.
- **Benefit**: unifies the third system; all WS now goes through `WSManager`.
- **Estimated diff**: ~50 lines in `ws.js`, ~50 lines in `useDoctorQueue.js`, ~2 lines in env files.
- **Testing**: ADR-0004 acceptance criteria.

### Acceptance Criteria

- [ ] `frontend/src/core/ws/WSManager.js` exists with the proposed API
- [ ] `WSManager.test.js` covers: connect, disconnect, fixed backoff, exponential backoff, heartbeat timeout, auth query param, subscribe/unsubscribe, backpressure, state transitions
- [ ] `openDisplayBoardWS` uses `WSManager` internally (Phase 2)
- [ ] `NotificationWebSocketContext` uses `WSManager` internally (Phase 3)
- [ ] `openQueueWS` uses `WSManager` internally (Phase 4)
- [ ] No file outside `core/ws/` directly constructs `new WebSocket(...)` — CI lint rule
- [ ] Manual test: kill backend, all 3 systems reconnect with exponential backoff, no thundering herd
- [ ] Manual test: display board no longer goes stale after 5 failed reconnects (was: silent death)

## Consequences

**Плюсы:**
- Single source of truth for WS transport — reconnect, heartbeat, auth, backpressure all in one place
- Consistent resilience across all 3 use cases — exponential backoff + infinite retry everywhere
- Shared backoff prevents thundering herd on backend recovery
- Single connection-state observable — UI can show one "reconnecting..." indicator instead of 3
- ~150 lines of duplicated logic deleted
- Easier to add new WS use cases — just `new WSManager({ url, ... })` + `subscribe`

**Минусы:**
- 4-phase migration requires coordination — each phase is a separate PR
- Phase 3 (NotificationWebSocketContext) is medium risk — notification delivery is critical, regressions could cause missed alerts
- `WSManager` is a new abstraction that developers must learn — onboarding cost
- If `WSManager` has a bug, it affects all 3 systems simultaneously (but also: bug fix in one place fixes all 3)

## Alternatives Considered

### A. Keep 3 separate implementations, just fix the known issues in each
- **Rejected**: This is the status quo. The duplication makes every fix 3× more expensive, and the inconsistency (5-attempt cap vs infinite retry vs no reconnect) has no principled basis.

### B. Use a third-party library (e.g. `reconnecting-websocket`, `socket.io-client`)
- **Rejected**: `reconnecting-websocket` is a thin wrapper that does not support heartbeat or backpressure. `socket.io-client` is a full framework with its own protocol — backend would need socket.io server, which is a larger change. The custom `WSManager` is ~150 lines and gives us full control.

### C. Wait for ADR-0004 (queue WS enablement) before starting this ADR
- **Partially accepted**: Phase 4 of this ADR depends on ADR-0004 Phase 3. But Phases 1-3 are independent and can proceed first. In fact, doing Phase 1-3 first makes ADR-0004 Phase 3 easier (just use `WSManager` instead of bespoke `openQueueWS`).

## Follow-up

- After Phase 4 is merged, add a CI lint rule that forbids `new WebSocket(...)` outside `core/ws/WSManager.js`.
- Consider extracting `RetryPolicy` into a shared `core/util/RetryPolicy.js` so it can be reused for HTTP retry (e.g. 503 backoff).
- Consider adding a `WSManager.getStats()` method returning `{ reconnectCount, messagesReceived, messagesDropped, uptimeMs }` for observability.
- Phase 5 (future): migrate JWT from query param to `Sec-WebSocket-Protocol` header for log safety — requires backend coordination.

## References

- `frontend/src/api/ws.js` — current `openQueueWS` + `openDisplayBoardWS`
- `frontend/src/contexts/NotificationWebSocketContext.jsx` — current notification WS
- `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-3 — original problem statement
- `docs/architecture/ADR-0004-queue-websocket-enablement.md` — depends on this ADR's Phase 4
- `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md` — notification architecture context
