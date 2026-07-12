# ADR-0005: Unified WebSocket Manager

**Status:** Proposed (updated 2026-07-13)
**Date:** 2026-07-04
**Owner:** Frontend Platform
**Related:** `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-3, ADR-0004 (Implemented)

## Context

> **Update 2026-07-13:** This ADR originally identified 3 WebSocket
> systems. A re-audit found **7 active WS construction sites** (plus
> 1 dead). The problem is now larger and more urgent than originally
> documented. The Decision and Principles below are unchanged; the
> inventory and migration phases have been updated.

The frontend currently has **seven active WebSocket construction sites**
(`new WebSocket(...)`) plus one dead function, with inconsistent auth
patterns, reconnect strategies, and heartbeat implementations:

### WS Inventory (as of 2026-07-13)

| # | File | Auth method | Reconnect | Heartbeat | Status |
|---|------|-------------|-----------|-----------|--------|
| 1 | `contexts/NotificationWebSocketContext.jsx:214` | ✅ subprotocol `bearer.<token>` | infinite 3s retry | implicit | Active — wraps entire app |
| 2 | `api/ws.js:70` (`openDisplayBoardWS`) | ✅ subprotocol | 5 attempts × 3s, then dies | ping 30s | Active — DisplayBoard |
| 3 | `utils/websocketAuth.js:49` (`createAuthenticatedWebSocket`) | ✅ subprotocol | configurable | configurable | Active — utility, callers unknown |
| 4 | `hooks/useQueueWebSocket.js:90` | ❌ **token in URL query** | exponential 3→30s, 5 attempts | none | Active — ModernQueueManager |
| 5 | `hooks/useAIChat.js:273` | ❌ **token in URL query** | none | none | Active — AI chat |
| 6 | `hooks/useApi.js:253` | ❌ **token in URL query** | none | none | Active — generic WS hook |
| 7 | `contexts/ChatContext.jsx:357` | ❌ **NO AUTH at all** | none | none | Active — chat |
| 8 | `api/ws.js:15` (`openQueueWS`) | none | none | none | **Dead code** — 0 callers |

### Security Finding (NEW — 2026-07-13)

**4 of 7 active WS sites leak JWT in URL query string** (`?token=...`),
which is the exact issue that frontend audit PR-36 / P0-3 was supposed to
fix. PR-36 fixed `NotificationWebSocketContext` and created
`websocketAuth.js` with the subprotocol pattern, but **4 other WS sites
were not migrated**:

- `useQueueWebSocket.js:85` — `?token=${encodeURIComponent(token)}`
- `useAIChat.js:270` — `?token=${token}`
- `useApi.js:251` — `?token=${encodeURIComponent(token)}`
- `ChatContext.jsx:357` — no auth at all (separate issue)

This is a **P0 security regression** — the JWT appears in nginx access
logs, browser history, and Referer headers for these 4 endpoints.

### The Problem

Seven separate implementations means:

1. **Duplicated logic** — each system re-implements URL building, token handling, reconnect, and message parsing. ~300 lines of near-identical code across 7 files.
2. **Inconsistent auth** — 3 sites use subprotocol (secure), 4 sites use URL query (insecure). No principled reason for the difference.
3. **Inconsistent resilience** — queue WS has exponential backoff, display board gives up after 5 tries, notifications retry forever, AI chat / ChatContext / useApi have no reconnect at all.
4. **No shared backoff** — when the backend recovers from an outage, all 7 systems reconnect independently (thundering herd). With N doctors, that is up to 7N concurrent WS connections.
5. **No shared connection state** — the user sees different "reconnecting..." indicators (or none) depending on which WS dropped.
6. **Testing burden** — each system must be tested separately. No shared test fixtures.
7. **Security debt** — 4 sites leak JWT in URL. A unified `WSManager` with subprotocol auth would fix all 4 in one migration.

## Decision

**Create a single `WSManager` class that all WebSocket use cases build on.**

### Principles

1. **One class, many channels** — `WSManager` manages a single WS connection to a given URL. Callers subscribe to channels/topics via `ws.subscribe(topic, handler)`.
2. **Configurable retry policy** — each `WSManager` instance accepts a `RetryPolicy` object: `{ strategy: 'fixed' | 'exponential', base: 1000, cap: 30000, maxAttempts: number | Infinity, jitter: 0.2 }`.
3. **Shared heartbeat** — `WSManager` sends `{type: 'ping'}` every 30s; if no pong within 10s, force reconnect. Configurable via `heartbeatIntervalMs`.
4. **Connection state observable** — `ws.onStateChange(callback)` emits `'connecting' | 'open' | 'closing' | 'closed' | 'reconnecting'`. UI can show a single "Connection lost, reconnecting..." indicator.
5. **Auth via subprotocol (default) OR query param** — `WSManager` accepts `auth: { type: 'subprotocol', value: () => tokenManager.getAccessToken() }` (default, secure — token not in URL/logs) or `auth: { type: 'query', key: 'token', value: () => ... }` (legacy, insecure — only for backend endpoints that don't support subprotocol yet). The 4 sites currently leaking JWT in URL query (useQueueWebSocket, useAIChat, useApi, ChatContext) will be migrated to subprotocol.
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

### Migration Plan (6 phases, each a separate PR)

> **Updated 2026-07-13:** Original plan had 4 phases for 3 WS sites.
> Now 7 active sites need migration. Phases 2-4 below are new (for the
> 4 insecure-auth sites). Phases 5-7 correspond to the original Phases 2-4.

#### Phase 0: Delete dead `openQueueWS` (Trivial, no risk)
- `frontend/src/api/ws.js:15-45` — `openQueueWS` has 0 callers.
- Delete the function. Keep `openDisplayBoardWS` and `wsEnabled()`.
- **Estimated diff**: -30 lines.

#### Phase 1: Create `WSManager` class + unit tests (No production change)
- New file `frontend/src/core/ws/WSManager.js`.
- New file `frontend/src/core/ws/__tests__/WSManager.test.js` — unit tests with a mock WebSocket.
- Tests cover: connect, disconnect, reconnect with fixed backoff, reconnect with exponential backoff, heartbeat, auth via subprotocol, auth via query param, subscribe/unsubscribe, backpressure drop, state transitions.
- **No existing code changes** — all 7 sites continue to work as-is.
- **Estimated diff**: ~300 lines new code (class + tests).
- **Testing**: Unit tests pass.

#### Phase 2: Migrate `useQueueWebSocket` to `WSManager` (Medium risk — security fix)
- **Priority: HIGH** — this site leaks JWT in URL query (`?token=...`).
- Rewrite `useQueueWebSocket.js` to use `WSManager` with `auth: { type: 'subprotocol' }`.
- Preserve the existing exponential backoff (3→6→12→24→30s, 5 attempts).
- **Benefit**: JWT no longer in URL query. Shared heartbeat. Shared state observable.
- **Estimated diff**: ~60 lines deleted, ~30 lines added.
- **Testing**: Manual — verify queue updates still arrive, verify JWT not in Network tab URL.

#### Phase 3: Migrate `useAIChat` to `WSManager` (Medium risk — security fix)
- **Priority: HIGH** — this site leaks JWT in URL query.
- Rewrite `useAIChat.js:273` to use `WSManager` with `auth: { type: 'subprotocol' }`.
- Add reconnect logic (currently none — AI chat dies silently on disconnect).
- **Benefit**: JWT no longer in URL. Reconnect on disconnect.
- **Estimated diff**: ~40 lines deleted, ~30 lines added.

#### Phase 4: Migrate `useApi` WS + `ChatContext` to `WSManager` (Medium risk — security fix)
- **Priority: HIGH** — `useApi` leaks JWT in URL query; `ChatContext` has no auth at all.
- Rewrite both to use `WSManager` with `auth: { type: 'subprotocol' }`.
- `ChatContext` needs auth added (currently `new WebSocket(wsUrl)` with no token — this is a separate bug).
- **Benefit**: JWT no longer in URL. Chat gets auth. Both get reconnect.
- **Estimated diff**: ~80 lines deleted, ~50 lines added.

#### Phase 5: Migrate `openDisplayBoardWS` to `WSManager` (Low risk)
- Rewrite `openDisplayBoardWS` as a thin wrapper around `WSManager`.
- Already uses subprotocol — keep it.
- **Benefit**: infinite reconnect (was: 5 attempts then die). Shared backoff.
- **Estimated diff**: ~80 lines deleted, ~30 lines added.

#### Phase 6: Migrate `NotificationWebSocketContext` to `WSManager` (Medium risk)
- Replace the bespoke WS logic in `NotificationWebSocketContext.jsx` with `WSManager`.
- The context still owns the message-routing logic — it just delegates transport to `WSManager`.
- Already uses subprotocol — keep it.
- **Benefit**: exponential backoff (was: fixed 3s, no jitter → thundering herd).
- **Estimated diff**: ~100 lines deleted, ~40 lines added.

#### Phase 7: Delete `websocketAuth.js` utility (Trivial, after Phase 5-6)
- `createAuthenticatedWebSocket` in `utils/websocketAuth.js` is superseded by `WSManager`.
- Check for remaining callers; if none, delete.
- **Estimated diff**: -200 lines.

### Acceptance Criteria

- [ ] `frontend/src/core/ws/WSManager.js` exists with the proposed API
- [ ] `WSManager.test.js` covers: connect, disconnect, fixed backoff, exponential backoff, heartbeat timeout, auth subprotocol, auth query param, subscribe/unsubscribe, backpressure, state transitions
- [ ] Dead `openQueueWS` deleted (Phase 0)
- [ ] `useQueueWebSocket` uses `WSManager` with subprotocol auth (Phase 2)
- [ ] `useAIChat` uses `WSManager` with subprotocol auth (Phase 3)
- [ ] `useApi` WS + `ChatContext` use `WSManager` with subprotocol auth (Phase 4)
- [ ] `openDisplayBoardWS` uses `WSManager` internally (Phase 5)
- [ ] `NotificationWebSocketContext` uses `WSManager` internally (Phase 6)
- [ ] `websocketAuth.js` deleted (Phase 7)
- [ ] No file outside `core/ws/` directly constructs `new WebSocket(...)` — CI lint rule
- [ ] **Security**: no WS URL in the codebase contains `?token=` or `&token=` — grep returns 0 results
- [ ] Manual test: kill backend, all systems reconnect with exponential backoff, no thundering herd
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
