# ADR-0004: Enable Queue WebSocket + Add Reconnect

**Status:** ✅ Implemented (2026-07-13)
**Date:** 2026-07-04
**Implemented in:** PR-36 (#2110) — Frontend Sprint 1 security
**Owner:** Frontend Platform
**Related:** `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-1

## Implementation Summary

This ADR was proposed on 2026-07-04 and implemented on 2026-07-12 by
the frontend audit sprint (PR-36, #2110) — without referencing this
ADR. The implementation covers all three phases proposed below:

- **Phase 1 (reconnect + auth + heartbeat):** ✅ Done in `frontend/src/hooks/useQueueWebSocket.js` — exponential backoff (3s → 6s → 12s → 24s → 30s, max 5 attempts), JWT via `Sec-WebSocket-Protocol: bearer.<token>` subprotocol (not URL query).
- **Phase 2 (exponential backoff + infinite retries):** ✅ Done — `RECONNECT_DELAYS = [3000, 6000, 12000, 24000, 30000]` in `useQueueWebSocket.js:33`. Falls back to polling after 5 failed attempts (acceptable — polling is the ultimate fallback).
- **Phase 3 (wire into useDoctorQueue + enable by default):** ✅ Done via a different path — `useQueueWebSocket` is consumed by `frontend/src/components/queue/ModernQueueManager.jsx:145` (the real queue UI), not `useDoctorQueue` (which is only used by the stub `DoctorPanel.jsx` — see P0-1).

The JWT-in-subprotocol approach (PR-36 / P0-3 from frontend audit) is
actually **better** than what this ADR proposed (JWT in query param) —
it avoids leaking the token into nginx access logs and browser history.

The legacy `openQueueWS` function in `frontend/src/api/ws.js:15` is
now dead code (no callers). It can be removed in a future cleanup PR.

---

## Original Proposal (kept for historical context)

## Context

The doctor queue currently updates via **HTTP polling every 30 seconds** (`frontend/src/hooks/useDoctorQueue.js:172`):

```javascript
// Авто-обновление каждые 30 секунд
useEffect(() => {
    loadQueue();
    const interval = setInterval(loadQueue, 30000);
    return () => clearInterval(interval);
}, [loadQueue]);
```

A WebSocket helper `openQueueWS` exists in `frontend/src/api/ws.js:15`, but:

1. **It is disabled by default** — `VITE_ENABLE_WS=0` gates the entire module (`wsEnabled()` at line 6).
2. **It has no reconnect logic** — `ws.onclose = () => {}` (line 32) silently gives up.
3. **It has no authentication** — the URL `/ws/queue?department=&date_str=` carries no JWT, unlike `openDisplayBoardWS` which adds `?token=...` (line 62).
4. **It has no heartbeat** — server-side timeouts will close the connection without the client noticing.
5. **It is never called** — `grep -rn "openQueueWS" frontend/src/` returns only the definition site; no panel or hook invokes it.

### The Problem

The 30-second polling interval causes two concrete issues:

**UX latency:** When a registrar adds a patient to a doctor's queue, the doctor does not see the new patient for up to 30 seconds. In a busy clinic with multiple doctors, this means:
- Doctors call patients who are no longer next in line (race condition with registrar edits)
- Patients wait at the door while the doctor's screen still shows the previous state
- The display board (which DOES use WS via `openDisplayBoardWS`) shows a different state than the doctor's panel — visible inconsistency

**Backend load:** With N doctors logged in, the backend serves `N × 2 requests/minute × 60 minutes × 8 hours = 960N` queue-list requests per day. For a clinic with 20 doctors, that is ~19,200 redundant requests per day — each one computing the full queue snapshot, checking RBAC, and serializing ~50-200 entries.

## Decision

**Enable the queue WebSocket by default, add reconnect + auth + heartbeat, and keep polling as a fallback.**

### Principles

1. **WS is primary, polling is fallback** — when WS is connected, polling pauses; when WS disconnects, polling resumes.
2. **Reconnect with exponential backoff** — start at 1s, double each failure, cap at 30s, reset on successful connect.
3. **JWT in query param** — same pattern as `openDisplayBoardWS` (line 62). The backend already supports this for display board; we extend it to `/ws/queue`.
4. **Heartbeat** — client sends `{type: 'ping'}` every 30s; if no pong within 10s, force reconnect.
5. **No breaking change** — `VITE_ENABLE_WS=0` still disables WS for environments that cannot support it (e.g. behind a reverse proxy without WS upgrade). Polling remains the only path in that case.

### Migration Plan (3 phases, each a separate PR)

#### Phase 1: Add reconnect + auth + heartbeat to `openQueueWS` (Low risk)
- Add `tokenManager.getAccessToken()` to the URL as `?token=...`.
- Add reconnect logic mirroring `openDisplayBoardWS` (5 attempts × 3s, then give up — but see Phase 2 for upgrade to exponential backoff).
- Add ping interval (30s) mirroring `openDisplayBoardWS`.
- Add `onConnect` / `onDisconnect` callbacks so callers can pause polling when WS is up.
- **No env change** — `VITE_ENABLE_WS=0` still gates the function.
- **Estimated diff**: ~60 lines added to `frontend/src/api/ws.js`.
- **Testing**: Unit test `openQueueWS` with a mock WebSocket — verify reconnect on close, ping interval, token in URL.

#### Phase 2: Upgrade reconnect to exponential backoff + infinite retries (Medium risk)
- Replace the 5-attempt × 3s cap with exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s (cap), infinite retries.
- Reset backoff to 1s on successful `onopen`.
- Add jitter (±20% of delay) to avoid thundering herd when the backend recovers.
- Apply the same upgrade to `openDisplayBoardWS` (currently 5 attempts × 3s, then dies — a known issue from `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-3).
- **Estimated diff**: ~40 lines, shared utility `computeBackoff(attempt, base, cap, jitter)`.
- **Testing**: Unit test backoff sequence; manual test — kill backend, verify reconnect attempts at 1/2/4/8/16/30/30/30s.

