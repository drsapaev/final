# ADR-0002: Consolidate API Interceptors

**Status:** Proposed
**Date:** 2026-07-04
**Owner:** Frontend Platform
**Related:** `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P0-2

## Context

The frontend currently has **two parallel axios interceptor systems** that both run on every API request:

### 1. `frontend/src/api/client.js` (lines ~50-150)
The main axios instance. Its request interceptor:
- Adds `Authorization: Bearer <token>` from `tokenManager.getAccessToken()`
- Adds CSRF token for state-changing methods (single-flight via `csrfTokenPromise`)
- Implements global 429 cooldown (60s, persisted in `localStorage.clinic_api_rate_limit_until`)
- Implements single-flight JWT refresh (if exp < 5 minutes, via `refreshPromise` mutex with `pendingRequestsQueue`)

Its response interceptor:
- 401 → only logs (does NOT clear auth state, to avoid race conditions during login transition)
- 429 → sets global cooldown + persists

### 2. `frontend/src/api/interceptors.js` (202 lines)
A separate `setupInterceptors()` function called from `main.jsx:18`. Its request interceptor:
- **DUPLICATE**: Adds `Authorization: Bearer <token>` (same as client.js)
- Adds request metadata (timestamp, requestId)

Its response interceptor:
- 401 → retry-after-refresh via `_retry` flag + repeats the original request
- Uses `shouldClearAuthOnUnauthorized()` to skip clear-auth for login/csrf/refresh endpoints
- Supports `silent` mode (skips toast), `expectedErrorStatuses`, CanceledError suppression
- Has its own `handleError()` with centralized toast logic

### The Problem

Both interceptor systems are active simultaneously. On a single 401 response:

```
client.js response interceptor runs → logs only
                                          ↓
