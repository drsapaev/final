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

## Next frontend group — doctor queue API/client paths (2026-11-05 follow-up)

**Owner direction:** append review findings and comment in **the same Draft PR #3886**; do not create a new PR. Scope remains a docs-only source review. Extra read-only files: `frontend/src/components/doctor/DoctorQueuePanel.tsx`, `frontend/src/pages/DoctorPanel.tsx`, `frontend/src/services/queue.ts`, `frontend/src/hooks/useQueueApi.ts`, `frontend/src/utils/queueApi.ts`, `frontend/src/api/client.ts`; the existing `DoctorQueuePanel.test.tsx`, `backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py`, plus consumer search for `queueService.callNextWaiting`. Read-only checks use pinned main `1e7e43dc738400544ae34294f17c439a3499a6c7`.

### DOCQ-FE-001 — P1 candidate: in-flight queue responses can overwrite another specialty's panel

- **Source:** [`DoctorQueuePanel.tsx:194–220`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/doctor/DoctorQueuePanel.tsx#L194-L220) re-runs loading on `specialty` change, but does not abort/epoch-guard the earlier request. [`DoctorQueuePanel.tsx:257–292`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/doctor/DoctorQueuePanel.tsx#L257-L292) unconditionally `setQueueData(data)` after an awaited `fetch` and does not clear previous specialty's queue on failed response. DoctorPanel supplies `specialty={doctorSpecialty}`.
- **Failure precondition:** same mounted component changes A→B while A's request is outstanding. B's response arrives first; A then resolves and replaces B's displayed patient names/phones, despite the route/prop still describing B. Alternatively, B returns 403/network error and A's previous queue remains visible. Backend authorizes each request independently; no server authorization bypass is alleged.
- **Fail-first test:** a `rerender` with specialty A then B, deferred `fetch` promises; resolve B then A. Assert B's queue stays visible; repeat when B's response is 403/500 and assert B displays a real unavailable/error state, never A's rows.
- **Suggested repair:** request identity epoch + stale-result guard or `AbortController`, including error/finally branches; reset queue state on identity change and deny stale patient views.

### DOCQ-FE-002 — P2: doctor queue raw fetch bypasses canonical JWT refresh/retry

- **Source:** [`DoctorQueuePanel.tsx:235–292`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/doctor/DoctorQueuePanel.tsx#L235-L292) and [`296–404`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/doctor/DoctorQueuePanel.tsx#L296-L404) use `fetch(buildApiUrl(...), {Authorization: Bearer getAccessToken()})` for reads and call/start/complete. [`api/client.ts:465–527`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/api/client.ts#L465-L527) implements single-flight access-token refresh and 401 retry **only** on the central axios `api` instance.
- **Consequence:** if staff JWT expires during this screen, a `fetch` can receive 401 and miss the shared refresh/Retry machinery; commands fail until independent re-auth/refresh and may leave stale queue UI. **No claim** this bypasses RBAC or exposes otherwise unauthorized data.
- **Fail-first test:** mocked 401 on first queue read or action, synthetic valid refresh token, 200 upon retry. Compare with central API behavior; require exactly one safe refresh/retry, and never replay a non-idempotent command blindly after an ambiguous network failure.
- **Suggested repair:** migrate these requests through the canonical `api/client.ts` abstraction, preserving backend status details and the domain's command retry/idempotency policy. This is a separate auth/contract-gated implementation PR.

### DOCQ-FE-003 — P2: error is rendered as “queue not created” or stale patient list

- **Source:** [`DoctorQueuePanel.tsx:278–292`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/doctor/DoctorQueuePanel.tsx#L278-L292) stores failed fetch as `message` but does not clear or mark queue as failed. [`DoctorQueuePanel.tsx:413–446`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/doctor/DoctorQueuePanel.tsx#L413-L446) returns `AppEmpty` whenever `!queueData || !queueData.queue_exists`, **before** the `message` alert is rendered.
- **Consequence:** on initial 401/403/500, the user sees “Очередь не создана” rather than an access/network error; after a successful prior load, an error can preserve old rows and action buttons. This is a frontend truthfulness/display-state issue, **not** an assertion that backend permits a stale action.
- **Fail-first test:** mount with a failed fetch and assert a visible error/retry, not `queue not created`; then load A successfully and make refresh fail, asserting stale data is clearly flagged/hidden and cannot be treated as a fresh queue state.
- **Suggested repair:** distinct `loading | ready | truly_empty | error` display model; parse backend errors safely (including non-JSON), keep backend `queue_exists=false` only for successful canonical responses.

### QAPI-FE-001 — P2 candidate: fallback re-derives next patient when server said “none”

- **Source:** [`services/queue.ts:89–99`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/services/queue.ts#L89-L99) applies a local fallback `entries.find(can_call)` if `next_call_entry_id` is null. [`services/queue.ts:135–145`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/services/queue.ts#L135-L145) submits the chosen `/doctor/queue/<id>/call`. Canonical [`_queue_ops.py:170–210,281–293`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py#L170-L293) computes and **always returns** `next_call_entry_id`, including explicit `null` when no entry is callable.
- **Failure precondition:** an inconsistent/stale/older payload has `next_call_entry_id:null` but an entry still advertises `can_call:true`. The UI then invents its own candidate despite the canonical server's *explicit* null choice; the backend call mutation still must validate the command. Current canonical backend computes both values from the same flags, so this is a **contract-drift guard**, not a demonstrated live queue-fairness violation.
- **Fail-first test:** response `{ next_call_entry_id:null, entries:[{id:17, available_actions:['call']} ] }` → `callNextWaiting` must **not** POST; response with valid canonical id must POST only that id. Also check omitted field as a contract failure rather than silently guessing first.
- **Suggested repair:** fail closed on missing/null canonical `next_call_entry_id`; render a retriable contract/invalidation message, and rely on backend SSOT for call order. This path is used by cardiology, dermatology and dentistry panels.

### Scope and evidence limits for this group

- The separate `frontend/src/utils/queueApi.ts` provides another `useQueueManager` / UTC-based default day, but search finds no active consumers of its `getQueueStatusBySpecialist` export outside that utility. Do **not** label an unused path as an active production failure without a caller.
- `frontend/src/hooks/useQueueApi.ts` is a thin typed wrapper; no standalone defect has been established in its 51 lines.
- `DoctorQueuePanel.test.tsx` covers canonical API origin and action availability from backend flags, but has no deferred A/B response race, 401 retry or failure-screen regression. No tests were run in this docs-only pass.
- Fail-first tests remain proposed only. No real patient, database, network, server or runtime changes. Future code fixes for authentication/queue identity require mandatory `AGENTS.md` gate, synthetic tests, and a separately approved implementation scope.

## Next frontend group — doctor hooks and cardiology queue (2026-11-05 follow-up)

**Same PR #3886, no new branch or PR.** Scope is a docs-only source review of `frontend/src/hooks/useDoctorQueue.ts`, `frontend/src/hooks/useQueueManager.ts`, `frontend/src/components/cardiology/CardiologyQueueTab.tsx`, their consumers (`DoctorPanel.tsx`, `CardiologistPanelUnified.tsx`, `ModernQueueManager.tsx`), pertinent Vitest suites (`CardiologyQueueTab.test.tsx`, `useQueueManager.snapshot.test.ts`, `useQueueManager.resourceAxis.test.ts`), and canonical `doctor_integration/_queue_ops.py` queue metadata. Main reference: `1e7e43dc738400544ae34294f17c439a3499a6c7`; only audit Markdown is writable. Repo `AGENTS.md`, `final-ssot-contract-repair` and `code-security` skills consulted. No executable or contract repair authorized by this review.

### CARDQ-FE-001 — P1 candidate: overlapping cardio polling responses are not ordered by request identity

- **Source:** [`CardiologyQueueTab.tsx:60–90`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/cardiology/CardiologyQueueTab.tsx#L60-L90): `loadQueue` is invoked on mount, on every `queueUpdated` event and by a 30-second interval. Every request independently does `setQueue(result)`, `setError(false/true)`, and `setLoading(false)`; there is no request epoch, response-ownership check or abort.
- **Scenario:** A starts, queue changes and event starts B, B returns the new patient list, then A resolves and overwrites it with the old list. Another interleaving lets an older request's `finally` remove B's loading indicator or its `catch` add an erroneous alert. This can display obsolete call/start actions, even though server-side action/authorization is separately validated.
- **Fail-first:** deferred `getTodayQueue` promises; trigger A on mount and B via `queueUpdated`, resolve B with version B and A last with version A. Assert version B remains authoritative and loading/error reflect **only** B. Repeat with A rejection and B pending. Existing `CardiologyQueueTab.test.tsx` covers action/empty states, not overlapping reads.
- **Repair:** monotonically increasing request ID or `AbortController`/identity guard over success/catch/finally; preserve event- and polling-based refresh. No frontend queue-order computation.

### CARDQ-FE-002 — P2: after failed refresh, error panel is displayed alongside still-actionable stale queue

- **Source:** [`CardiologyQueueTab.tsx:60–74`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/cardiology/CardiologyQueueTab.tsx#L60-L74) sets `error=true` but retains `queue` on rejection. [`CardiologyQueueTab.tsx:137–155`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/cardiology/CardiologyQueueTab.tsx#L137-L155) renders an error *and then* the old `entries` list whenever `loading` is false. [L182–205](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/cardiology/CardiologyQueueTab.tsx#L182-L205) still renders call/start buttons based on stale `available_actions`.
- **Scenario:** initial fetch succeeds with waiting ticket X; next fetch returns 403, 500 or network failure. The screen warns but still renders X with active `call`/ `start_visit` from the previous snapshot. Backend command guards may refuse; frontend no longer distinguishes current actionable state from an obsolete snapshot.
- **Fail-first:** initial success containing `available_actions:['call']`, then trigger refresh with rejected/403 response. Assert error and retry are visible, **no callable stale buttons**; after a successful refresh, verified current actions return. No real patient names.
- **Repair:** fail-closed on actions during failed/stale reads; optionally keep visibly marked last-known rows read-only, but only backend-confirmed fresh data may enable commands. Distinct from the other `DoctorQueuePanel` failure-screen finding: this is the cardiology component with a different update pathway.

### QMAN-FE-001 — P2: failed current doctor/date snapshot leaves another selection's queue visible

- **Source:** [`useQueueManager.ts:183–260`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useQueueManager.ts#L183-L260) guards stale epochs but, when the *latest* `fetchQueuesToday(targetDate)` fails, rethrows without clearing `queueData` or `statistics`. [`ModernQueueManager.tsx:182–199`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/queue/ModernQueueManager.tsx#L182-L199) catches and **only logs** that error; the stale queue is then still passed to `QueueTable` and old `queueData.is_open` conditions remain available.
- **Scenario:** doctor A/day D successfully loads; user selects doctor B or day D+1; fetching B fails. The hook leaves A's data on-screen while the dropdown shows B. Previous REG-FE-035/068 tests assert stale *responses* cannot overwrite a newer selection, but do not assert that current-request **failure** removes the old selection's data.
- **Fail-first:** load doctor A, switch to B with a rejecting fetch, assert neither A's rows nor A's `is_open` decision are presented as B's current queue and that a recoverable error is visible. Repeat same doctor with a different target day. Preserve existing success/pending overlap tests.
- **Repair:** reset or scope data to selected `specialistId, targetDate` when a new selection begins; expose an error state on the hook and show non-actionable retry UI on current failure. Keep the backend SSOT for queue ownership/open state.

### QAPI-FE-001 — Additional independently observed consumer, no duplicate finding

- [`useDoctorQueue.ts:61–74`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useDoctorQueue.ts#L61-L74) implements the **same** null/absent `next_call_entry_id` fallback to the first `available_actions:['call']` entry already filed as `QAPI-FE-001` for `services/queue.ts`. [`useDoctorQueue.ts:156–183`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useDoctorQueue.ts#L156-L183) uses the fallback for `callNext()`.
- Backend [`doctor_integration/_queue_ops.py:188–210,283–293`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py#L188-L293) always emits canonical `next_call_entry_id` including explicit null.
- Extend the **same** fail-first null-response test to both helpers. No new ID: no demonstrated real queue-fairness violation when the backend is internally consistent.

## Verification boundaries for the latest group

- **Confirmed:** source contains independent overlapping async writes, stale actionable list after rejected cardio refresh, previous-selection state preservation on latest snapshot failure, and repeated frontend next-call fallback. Compared against current source and existing test scenarios.
- **Not run:** Vitest, Playwright/browser, real queue actions, backend DB, local `git status`, gate launcher, TypeScript/ESLint. These remain source-observed risks with proposed fail-first tests, not reproduced end-to-end failures or fixes.
- **Security/policy:** server remains sole owner of queue identity, fair ordering, command permission and action execution. No patient PHI used. Future queue/contract implementation requires mandatory agent gate before any source edit; this PR is strictly documentation/commentary and remains Draft.

## Next frontend group — specialty visit completion and auto-call (2026-11-05)

**Scope:** Same Draft PR #3886; docs-only source review of `frontend/src/pages/dentist/useDentistActions.ts`, `frontend/src/pages/DermatologistPanelUnified.tsx`, `frontend/src/pages/CardiologistPanelUnified.tsx`, `frontend/src/services/queue.ts` and `frontend/src/components/common/ConfirmDialog.tsx`; read-only comparison with `backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py` and existing dentist unit tests. Base main `1e7e43dc738400544ae34294f17c439a3499a6c7`. **Findings source-observed, tests pending.** No live clinic data or queue operations.

### DOCFLOW-FE-001 — P1 candidate: completion success rendered without confirmed backend ACK

- **Source:** [`services/queue.ts:19–61`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/services/queue.ts#L19-L61) catches 2xx `res.json()` parse failures and returns `null`; [`services/queue.ts:123–132`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/services/queue.ts#L123-L132) fires `queueUpdated` and returns that result without checking `success`.
- **Consumers:** [dentist `useDentistActions.ts:369–385`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/dentist/useDentistActions.ts#L369-L385), [dermatologist `DermatologistPanelUnified.tsx:1247–1270`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/DermatologistPanelUnified.tsx#L1247-L1270) and [cardiologist `CardiologistPanelUnified.tsx:1250–1271`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/CardiologistPanelUnified.tsx#L1250-L1271) treat a nonthrowing completion as confirmed, show success, reset patient/visit state, and may auto-call the next patient.
- **Precondition:** 2xx body missing/invalid JSON, or 2xx body with `success:false`; normal [backend complete endpoint](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py#L1198-L1220) returns `success:true`. **Do not claim a normal backend call emits malformed JSON.** A broken response is ambiguous: server may have committed; no blind retry.
- **Fail-first:** mock 200 with `json()` rejection and 200 `{success:false}`; assert **no confirmed success, no clinical-state reset, no auto-next-call** until current backend status is reconciled. Positive test: `{success:true}` permits success.
- **Suggested fix:** typed positive DTO acknowledgment, explicit `confirmed / rejected / unknown` state, reconcile unknown result with canonical server before any retry; protected clinical/queue contract code requires mandatory gate.

### DOCFLOW-FE-002 — P1 candidate: pending confirmation not bound to selected patient/visit

- **Source:** [dentist `useDentistActions.ts:294–350,369–375`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/dentist/useDentistActions.ts#L294-L375) captures patient/queue id before awaiting `confirm()` and does not recheck current identity before POST/reset. [Cardiology `CardiologistPanelUnified.tsx:1157–1169,1232–1261`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/CardiologistPanelUnified.tsx#L1157-L1261) similarly lacks post-confirm identity validation.
- **Precondition:** route/deeplink or app state changes selection A→B while modal promise for A is pending. Stale A handler can complete A and clear B's displayed state. A modal limits ordinary clicks, so this is conditional; no production miscompletion asserted.
- **Existing safe precedent:** [dermatology `DermatologistPanelUnified.tsx:1220–1249`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/pages/DermatologistPanelUnified.tsx#L1220-L1249) snapshots `currentVisitContext` and rechecks `isSameDermatologyVisit(completionContext, currentVisitContextRef.current)` after confirmation.
- **Fail-first:** deferred `confirm()`, start completion for synthetic A, rerender/navigate B before resolving it true, assert no stale POST and B state not wiped. Repeat with unchanged selection for positive path.
- **Suggested fix:** bind confirmation to queue-entry/patient/visit identity; check active context after every async boundary before irreversible POST and UI reset. Backend authorization remains SSOT.

### DOCFLOW-FE-003 — P2 candidate: auto-call returns fabricated success without backend call ACK

- **Source:** [`services/queue.ts:135–145`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/services/queue.ts#L135-L145) POSTs `/doctor/queue/<id>/call`, ignores response and always returns `{success:true,entry:nextEntry}` using the previous GET. [Backend `_queue_ops.py:655–674`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py#L655-L674) returns the canonical `success:true` and updated entry when the operation commits.
- **Precondition:** unusual 2xx response with `success:false` or unreadable body (becomes `null`); the frontend still broadcasts a patient-called event and shows a next-patient-called success. Normal 4xx/5xx throws, so is excluded.
- **Fail-first:** synthetic GET with `next_call_entry_id:17`, POST 200 `{success:false}` or malformed body, verify **no fabricated positive acknowledgment** and no misleading refresh event. 200 `success:true` should use returned backend entry. Ambiguous call must reconcile before retry.
- **Suggested fix:** check positive result and propagate canonical response; distinct from QAPI-FE-001 about choosing an ID when backend explicitly says none.

### Verification and stop conditions

- Existing dentist tests exercise successful completion and rejected next-call, not 2xx malformed or stale confirm identity. Dermatology's post-confirm check is a positive reference. Findings are static/source-confirmed, **not** Vitest-reproduced. This docs-only pass has not run browser/pytest, real queue commands, user data, gate launcher or production actions.
- Allowed write: only this audit Markdown and a top-level Conversation comment on PR #3886. No code fixes, test commits, new PR or merge. Protected queue/clinical changes require a later mandatory agent gate and fail-first tests.

## Next frontend group — manager called-patient state and WebSocket reconnect (2026-11-05 follow-up)

**Scope:** Same Draft PR #3886, no new PR and no executable code changes. Reviewed `frontend/src/components/queue/ModernQueueManager.tsx`, `frontend/src/components/queue/QueueTable.tsx`, `frontend/src/hooks/useQueueWebSocket.ts`, `frontend/src/components/QueueIntegration.tsx`, `frontend/src/api/queue.ts`, relevant `ModernQueueManager.dentalStartVisit.test.tsx`, `QueueManager.contract.test.tsx`, `QueueTable.keyboardNav.test.tsx`, `QueueTable.stickyHeader.test.tsx` and canonical `backend/app/ws/queue_ws.py` / `services/qr_queue/_queue_ops.py`. Existing QR-FE-010 (heartbeat ping missing pong) in previous audit was checked and deliberately not duplicated. Findings remain **source-observed / regression tests pending**. Base source: `1e7e43dc738400544ae34294f17c439a3499a6c7`.

### QMAN-FE-002 — P1 candidate: called-patient action persists across doctor/date context switches

- **Source:** [`ModernQueueManager.tsx:118–129`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/queue/ModernQueueManager.tsx#L118-L129) derives current `effectiveDoctor/effectiveDate` but stores `calledPatients` as a component-lifetime list with no doctor/date owner. [`ModernQueueManager.tsx:379–421`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/queue/ModernQueueManager.tsx#L379-L421) appends a called entry's `patient` to that list and only removes it after `onStartVisit` says success. [`ModernQueueManager.tsx:791–811`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/components/queue/ModernQueueManager.tsx#L791-L811) renders Start Visit actions for all previously appended entries without checking current doctor/date. A different snapshot is loaded when `effectiveDoctor/effectiveDate` changes, but no `setCalledPatients([])` or keyed retention exists.
- **Reproduction scenario:** doctor-mode manager stays mounted; call synthetic queue entry X in doctor A/day D; switch selected doctor to B or date to D+1; the current queue table now belongs to B/D+1 but the separate called-patients panel still exposes X's name and `onStartVisit(X)` action. The `QueueIntegration.tsx:128–136` doctor-mode wrapper accepts `selectedDoctor` changes without a remount guarantee. The backend receives a queue entry id and applies its own access checks; **do not claim successful cross-doctor mutation without a backend test**.
- **Fail-first:** render doctor-mode `ModernQueueManager`, resolve synthetic `callNextPatientInQueue` for A with entry X; `rerender` with doctor B (and separately a new date), assert X's row/action is absent and clicking cannot invoke `onStartVisit(X)`. Repeat with a pending call-next for A that resolves only after B is selected; the stale response must not append X to B's list. Existing dentist start-visit tests cover same-doctor success/false failure, not selection identity.
- **Suggested repair:** bind each local called entry and pending command response to the canonical selected doctor/date (or clear and invalidate on each identity transition), optionally reconcile displayed called entries against the latest backend queue; preserve backend SSOT and never authorize a cross-specialty action from client state.

### WSQ-FE-001 — P2: reconnect budget is inherited by a different queue subscription

- **Source:** [`useQueueWebSocket.ts:52–75`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useQueueWebSocket.ts#L52-L75) keeps `reconnectAttemptRef` for the hook's entire lifetime. `cleanup()` closes the old socket and timer but does not reset attempts. [`useQueueWebSocket.ts:144–167`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useQueueWebSocket.ts#L144-L167) stops retrying once the counter is 5, while [effect L175–188](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useQueueWebSocket.ts#L175-L188) reuses that counter on doctor/date changes. Only `ws.onopen` resets the budget.
- **Failure precondition:** a previous doctor's WS exhausted five reconnection attempts; without unmounting the component, user selects a different doctor/day. The new socket is attempted once; if that attempt closes before reaching `onopen`, the old `5` prevents every retry on the **new** subscription, leaving it polling-only. No claim of a permanent outage if a new connection succeeds immediately or the hook remounts.
- **Fail-first:** mock `WebSocket` and fake timers, exhaust A's retries (five failed connections), change specialty A→B in one mounted hook, fail the first B socket, assert B has a fresh bounded retry schedule and `onUpdate` uses only B's current subscription. Verify cleanup removes A timers and sockets.
- **Suggested repair:** reset the attempt budget per subscription identity (`specialistId` + `date` and enable transitions), not across unrelated queues; retain bounded backoff within each identity and fallback polling for sustained failures.

### WSQ-FE-002 — P2 candidate: server-initiated normal close permanently disables live refresh

- **Source:** [`useQueueWebSocket.ts:64–72`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useQueueWebSocket.ts#L64-L72) already suppresses `onclose` when *the client* deliberately closes the socket. Independently, [`useQueueWebSocket.ts:144–153`](https://github.com/drsapaev/final/blob/1e7e43dc738400544ae34294f17c439a3499a6c7/frontend/src/hooks/useQueueWebSocket.ts#L144-L153) treats **every** WebSocket close code `1000` as a deliberate/manual close and returns without retrying.
- **Failure precondition:** the **server** sends a normal `1000` close while the doctor's panel stays mounted, e.g. a graceful server-side lifecycle close. This socket is not client-closed, yet the code permanently switches to disconnected/polling-only until remount or subscription change. The reviewed backend does not establish that it routinely sends 1000, so the finding is **conditional** rather than a reported production incident.
- **Fail-first:** manually dispatch `onclose({code:1000})` from an active mock server socket (not a client-triggered cleanup), advance fake timers and assert a bounded reconnect attempt. Conversely, unmount/disable must cause **zero** reconnects even if the mocked close code is not 1000.
- **Suggested repair:** use explicit lifecycle flags / generation identity to distinguish deliberate client cleanup from a remote normal close; don't infer *who initiated* a close from code 1000 alone. Preserve security-policy close handling and the known QR-FE-010 heartbeat fix as separate concerns.

### Checks, existing defenses and evidence limits

- **Confirmed protections:** `QueueTable.tsx` is presentation-only and has no patient-call buttons; existing keyboard-navigation and sticky-header tests cover its accessible table wiring. `api/queue.ts` still delegates call-next selection and mutation to the backend with a selected doctor/day. Backend `QRQueueService.call_next_patient()` uses `OnlineQueueEntry.id` for its returned `patient.id`, which matches the dentist queue-start callback's expected entry id.
- **Non-duplication:** prior QR-FE-010 separately covers lack of `pong` on backend heartbeat. These WSQ findings cover *attempt budget ownership* and *server-initiated normal closure*, not the heartbeat protocol. Prior QMAN-FE-001 covers outdated snapshot on load failure, not the local `calledPatients` cross-selection list.
- **Not performed:** Vitest, WS simulation, browser route/doctor switching, real queue mutation, patient/PHI access, mandatory gate for runtime fixes, merge or deployment. Tests above are proposed, not run. A future queue/runtime patch requires the repository's mandatory agent gate and synthetic negative tests. This document/comment is the only allowed write in #3886.
