# Independent Code Review — group99: Registrar worklist refresh lifecycle

**Date:** 2026-11-16 (Asia/Tashkent). **Read-only source pin:** [`main@b93ea7117e2272d18c19fe1c4825695392c9b550`](https://github.com/drsapaev/final/commit/b93ea7117e2272d18c19fe1c4825695392c9b550). **Audit home:** existing [Draft #4059](https://github.com/drsapaev/final/pull/4059), groups 47–98 retained unchanged. **Scope:** [`frontend/src/pages/registrar/useRegistrarWorklistData.ts`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts) and its [hook tests](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts), with read-only references to [`api/client.ts`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/api/client.ts), [`tokenManager.ts`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/utils/tokenManager.ts), [`RegistrarPanel.tsx`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/RegistrarPanel.tsx), [`queue.ts`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/services/queue.ts), historical registrar audit and [Draft #4097](https://github.com/drsapaev/final/pull/4097). Consulted root `AGENTS.md` and repo `code-security` skill. **No application code changes or tests executed by reviewer.** These are independently source-grounded findings with deterministic test specifications, not alleged production incidents.

## Review outcome

- **2 NEW distinct P2, OPEN, unimplemented:** `REGDATA-FE-001` (critical `queueUpdated` delayed callback can reload obsolete date after date transition), `REGDATA-FE-002` (stale request's 401 handler removes newly installed access token before its own superseded guard).
- **One PRE-EXISTING open P2, source-reconfirmed, no duplicate ID:** `REG-FE-005` (URL `?date` changes while calendar is closed do not trigger a direct reload and date label can diverge).
- **Three previously FIXED-VERIFIED historical entries reconfirmed by source+test presence, NOT reopened or counted as new:** `REG-FE-007` (429 explicit failed/stale load), `REG-FE-020` (superseded request cannot release newest in-flight guard or start cooldown), and `REG-FE-021` (30s timer checks `anyDialogOpenRef.current` on each tick). Existing historical merged-PR provenance remains as recorded; this review did not rerun CI or test suites.
- **Other agent's clinical fix pending:** existing `REG-FE-006` Welcome confirmation gap still present on pinned main. [#4097](https://github.com/drsapaev/final/pull/4097) is a **docs-only Draft handoff**, not evidence of source correction. No fix status changed.

## NEW `REGDATA-FE-001` — P2 / CONFIRMED_SOURCE, RUNTIME_REPRO_PENDING

**Title:** Delayed critical `queueUpdated` refresh survives effect cleanup and can supersede the newly selected calendar day.

**Evidence:**
1. [`useRegistrarWorklistData.ts:493–523`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L493-L523): for `patientCalled`, `visitStarted`, `visitCompleted`, `nextPatientCalled`, `refreshAll`, `entryAdded`, the event listener schedules `setTimeout(... loadAppointments(...), 300/500)` with **no timeout ID retained**. Cleanup removes only the `queueUpdated` listener; it does **not cancel callbacks already scheduled**.
2. [`useRegistrarWorklistData.ts:284–288`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L284-L288) computes `target_date` from the callback's closed-over `showCalendar`, `historyDate`, and `searchParams`; the [callback dependencies at L469](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L469) confirm the callback changes on date transitions.
3. [`useRegistrarWorklistData.ts:533–538`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L533-L538) starts a calendar B reload; [L264–265](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L264-L265) assigns **request sequence when a request starts**, not when its UI date was selected. Hence a delayed **old closure A starting after B** acquires a *newer* request ID and may overwrite B's rows and `loadedDate`.
4. The existing [`useRegistrarWorklistData.test.ts`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts) exercises request A/B arrival ordering and calendar switches, but has **no `queueUpdated` event test**; it cannot catch a *late-starting* request with stale closed-over date. The [historical registrar ledger](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/docs/audits/2026-10-29-registrar-frontend-review-ledger.md) mentioned a related **unnumbered** post-unmount timeout concern. This issue elevates it to a specific new numbered finding because the **old-date-overwrites-new-date ordering** is established from the source. Do not duplicate historical `REG-FE-020` (which guards requests that **started** earlier).

**Deterministic fail-first reproduction for fixing agent (all synthetic):**
- Mount hook with stable dependencies, `showCalendar=true`, `historyDate='2026-11-14'` (day A), flush initial load.
- `window.dispatchEvent(new CustomEvent('queueUpdated', { detail: { action: 'entryAdded', specialty: 'all' } }))` schedules the 500ms A reload.
- Before advancing the timer, rerender with `historyDate='2026-11-15'` (B); permit B's calendar reload to complete with `SYNTHETIC-B` (or keep it deferred).
- Advance fake timers 500ms: **current source** calls `api.get` for **A after B was selected**, and because that invocation now has the highest request sequence, an A response can install A rows/`loadedDate` under B selection.
- Assert no post-switch request targets A; final `appointments`, `loadedDate`, `stale` reflect B. Separate unmount test: dispatch critical event, unmount, advance timers, assert no additional GET or post-unmount side effects.
- Cover `entryAdded` / `refreshAll` 500ms and `visitCompleted` 300ms paths, without real patient fixtures.

**Recommended bounded correction (not implemented):** track pending timer IDs in hook effect and clear them in cleanup; validate current selected date/request generation before starting delayed loads (not merely a guard at response application). Keep backend queue ownership, status policy, and RQ-22 late-response guard intact. Prevent background requests after unmount.

**Severity basis:** P2 workflow integrity — inconsistent date and patient list during rapid update/selection; **not proof** of patient data being mutated on server or authorization bypass.

**State:** `OPEN — SOURCE-OBSERVED / DETERMINISTIC_TEST_PENDING`.

## NEW `REGDATA-FE-002` — P2 / CONFIRMED_SOURCE, RUNTIME_REPRO_PENDING

**Title:** Obsolete HTTP 401 clears live registrar authentication token before verifying whether its request was superseded.

**Evidence:**
1. [`useRegistrarWorklistData.ts:422–432`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L422-L432) enters 401 branch and executes **`sessionStorage.removeItem('auth_token')`** before `if (isSuperseded()) return 'superseded';`. This unconditional side effect therefore also executes for a late HTTP 401 from an obsolete request, including after a newer request was successful.
2. [`tokenManager.ts:16–30`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/utils/tokenManager.ts#L16-L30) confirms `auth_token` is the **live centralized access-token key in `sessionStorage`**. This is not an irrelevant legacy storage location.
3. The canonical [API client's response interceptor at `api/client.ts:474–546`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/api/client.ts#L474-L546) intentionally re-reads `liveToken` and protects a **newly installed session** when the failed request's `failedToken` differs. In the **rejected** 401 case, the interceptor returns the error to callers; this registrar-specific catch can then invalidate the protected new access token, violating the shared contract.
4. [`useRegistrarWorklistData.test.ts`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts) has late-response/429 tests, but **no synthetic 401 test** that simulates token rotation/session replacement while an old queue request remains pending.

**Deterministic fail-first reproduction for fixing agent (synthetic only):**
- Set `sessionStorage.auth_token='SYNTHETIC-TOKEN-A'`; start deferred API request A under that token.
- Rotate to `SYNTHETIC-TOKEN-B'` (or create new access-only session), start and resolve newer request B, verifying B's rows.
- Reject old A as `{ response: { status: 401 } }`; **current hook removes token B** before it notices A has been superseded. Test `tokenManager.getAccessToken()` remains B after A's rejection and `loadedDate` remains B.
- Also test **same-request, truly invalid session** (401 for current request) retains correct authoritative auth-store/route response; do not merely suppress every 401. Test with actual Axios interceptor semantics as an integration contract after the isolated hook test.
- Check effects after new principal/login transition, whether patient/registrar session replacement paths can be affected, and browser cross-tab/session storage semantics. Do not assert a confirmed production incident or patient PHI exposure.

**Recommended bounded correction (not implemented):** avoid direct `sessionStorage` write in this feature hook, defer auth invalidation to centralized token/session manager and its current-token identity checks. At minimum check `isSuperseded()` **before any auth side effect** and never clear a token which is not the token of the failed request. No weakening of actual dead-session 401 behavior.

**Severity basis:** P2 availability/security-consistency risk — an older request may break a valid/new session and leave auth state inconsistent. **Not proof** of unauthorized access; the backend still validates JWTs.

**State:** `OPEN — SOURCE-OBSERVED / DETERMINISTIC_TEST_PENDING`.

## Existing `REG-FE-005` — P2 / still SOURCE-OBSERVED OPEN (no new ID)

[`useRegistrarWorklistData.ts:284–288`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L284-L288) selects `?date` when calendar is closed. While `searchParams` is a dependency of `loadAppointments`, [`useRegistrarWorklistData.ts:483–490`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L483-L490) guards the initial-load effect with `initialLoadRef.current` and therefore does **not** request on subsequent callback changes. [Calendar-date effect L532–539](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L532-L539) only acts when `showCalendar` is true. Accordingly a changed `?date` with calendar closed does not directly load that day; other refresh triggers may eventually do so. Existing `REG-FE-005` correctly documents this; do **not** claim it was fixed just because the load callback depends on `searchParams`. User-facing date-title semantics also need the known separate check. Existing audit ID stays open, no new checklist row.

## Re-verified historical FIXED-VERIFIED statuses — NO duplicate IDs, NO state change

| Existing finding | Evidence on current pinned main | Review verdict |
|---|---|---|
| `REG-FE-007` (429 fails to mark load as failure) | [`useRegistrarWorklistData.ts:401–419`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L401-L419) now dispatches `LOAD_FAILED` for an authoritative 429 and 60s cooldown; [tests L596–627](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L596-L627) cover primary and refresh stale states | **CODE+TEST PRESENT — historic FIXED-VERIFIED remains** |
| `REG-FE-020` (old response releases newest in-flight guard/installs 429 cooldown) | [`useRegistrarWorklistData.ts:401–409, 453–464`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L401-L464) uses `isSuperseded()` before cooldown/finally ownership; [tests L629–726](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L629-L726) cover A/B pending and superseded 429 | **CODE+TEST PRESENT — historic FIXED-VERIFIED remains** |
| `REG-FE-021` (timer's dialog-open flag stale) | [`useRegistrarWorklistData.ts:560–586`](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/useRegistrarWorklistData.ts#L560-L586) checks `anyDialogOpenRef.current` on each 30s tick; [tests L729–767](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/frontend/src/pages/registrar/__tests__/useRegistrarWorklistData.test.ts#L729-L767) cover dialog open/close | **CODE+TEST PRESENT — historic FIXED-VERIFIED remains** |

These prior statuses are quoted from the canonical [historical registrar ledger](https://github.com/drsapaev/final/blob/b93ea7117e2272d18c19fe1c4825695392c9b550/docs/audits/2026-10-29-registrar-frontend-review-ledger.md), which links the previously merged fix PRs and main-CI evidence. **This group99 review did not execute the tests or retrieve new CI run results for those old commits.**

## Do-not-fix-claims / boundary

- `REG-FE-006` remains source-visible on pinned main; Draft [#4097](https://github.com/drsapaev/final/pull/4097) is **only a reference patch + fixing-agent handoff**. Its green docs CI is not confirmation of applied Welcome confirmation logic.
- These two NEW issues do not duplicate the old request response ordering `REG-FE-020` or the URL date `REG-FE-005`. The distinguishing mechanisms are respectively **stale callback starting a brand-new request after date change**, and **auth token cleared before the superseded guard**, not ordinary old responses.
- No code/patch/test/branch fix, agent gate, CI mutation, merge, deploy, live user/session or production data access performed. Remediation of auth/queue workflow is another agent's task. Never mark issue items checked without independently verified source merge.