interceptors.js response interceptor runs → triggers refresh + retry
```

But both request interceptors already added the `Authorization` header. If the refresh happens in `interceptors.js`, the new token from `client.js`'s single-flight `refreshPromise` may or may not be picked up — depending on timing.

**Concrete race condition scenario:**

1. User's JWT expires at T=0.
2. At T=0.001, two parallel requests fire: `GET /patients/42` and `GET /v2/emr/99`.
3. Both get 401.
4. `client.js` response interceptor logs both 401s.
5. `interceptors.js` response interceptor sees the first 401, checks `_retry` flag (not set), calls `refreshToken()`.
6. `client.js` request interceptor's single-flight `refreshPromise` mutex kicks in — only one refresh actually hits the backend.
7. `interceptors.js` response interceptor sees the second 401, also tries `refreshToken()` — gets the same `refreshPromise` (good).
8. Refresh resolves. Both requests retry.
9. **Bug**: `interceptors.js` retries with the old request config, which has the OLD `Authorization` header. The new token from step 6 may not be re-added because `client.js` request interceptor already ran for the original request and won't re-run for the retry.

**Symptoms observed in production (anecdotal):**
- Random logouts after 1 hour of inactivity (token expiry)
- "Двойной" refresh token calls in backend logs
- Intermittent 401 cascades that clear auth state unexpectedly

## Decision

**Consolidate all interceptor logic into `frontend/src/api/client.js`.**

### Principles

1. **Single source of truth for auth headers** — only `client.js` request interceptor adds `Authorization`.
2. **Single source of truth for 401 handling** — only `client.js` response interceptor handles 401 (refresh + retry). No `_retry` flag.
3. **Single source of truth for 429 cooldown** — already in `client.js`, no change.
4. **Single source of truth for error toasts** — `interceptors.js` keeps its `handleError()` function but it becomes a pure function called from `client.js`, not a separate interceptor.

### Migration Plan (3 phases, each a separate PR)

#### Phase 1: Extract `handleError` from `interceptors.js` (Low risk)
- Move `handleError()`, `shouldClearAuthOnUnauthorized()`, `expectedErrorStatuses` logic into a new `frontend/src/api/errorHandler.js` module.
- `interceptors.js` imports it — no behaviour change.
- Add unit tests for `handleError` and `shouldClearAuthOnUnauthorized`.
- **Estimated diff**: ~150 lines moved, 0 behaviour change.

#### Phase 2: Move 401 retry logic into `client.js` (Medium risk)
- Replace `client.js` response interceptor's "log only" 401 handler with the full refresh+retry logic from `interceptors.js`.
- Use the existing `refreshPromise` single-flight mutex.
- On refresh success → retry the original request with the new token (re-run request interceptor to add the new `Authorization` header).
- On refresh failure → `clearAuthState()` + redirect to `/login`.
- Remove the 401 handler from `interceptors.js`.
- **Estimated diff**: ~80 lines moved, behaviour change (better 401 handling).
- **Testing**: Manual 401 flow test (let JWT expire, verify single refresh + retry, no double logouts).

#### Phase 3: Remove `interceptors.js` entirely (Low risk, after Phase 2 stabilises)
- `main.jsx` no longer calls `setupInterceptors()`.
- Delete `frontend/src/api/interceptors.js`.
- All interceptor logic now lives in `client.js`.
- **Estimated diff**: -202 lines, 0 behaviour change.

### Acceptance Criteria

- [ ] `frontend/src/api/interceptors.js` is deleted
- [ ] `frontend/src/api/client.js` is the only file that calls `axios.interceptors.request.use` / `axios.interceptors.response.use`
- [ ] Unit test: simulate 401 → verify exactly 1 refresh call → verify exactly 1 retry with new token
- [ ] Unit test: simulate 2 parallel 401s → verify exactly 1 refresh call (single-flight)
- [ ] Unit test: simulate refresh failure → verify `clearAuthState()` + redirect to `/login`
- [ ] Manual test: let JWT expire, verify no double logouts
- [ ] Backend logs: verify no "double refresh" pattern in `/auth/refresh` endpoint logs

## Consequences

**Плюсы:**
- Single source of truth for auth + error handling
- No race condition between two interceptor systems
- Easier to reason about 401 flow
- Fewer lines of code (~200 lines deleted in Phase 3)
- Better test coverage (unit tests for each 401 scenario)

**Минусы:**
- 3-phase migration requires coordination — each phase is a separate PR
- Phase 2 is medium risk — manual 401 testing required
- Existing `silent` / `expectedErrorStatuses` flags must be preserved in the consolidated handler
- Backend logs may show a temporary change in `/auth/refresh` call patterns during migration

## Alternatives Considered

### A. Keep both interceptors, but disable one
- Mark one interceptor as "deprecated" and add a feature flag.
- **Rejected**: Both interceptors are active in production today; disabling one without consolidation risks breaking the 401 flow.

### B. Use axios `instance.defaults` for auth header instead of interceptor
- Set `axiosInstance.defaults.headers.common['Authorization'] = 'Bearer ' + token` whenever the token changes.
- **Rejected**: Doesn't handle the refresh-on-401 flow — we still need a response interceptor for that. And `defaults` is harder to invalidate when the token refreshes mid-flight.

### C. Switch to a different HTTP client (e.g. `ky`, `got`, native `fetch`)
- Replace axios entirely with a smaller client.
- **Rejected**: Too large a change for the benefit. Axios interceptors are well-understood by the team, and the consolidation in Phase 1-3 solves the actual problem without a rewrite.

## Follow-up

- After Phase 3 is merged, add a CI lint rule that forbids any new file from calling `axios.interceptors.*.use` outside `client.js`.
- Add the 401 race condition scenario to `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md` as a manual smoke test.
- Consider extracting the 429 cooldown logic into its own module (`api/rateLimitHandler.js`) so it can be tested independently.

## References

- `frontend/src/api/client.js` — current main interceptor
- `frontend/src/api/interceptors.js` — current duplicate interceptor (to be removed)
- `frontend/src/main.jsx:18` — `setupInterceptors()` call site
- `frontend/src/utils/tokenManager.js` — token storage
- `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P0-2 — original problem statement
- `backend/app/api/v1/endpoints/auth.py` — `/auth/refresh` endpoint
