# QR patient join — legacy token, session horizon and post-complete handling

**Review date:** 2026-11-05  
**Repository/base:** `drsapaev/final`, main `1e7e43dc738400544ae34294f17c439a3499a6c7`  
**Evidence:** SOURCE-OBSERVED; browser / Vitest reproduction pending. Not a runtime fix.  
**Review scope:** public QR patient registration; new findings QR-FE-028–030.

## Scope, authority and baseline

- **Mode:** `direct_execute` for this narrow docs-only audit. No executable code, queue-fairness/ownership/security policy, API, migration, test, data or infrastructure change. **A fix touching the QR/queue business contract requires the mandatory `AGENTS.md` gate** (`ai/langgraph/scripts/run_agent_gate.ps1` from `ai/langgraph`), fail-first tests, and a separate implementation PR.
- **Allowed write:** this exact Markdown audit file only. **Denied:** `frontend/**`, `backend/**`, `ops/**`, `.github/**`, production/staging changes, PR merges, patient/queue/clinical data.
- **Sources reviewed:** `frontend/src/pages/QueueJoin.tsx` (3,615+ LOC), `frontend/src/api/queue.ts`, `frontend/src/api/queueDirections.ts`, `frontend/src/api/mappers/queue.ts`, `frontend/src/types/domain/queue.ts`; tests `QueueJoin.legacyAttemptRecovery.test.tsx`, `QueueJoin.direction.test.tsx`, `QueueJoin.partialResult.test.tsx`, `QueueJoin.accessibility.test.tsx`; backend `qr_queue/_join.py`, `qr_queue/_helpers.py`, `services/qr_queue/_sessions.py`. Reviewed root `AGENTS.md` and repo `final-ssot-contract-repair`/`code-security` skills.
- **Deduplication:** QR-FE-001–007 in the prior registrar/cashier/QR follow-up audit are **not** reopened; QR-FE-005/006 already added the legacy unknown-attempt envelope and best-effort persistence for the *session-start* path. The QR realtime/board audit #3875 reaches QR-FE-027; these new IDs start at 028. Existing separate backup source audit #3882 is intentionally retained as Draft: the user explicitly switched to the next frontend file group.
- **Validation boundary:** reviewed GitHub source and test fixtures only. No component tests, real HTTP requests, browser, queue mutating actions, PostgreSQL or clinical data accessed. The below examples are *proposed synthetic repros*, not evidence that a production patient was misrouted or that duplicate tickets occurred.

## Findings

| ID | Priority candidate | Source-observed defect | Real-world consequence (conditional) |
| --- | --- | --- | --- |
| **QR-FE-028** | **P1** | Legacy `/queue/join/:token` lacks stale-response/epoch guards on asynchronous token-info and session-start calls | A delayed response for QR A can overwrite QR B's live UI/session in the same mounted route |
| **QR-FE-029** | **P1 candidate** | Legacy attempt envelope always writes `attemptExpiresAt: null` despite backend exposing `attempt_expires_at` | A next-day unknown attempt may be discarded at fixed 24h before the target queue day ends |
| **QR-FE-030** | **P1 candidate** | An unguarded `localStorage.setItem('lastQueueJoin', …)` runs *after* successful completion and after deleting the attempt recovery envelope | Storage quota/security failure turns a committed success into an unknown/failure screen; reload no longer retains the original attempt identity |

### QR-FE-028 — Legacy QR A/B navigation accepts late cross-token responses (P1 candidate)

**Source:**

- [`QueueJoin.tsx:515–524`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L515-L524) computes `legacyToken` from route/query.
- [`QueueJoin.tsx:815–850`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L815-L850) awaits `startQueueJoinSession(legacyToken)` and unconditionally calls `setSessionToken`, `setQueueInfo`, `setAvailableSpecialists`, `setStep` regardless of whether the route has since switched to another legacy token.
- [`QueueJoin.tsx:852–908`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L852-L908) awaits `fetchQrTokenInfo(legacyToken)` and applies its results without an abort/epoch or active-token check. [Boot effect:911–980](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L911-L980) runs on token change but does not cancel old promises or check ownership in their completions.
- The **permanent-direction** path already uses `directionEpochRef` and guards its async callbacks; this protection is not applied to the legacy path. The backend joins on **session token**, so a stale session A need not match the current browser URL B in order to perform an A-scoped registration. Backend is still SSOT of its token/owner.

**Timeline:** A route starts info/session request; user switches client-side to QR B without remount; B info/start resolves and shows B; A resolves late, overwriting page with A's queue info/session. A subsequent form submit could use session A while the address bar says B, leading to unexpected department/doctor queue selection. This is a client async identity bug, **not** proof of server-side queue permission bypass.

**Fail-first:** React `MemoryRouter` route instance with a navigation control A→B; use deferred mock promises for both `fetchQrTokenInfo` and `startQueueJoinSession`. Resolve B first, A last. Assert B's visible owner, selected options and `session_token` sent to `completeQueueJoinSession` are still B; no A-specific state or success/error can be painted after route change. Reverse the resolution order and repeat across query-token input. Do not use real patient names.

**Repair boundary:** introduce legacy request-epoch/abort and token ownership guards for info/start/errors/finally; reset B's stale A session/context on token change. Preserve the direction-mode recovery and server-owned queue identity.

### QR-FE-029 — Legacy QR discards the server's queue-day attempt horizon (P1 candidate)

**Source:**