#### Phase 3: Wire `openQueueWS` into `useDoctorQueue` + enable by default (Medium risk)
- In `useDoctorQueue.js`, replace the `setInterval(loadQueue, 30000)` with:
  ```javascript
  const closeWS = openQueueWS(specialty, todayDateStr, (message) => {
    if (message.type === 'queue_update') {
      setQueue(message.payload);
    }
  }, () => {
    // onConnect — pause polling
    pollingEnabledRef.current = false;
  }, () => {
    // onDisconnect — resume polling
    pollingEnabledRef.current = true;
    loadQueue(); // immediate refresh
  });

  // Fallback polling — only runs when WS is disconnected
  useEffect(() => {
    const interval = setInterval(() => {
      if (pollingEnabledRef.current) {
        loadQueue();
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [loadQueue]);
  ```
- Set `VITE_ENABLE_WS=1` in `frontend/.env.production` and `frontend/.env.staging`.
- Keep `VITE_ENABLE_WS=0` in `frontend/.env.development` (developers can override locally).
- **Estimated diff**: ~50 lines in `useDoctorQueue.js`, ~2 lines in env files.
- **Testing**: Manual — open two browsers (registrar + doctor), registrar adds patient, doctor sees it within 1s (was: up to 30s). Kill WS server, verify polling resumes. Restart WS server, verify polling pauses.

### Acceptance Criteria

- [ ] `openQueueWS` reconnects on close (verified by unit test)
- [ ] `openQueueWS` sends JWT in query param (verified by unit test)
- [ ] `openQueueWS` sends ping every 30s (verified by unit test)
- [ ] `useDoctorQueue` uses WS when available, polling when not (verified by manual test)
- [ ] `VITE_ENABLE_WS=1` in production env (verified by CI env check)
- [ ] Doctor sees new queue entries within 1s (was: up to 30s) — manual clinic test
- [ ] Backend `/ws/queue` endpoint accepts JWT in query param — backend test
- [ ] Backend logs show WS connections persisting for hours without reconnect storms

## Consequences

**Плюсы:**
- Real-time queue updates — 30s latency → <1s latency
- Backend load reduced — ~19,200 fewer requests/day for a 20-doctor clinic
- Display board and doctor panel show consistent state (both use WS)
- Foundation for future real-time features (e.g. "doctor is ready" indicator, patient-called notifications)

**Минусы:**
- WS requires backend support for long-lived connections — confirm reverse proxy (nginx/caddy) is configured for WS upgrade
- More complex than polling — reconnect logic, heartbeat, fallback coordination
- WS connections consume server resources (1 file descriptor per doctor) — confirm backend can handle N=100 concurrent WS
- JWT in query param is logged by some reverse proxies — ensure access logs are sanitized or use subprotocol header instead (Phase 4 candidate)

## Alternatives Considered

### A. Keep polling, reduce interval to 5s
- **Rejected**: 5s polling is 6× the backend load for 6× worse UX than WS. Does not solve the consistency problem with the display board.

### B. Use Server-Sent Events (SSE) instead of WS
- **Rejected**: SSE is unidirectional (server → client), which is sufficient for queue updates, but the existing `openDisplayBoardWS` and `NotificationWebSocketContext` already use WS. Adding SSE would introduce a third real-time transport. Consolidation (ADR-0005) is preferable.

### C. Wait for ADR-0005 (Unified WSManager) before enabling
- **Rejected**: ADR-0005 is a larger refactor. The 30s latency is a present-day UX problem. Phase 1 + Phase 2 of this ADR are independent of ADR-0005 and can ship first. Phase 3 can be re-done as part of ADR-0005 if needed.

## Follow-up

- After Phase 3 is merged, add a CI lint rule that forbids `setInterval(loadQueue, ...)` outside a WS-fallback context.
- Add a `VITE_ENABLE_WS` env check to the production build — fail build if not set to `1`.
- Coordinate with backend team to confirm `/ws/queue` accepts JWT in query param (currently only `/api/v1/display/ws/board/{id}` does).
- Consider Phase 4: move JWT from query param to `Sec-WebSocket-Protocol` header (more secure, avoids log leakage).

## References

- `frontend/src/api/ws.js:15` — current `openQueueWS` (disabled, no reconnect)
- `frontend/src/api/ws.js:51` — `openDisplayBoardWS` (reference implementation with reconnect + ping)
- `frontend/src/hooks/useDoctorQueue.js:172` — current 30s polling
- `frontend/src/contexts/NotificationWebSocketContext.jsx` — reference infinite-reconnect pattern
- `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-1 — original problem statement
- `backend/app/api/v1/endpoints/` — confirm `/ws/queue` endpoint exists and accepts JWT