- [Backend `JoinSessionStartResponse:220–241`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/backend/app/api/v1/endpoints/qr_queue/_helpers.py#L220-L241) publishes `target_date` and `attempt_expires_at`. [`_sessions.py:417–447`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/backend/app/services/qr_queue/_sessions.py#L417-L447) computes it from the target queue-day in clinic timezone plus grace, **for the same public `/queue/join/start` path**.
- [Frontend `QueueJoinSessionData`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/types/domain/queue.ts) declares only `session_token` and `queue_info`; [`QueueJoin.tsx:815–850`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L815-L850) drops the other backend fields.
- [`QueueJoin.tsx:1720–1802`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L1720-L1802) writes a legacy `kind='qr'` attempt envelope with **`attemptExpiresAt: null`**. [`attemptStateHorizonValid:182–193`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L182-L193) then applies a fixed 24h TTL when horizon is null.
- Direction-mode tests already pin the server absolute horizon; the legacy recovery test `QueueJoin.legacyAttemptRecovery.test.tsx` seeds `attemptExpiresAt: null`, not a returned next-day horizon.

**Failure precondition:** a standard QR start session targets a future queue day (e.g. a legitimate next-day QR), a `/join/complete` response is lost after the business command, and the patient returns after 24h but before the target day's configured horizon. The legacy envelope is dropped, so the original session can no longer be probed/replayed through UI. A new attempt may be started; the backend duplicate guard can still prevent duplicate tickets for the same patient, so **do not claim duplicates are guaranteed**.

**Fail-first:** mock `/queue/join/start` returning `attempt_expires_at` well beyond `Date.now()+24h`, submit with a deferred/lost complete response, verify saved `queue_join_attempt_qr_<token>__<session>` has the **actual backend horizon**, then advance fake clock beyond 24h but before the returned horizon and remount. Assert no new session is minted, with original token available for reconciliation.

**Repair boundary:** extend typed `QueueJoinSessionData` with `attempt_expires_at?: string|null`; capture and use the backend horizon for the actual legacy session and each renewal. Keep 24h fallback **only** for old responses without that field; preserve PHI-free envelope and strict write verification.

### QR-FE-030 — Post-commit localStorage error misclassifies a confirmed join (P1 candidate)

**Source:**

- [`QueueJoin.tsx:1798–1825`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L1798-L1825) receives a successful `completeQueueJoinSession`, sets result and **deletes the per-attempt recovery envelope** (outcome known).
- [`QueueJoin.tsx:1827–1895`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L1827-L1895) dispatches `queueUpdated`, then does a **raw**, unguarded `localStorage.setItem('lastQueueJoin', …)` before `setStep('success')`. [Catch:1897–1977](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/QueueJoin.tsx#L1897-L1977) interprets the thrown exception as a business submit failure/unknown outcome. Earlier best-effort `legacyStorageSet` only covers session-start, not this post-success code.
- [`RegistrarPanel.tsx:219–220`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/RegistrarPanel.tsx#L219-L220) says the old `lastQueueJoin` polling consumer was removed; current queue consumers use WS/`queueUpdated`. Thus this persisted sync flag has no demonstrated active registrar need.

**Failure precondition:** `/join/complete` commits and returns success, but browser storage quota, security policy or disabled storage makes the later `lastQueueJoin` write throw. UI can show an error/UNKNOWN state instead of the actual ticket; the original recovery envelope has already been deleted, so a reload may automatically mint a new session. Actual duplicate creation is not proven; the critical observed violation is **a non-business side effect overriding a known successful business result**.

**Fail-first:** mount single and multi join flows with a synthetic 2xx issued-ticket DTO. Mock verified attempt-envelope writes as successful, but throw only for key `lastQueueJoin`. Assert success page and ticket number render, no `submitResultUnknown`, no new `startJoinSession` on reload; preserve result and no lingering unneeded `lastQueueJoin` persistence. Add a separate test that `queueUpdated` consumer errors do not turn a successful response into false failure.

**Repair boundary:** remove unused lastQueueJoin persistence after confirming no active consumer (or isolate as best-effort nonclinical telemetry); business success state must be committed/rendered regardless of any localStorage or presentation side effect. Do not move queue mutation/fairness into frontend and do not log PHI.

## Existing protections / no duplicate claim

- QR-FE-001 (no patient PHI draft on public/shared QR), QR-FE-005 (legacy UNKNOWN envelope/owner markers), QR-FE-006 (best-effort *start-session* persistence), and direction route epoch/horizon are implemented; these new gaps concern distinct legacy A/B navigation, dropped legacy server horizon, and **post-commit** sync persistence.
- `mapQueueActionResponseDto` preserves the backend response fields via object spread; no finding is alleged for losing `entries`/partial errors.
- The backend remains authority for actual target-day/owner, session idempotency and duplicate prevention; none of these findings claims an observed production misrouting or successful RBAC/queue ownership bypass.
- The public join response is a *session attempt*, not an authorization token for acting on other patients. Test artifacts must contain only synthetic identities and no real clinic PHI.

## Proposed follow-up order

1. QR-FE-028 P1: test interleaved QR A/B on the same mounted route, then scoped epoch/abort fix.
2. QR-FE-030 P1 candidate: test 2xx success + throwing `lastQueueJoin` persistence; isolate/remove nonbusiness side effect.
3. QR-FE-029 P1 candidate: test delayed unknown attempt beyond 24h, then pass server horizon through typed client.
4. Narrow frontend Vitest + TypeScript/ESLint + applicable backend shape tests. In a separate security/queue gated fix PR; no user-data or production operations.

## Verification and rollback

- **Performed:** GitHub source and existing tests read; current main pinned; checked earlier QR audit IDs and previous fixes; no runtime code changed. This audit records static defects and fail-first repro plans.
- **Not performed:** application Vitest, React browser, actual QR scan/registration, source-level tests, mandatory gate (no protected code edit), `git diff --check` local, staging/production, real DB or network requests.
- **Rollback:** close/revert this docs-only Draft PR. Any future fix requires fresh main, mandatory queue contract gate, red-first tests and independent review, with merge/deployment approval separate.
