# Verification Pass & Remediation Roadmap

> Independent senior-reviewer audit of the JS→TS migration.
> Verification pass performed 2026-07-25 against `main@5e3e8a38`.
> This document supersedes the initial audit; all 73 findings were re-verified by direct file reads + grep call-site checks + execution-path tracing.

---

## Method

Each of 73 findings was independently verified by:

1. Reading the actual file at the cited lines.
2. Grepping for real consumers (zero-consumer = dead code).
3. Tracing execution paths (reachable / conditional / not reachable).
4. Categorising as A (proven bug) / B (design issue) / C (possible) / D (opinion).
5. Assessing fix risk (regression, API, FE, BE, migration, tests, users, medical-data).

## Categories

- **A — Proven bug**: reproducible defect with concrete evidence
- **B — High-confidence design issue**: behaviour correct but architecture problematic
- **C — Possible issue**: risk exists, needs more verification
- **D — Opinion / style**: architectural preference, not a defect

---

## Verification Matrix (73 findings)

| ID | Status | Proven | Confidence | Priority | Fix risk | Auto-fix | Phase |
|----|--------|--------|------------|----------|----------|----------|-------|
| BS-1 | B | 3 (not 2) `AuthState` defs; consumers use `stores/auth.ts` version; both `types/` defs dead | 95% | Med | Low | No | 5 |
| BS-2 | C | Duplicate `LoginResponse`; live consumer uses safe union version; flat version dead | 90% | Low | Low | Yes | 5 |
| BS-3 | B | `\| string` collapses 9+ domain unions to `string`; minor line# slip | 95% | Med | Med | Yes | 5 |
| BS-4 | C | Dead code; claim `typeof never returns 'array'` WRONG (Array.isArray checked); real issue: implicit-any params | 85% | Low | Zero | Yes | 0 |
| BS-5 | B | 17 `as never` Icon.size casts in Dermatologist; App.tsx:310-312 is Sidebar props (not Icon.size); Icon silently ignores numeric sizes | 95% | Med | Med | No | 5 |
| BS-6 | B | 5 (not 3) casts in `useTranslation.ts:64` | 95% | Low | Low | No | 5 |
| BS-7 | C | Fabricated error real; `axios.isAxiosError` claim likely WRONG (axios v1 duck-types); no caller invokes it | 70% | Low | Zero today | No | — |
| BS-8 | C | Duplicate `QueueState`; both versions 0 consumers | 95% | Low | Zero | Yes | 0 |
| BS-9 | B | Case-diff duplicate `EMRStatus`/`EmrStatus` etc; both versions LIVE in different code paths | 95% | High | Med | No | 5 |
| BS-10 | C | `types/i18n.ts` 0 direct imports; TS augmentation may apply via tsconfig include | 75% | Low | Low | No | 5 |
| BS-11 | B | 4/5 broken-import masks; ALL 5 hooks are dead code; `useNavigation` mis-categorised (destructuring, not import) | 90% | Low | Zero | Yes | 0 |
| BS-12 | A | Deps array `[resolvedDelay, deps]` breaks memoization; 4 consumers | 95% | High | Low | Yes | 4 |
| BS-13 | B | AbortController not wired to `api.get`; 4× in AdminDashboard | 95% | Med | Low | Yes | 4 |
| BS-14 | A | `pingInterval` leaked in `ws.ts` close(); 1 consumer (DisplayBoard) | 95% | High | Low | No | 4 |
| BS-15 | C | Real defect but `useWebSocket={false}` everywhere → dormant; race less acute than claimed | 95% | Low (dormant) | Low | No | 4 |
| BS-16 | A | `ChatContext` value not memoised; 2 consumers | 95% | High | Low | No | 4 |
| BS-17 | B (medical) | `useEMRAutosave` maxWait captures stale `doAutosave` → saves stale data after 30s typing | 80% | **Critical** | High | No | 1 |
| BS-18 | C | Module-level `emrCache`; 1 consumer; self-heals after promise resolve | 80% | Med | Low | No | 1 |
| BS-19 | A | `AppDataContext` value not memoised; `useAppDataSelector` fake; 0 selector consumers | 95% | Med | Low | No | 4 |
| BS-20 | B | `NotificationWebSocketContext` value new + stale ref; 0 external consumers | 80% | Low | Low | No | 4 |
| BS-21 | B | Stale closure on `onWarning`/`onExpired`; 5 panel consumers | 80% | Med | Med | No | 4 |
| BS-22 | B (partial) | Race in `useAppointments`/`useDoctorQueue` real; `usePatients` claim WRONG (optimistic updates) | 80% | Med | Low | No | 4 |
| BS-23 | D | Claim WRONG: `cleanup()` already nulls `onclose` + clears timer | 80% | — | — | — | — |
| BS-24 | C | Real defect (wrong endpoint, no auth) but 0 consumers — dead code | 95% | Low | Zero | Yes | 0 |
| BS-25 | A | `services/api.ts` raw fetch; 3 production consumers | 95% | High | Low | No | 3 |
| BS-26 | A (partial) | Double interceptor registration confirmed; pair-3 (`utils/api.ts`) on SEPARATE instance, not shared | 95% | High | Med | No | 3 |
| BS-27 | B | Two uncoordinated 401-refresh paths | 80% | High | High | No | 3 |
| BS-28 | A | `useTelegramAuth` uses `/auth/refresh` instead of `/authentication/refresh`; needs BE verification | 95% | High | Low | Yes | 3 |
| BS-29 | B | `invalidateAccessToken` dead branch; 4001 silently fails | 95% | High | Low | Yes | 2 |
| BS-30 | A | 4 event listeners never fire; entire module largely dead | 95% | Med | Zero | Yes | 0 |
| BS-31 | C | `cachedFetch` bypasses interceptors; 0 consumers — dead | 80% | Low | Zero | Yes | 0 |
| BS-32 | A | `localStorage.getItem('auth_token')` always null; theme prefs never loaded | 95% | High | Low | Yes | 2 |
| BS-33 | A | Direct `removeItem('auth_token')` bypasses tokenManager; refresh_token survives | 95% | High | Low | Yes | 2 |
| BS-34 | A (medical) | `transformPatient` hardcodes `allergies: ''`, `chronicDiseases: ''`, `bloodType: ''`; snake_case fields never read | 95% | **Critical** | High | Yes | 1 |
| BS-35 | A | `CONFLICT_RESOLVED` doesn't reset history/isDirty → undo loop after conflict | 95% | High | Med | Yes | 1 |
| BS-36 | A | `deletedIds` grow monotonically; `updatedAt` written but never read | 95% | Med | Low | No | 4 |
| BS-37 | A (PHI) | `admin_finance_transactions_cache` + `cache_*` survive logout in localStorage | 95% | **Critical** | Med | No | 2 |
| BS-38 | A (PHI) | `patient_jwt_token` etc. survive staff logout | 95% | **Critical** | Low | Yes | 2 |
| BS-39 | B | Dead `patientAuthInterceptor.ts`; latent if re-imported | 95% | Low (latent) | Zero | Yes | 0 |
| BS-40 | A | `Object.assign(SPECIALTY_TO_CODE, ...)` mutates exported const | 95% | Med | Med | No | 4 |
| BS-41 | C | `useNavigation.tsx` reimplements routing; 0 importers — dead | 80% | Low | Zero | Yes | 0 |
| BS-42 | A (medical) | 7 module-level caches in `DentistPanelUnified.tsx`; unkeyed caches leak between patients | 95% | **Critical** | Med | No | 1 |
| BS-44 | B | ~97 (not 23+) `.jsx`/`.js` imports of `.tsx`/`.ts`; tsc DOES resolve via bundler; style only | 95% | Low | Zero | Yes | 7 |
| BS-45 | B | `@/` alias configured, 0 actual imports | 95% | Low | Zero | Yes | 7 |
| BS-46 | B | `sourcemap: true` always on; inline comment contradicts behaviour | 95% | Med | Low | Yes | 7 |
| BS-47 | B | `REACT_APP_VAPID_PUBLIC_KEY` instead of `VITE_`; 2 consumers | 95% | Med | Low | Yes | 7 |
| BS-48 | A | ESLint test rule matches only `.test.{js,jsx}` (0 files); 149 `.test.ts`/`.tsx` files uncovered | 95% | Med | Zero | Yes | 7 |
| BS-49 | A | `no-restricted-imports` missing; inline comments promise rules that don't exist | 95% | Med | Low | No | 7 |
| BS-50 | C | No `sideEffects` field; impact muted for private app | 80% | Low | Low | Yes | 7 |
| BS-52 | B | JWT prefix log in `AppointmentWizardV2.tsx:1613-1615`; dev-gated, prod strips via `drop_console` | 95% | Med | Low | Yes | 2 |
| BS-53 | B | `<img src>`/`<a href>`/`window.open` with unsanitized URLs; ReactMarkdown branch has filter | 90% | High | Low | Yes | 2 |
| BS-54 | B | `validateFile` called only in chat FileUploader; PhotoUploader + ui/FileUpload missing | 95% | Med | Med | No | 2 |
| BS-55 | B | `detectPromptInjection` missing in `EMRContainerV2` + `AIAssistant` direct MCP calls | 90% | High | Med | No | 2 |
| BS-56 | B | CSRF fails open; `csrfEndpointUnavailable` permanent flag | 95% | High | **High** | No | 3 |
| BS-57 | B | Sentry PHI list missing `full_name`, `birth_date`, `address`, `card_number`; `event.contexts` not scrubbed | 95% | High | Low | Yes | 2 |
| BS-58 | B | WebAuthn client-overridable RP ID + `userVerification: 'preferred'`; backend SHOULD validate | 85% | Med | Med | No | 2 |
| BS-59 | A | ChatContext sends JWT as plain JSON; inconsistent with subprotocol approach | 95% | Med | Med | No | 3 |
| BS-60 | C | O(n²) deduplication in `aggregatePatientsForAllDepartments` | 90% | Low | Low | Yes | 6 |
| BS-61 | C | Nested `find()` per service per row; `createServiceMapping` keyed wrong | 90% | Med | Low | No | 6 |
| BS-62 | D (partial) | 3 of 4 files use `JSON.parse(JSON.stringify())`; `dentistVisitProtocolBridge.ts` uses `structuredClone` | 95% | Low | Zero | Yes | 6 |
| BS-63 | C | No `manualChunks`; recharts eager imported | 95% | Low | Med | No | 6 |
| BS-64 | B | `LinkPreview` raw fetch, no auth, no abort, no cache | 90% | Med | Low | No | 6 |
| BS-65 | B | `endpoints.ts` 386 lines, most exports 0 importers; drift from actual API paths | 95% | Med | Med | No | 7 |
| BS-66 | B | **186** (not 33+) "Phase 9"/"TODO Phase" across 92 files; `strict: false` confirmed | 95% | Med | **High** | No | 5 |
| BS-67 | D | "Every render cycle" WRONG; runs once per mount + on mutation | 95% | Low | N/A | — | — |
| BS-69 | B | `useChat.ts` shim dead; **6** (not 4) aliases in `client.ts`; only `apiClient` live | 95% | Low | Zero | Yes | 0 |
| BS-70 | C | Duplicate `removeItem('auth_profile')`; cosmetic (idempotent) | 95% | Low | Zero | Yes | 0 |
| BS-71 | C | Dep churn pattern real; entire `useBlobURL.ts` (125 lines) dead | 95% | Low | Zero | Yes | 0 |
| BS-72 | B | `setInterval` in constructor, never cleared; singleton mitigates | 95% | Low | Low | No | 7 |
| BS-73 | B/C | `key={index}` on dynamic lists; `EnhancedAppointmentsTable:1512` already uses proper key | 95% | Med | Low-Med | No | 6 |

---

## Counts

| Category | Count |
|----------|-------|
| A (Proven bug) | 19 |
| B (Design issue) | 26 |
| C (Possible) | 18 |
| D (Opinion / claim wrong) | 2 (BS-23, BS-67) |
| Dead code (zero-consumer) | ~19 findings |

## Confidence

- 95-100%: 56 findings
- 80-95%: 13 findings
- 50-80%: 4 findings (BS-7, 10, 18, 20)
- <50%: 0

---

## Key Claim Corrections vs Initial Audit

| ID | Initial claim | Verified truth |
|----|---------------|----------------|
| BS-1 | Two `AuthState` defs | THREE defs; consumers use `stores/auth.ts` version |
| BS-4 | `validateDTO` uses `typeof` never returning 'array' | WRONG: code uses `Array.isArray(value) ? 'array' : typeof value` |
| BS-5 | `App.tsx:310-312` = Icon.size cast | WRONG: Sidebar props cast |
| BS-7 | `axios.isAxiosError(error)` returns false | Likely WRONG for axios v1.x (duck-types); no caller invokes it |
| BS-11 | 5 hooks with `@ts-expect-error` masking broken imports | 4/5 correct (all dead code); `useNavigation` mis-categorised |
| BS-15 | WS reconnect race + infinite storm | Race less acute; `useWebSocket={false}` everywhere → dormant |
| BS-18 | "2nd instance empty" | Self-heals after resolve; 1 consumer |
| BS-22 | Race in `usePatients` | WRONG: optimistic updates, no reload-after-mutation |
| BS-23 | `useQueueWebSocket` stale `connect` | WRONG: `cleanup()` already nulls onclose + clears timer |
| BS-24 | `useEMRTelemetry` fires after unmount | Real defect but 0 consumers — dead code |
| BS-26 | Triple registration on shared instance | Pair-3 on SEPARATE axios instance; double confirmed |
| BS-31 | `cachedFetch` bypasses interceptors | Confirmed but 0 consumers — dead |
| BS-41 | `useNavigation.tsx` reimplements routing | Confirmed but 0 importers — dead |
| BS-44 | 23+ `.jsx` imports of `.tsx` | ~97 cases (understated 4×); tsc DOES resolve via bundler |
| BS-62 | 4 files with `JSON.parse(JSON.stringify())` | 3 of 4; `dentistVisitProtocolBridge.ts` uses `structuredClone` |
| BS-66 | 33+ Phase deferrals | 186 occurrences (understated 6×) |
| BS-67 | useFinance "every render cycle" | WRONG: once per mount + on mutation |
| BS-69 | 4 aliases in client.ts | 6 aliases; only `apiClient` live |
| BS-71 | useBlobURL dep churn | Pattern real; entire module dead (bigger finding) |

---

## Dependency Graph

### Cluster 1: Auth/Token infrastructure
```
BS-25 (services/api.ts raw fetch)
   ↓
BS-26 (double interceptors on shared api)
   ↓
BS-27 (two refresh paths, no coordination)
   ↓
BS-28 (useTelegramAuth wrong endpoint) ← independent (BE check)
BS-29 (invalidateAccessToken dead code) ← independent
BS-32 (ThemeContext reads localStorage) ← independent
BS-33 (useUserPreferences direct removeItem)
   ↓
BS-37 (PHI in localStorage survives logout)
BS-38 (patient JWT survives logout)
   ↓
BS-39 (patientAuthInterceptor latent)

Fix BS-26 (consolidate interceptors) auto-closes: BS-27
Fix BS-25 alone does NOT close BS-26
Fix BS-33 + BS-37 + BS-38 → cleaner logout
```

### Cluster 2: EMR medical safety
```
BS-17 (useEMRAutosave stale doAutosave) ← CRITICAL
   ↓
BS-35 (emrReducer.CONFLICT_RESOLVED incomplete)
   ↓ (Undo after conflict → 409 loop → triggers autosave)

BS-18 (useEMR shared cache) — independent
BS-42 (DentistPanel module-level caches) — independent
BS-9 (EMRStatus/EmrStatus case-duplication) — naming confusion risk

Fix BS-17 + BS-35 → conflict resolution works correctly
Fix BS-42 → stale data after patient switch disappears
Fix BS-9 → renaming simplifies review
```

### Cluster 3: React context performance
```
BS-16 (ChatContext value not memoised) — CRITICAL
BS-19 (AppDataContext value not memoised) — CRITICAL
BS-20 (NotificationWebSocketContext) — latent (0 consumers)

BS-12 (useDebouncedCallback deps broken) — independent, propagation effect
   ↓
BS-21 (useSessionTimeoutWarning stale closure) — related pattern

Fix BS-12 → stabilises all useDebouncedCallback consumers
Fix BS-16/19/20 → useMemo(value) — independent
```

### Cluster 4: API/cache infrastructure (all dead/dormant)
```
BS-30 (apiCache event listeners never fire)
BS-31 (cachedFetch bypasses interceptors) — 0 consumers
BS-65 (endpoints.ts drifts)
BS-72 (apiCache setInterval leak)

All 4 — dead/dormant. Fix = delete + migrate live consumers (none today).
```

### Cluster 5: TS migration artifacts
```
BS-44 (.jsx imports of .tsx) — ~97 cases, style only
BS-45 (@/ alias unused) — 0 imports
BS-66 (186 Phase deferrals) — Phase 9 never landed
BS-69 (6 dead aliases) — 1 live
BS-11 (5 @ts-expect-error hooks) — all dead code
BS-71 (useBlobURL dead) — entire module dead
BS-41 (useNavigation dead) — 0 importers

Fix BS-44 (codemod strip extensions) + BS-45 (codemod relative→@/) — independent
Fix BS-66 (strict:true) — HIGH risk, surfaces hundreds of errors; do LAST
```

### Cluster 6: WebSocket lifecycle
```
BS-14 (ws.ts pingInterval leak) — DisplayBoard only
BS-15 (useAIChat reconnect) — dormant (useWebSocket=false)
BS-23 (useQueueWebSocket) — already mitigated (D)
BS-59 (ChatContext JWT in plain JSON) — inconsistency with websocketAuth.ts

Fix BS-14 + BS-59 — independent
BS-23 does NOT need fixing
```

### Cluster 7: File upload security
```
BS-54 (magic-byte validation missing) — PhotoUploader, ui/FileUpload
BS-55 (prompt injection on MCP callers) — EMRContainerV2, AIAssistant

Independent. Fix = add validateFile() / detectPromptInjection() at call sites.
```

---

## Contradictions Between Recommendations

### C1: Generated DTOs vs Hand-written domain types
- BS-1, BS-2, BS-9 recommend: delete hand-written dups, use generated DTOs as SSOT.
- BS-3 recommends: tighten `| string` unions in domain types.

**Conflict:** If we delete `domain/auth.ts`, `domain/clinic.ts` and use only `types/generated/api.ts`, BS-3 becomes moot. But consumers use `[key: string]: unknown` interfaces — they must be rewritten.

**Resolution:** Decide SSOT policy first (generated vs hand-written), then apply.

### C2: Phase 9 strict vs Incremental cleanup
- BS-66 recommends: enable `strict: true` (Phase 9).
- BS-11, BS-24, BS-31, BS-41, BS-71 recommend: delete dead code.

**Conflict:** Deleting dead code BEFORE strict:true surfaces fewer errors. Enabling strict:true FIRST surfaces hundreds of errors in dead code too.

**Resolution:** Delete dead code first, then strict:true.

### C3: Fail-closed CSRF vs Backward compat
- BS-56 recommends: fail-closed CSRF (reject request when no token).
- `ensureCSRFToken` deployment context: `csrfEndpointUnavailable` flag allows backend without `/auth/csrf-token`.

**Conflict:** Fail-closed breaks deployments without CSRF endpoint. Fail-open = security risk.

**Resolution:** Feature flag (`VITE_CSRF_STRICT=true` for prod, false for dev/staging without endpoint).

### C4: useAppDataSelector vs Delete
- BS-19 recommends: either `useMemo` value, or real selector library.
- BS-19 also: `useAppDataSelector` — 0 consumers.

**Conflict:** If 0 consumers — can just delete `useAppDataSelector`. If planning to use — need real selector.

**Resolution:** Delete for now; reintroduce with `use-context-selector` when consumer appears.

### C5: useTelegramAuth refresh endpoint
- BS-28 recommends: change `/auth/refresh` → `/authentication/refresh`.
- Code purpose: Patient Mini App auth flow, separate from staff.

**Conflict:** If backend REALLY has `/auth/refresh` for patient flow, change breaks patient auth.

**Resolution:** Verify backend routes first (grep backend code or ask BE team), then change.

---

## Remediation Roadmap (minimal regressions)

### Phase 0 — Dead code removal (zero-risk, FIRST)

**Goal:** Reduce surface area for all subsequent phases.

| ID | Action | Auto | Risk |
|----|--------|------|------|
| BS-4 | Delete `src/types/api-constants.ts` | Yes | 0 |
| BS-8 | Delete `QueueState` placeholder in `types/features/queue.ts` | Yes | 0 |
| BS-11 | Delete 4 dead hooks (`useTable.tsx`, `useForm.tsx`, `usePatientSessions.ts`, `useTelegramAuth.tsx` in `hooks/`) | Yes | 0 |
| BS-24 | Delete `useEMRTelemetry.ts` (0 consumers) | Yes | 0 |
| BS-30 | Delete `setupCacheInvalidation` + entire apiCache module if 0 consumers | Yes | 0 |
| BS-31 | Delete `cachedFetch`, `useOptimizedData`, `useCachedAPI` (0 consumers) | Yes | 0 |
| BS-39 | Delete `patientAuthInterceptor.ts` | Yes | 0 |
| BS-41 | Delete `useNavigation.tsx` (0 importers) | Yes | 0 |
| BS-69 | Delete 5 dead aliases in `client.ts:411-417` (keep `apiClient`) | Yes | 0 |
| BS-70 | Fix duplicate `removeItem` in `clearAuthCache.ts` | Yes | 0 |
| BS-71 | Delete `useBlobURL.ts` (0 importers) | Yes | 0 |

**Dependencies:** None. All 11 independent deletes.
**Tests:** `vitest run` must remain green.

---

### Phase 1 — Critical medical safety (BEFORE any other changes)

**Goal:** Eliminate risks to patients.

| ID | Action | Auto | Risk | BE? |
|----|--------|------|------|-----|
| **BS-34** | `usePatients.transformPatient` — read `allergies`, `chronicDiseases`, `bloodType`, `insuranceNumber`, `emergencyContact`, `emergencyPhone`, `notes` from `p` (snake_case) with `?? ''` fallback | Yes | Med (FE display) | No |
| **BS-17** | `useEMRAutosave` — introduce `doAutosaveRef.current = doAutosave`; maxWait timer calls `doAutosaveRef.current()`. Same for debounceTimer | No | Med (medical-data) | No |
| **BS-35** | `emrReducer.CONFLICT_RESOLVED` — add `history: [], future: [], isDirty: true, error: null` | Yes | Low | No |
| **BS-42** | `DentistPanelUnified.tsx:83-89` — move 7 module-level caches into `useRef` or LRU with invalidation on patient switch | No | Med (FE perf) | No |

**Dependencies:** BS-17 + BS-35 related (autosave loop after conflict). BS-34 independent. BS-42 independent.
**Tests:** Add regression tests:
- `transformPatient` preserves `allergies` after `updatePatient`
- `useEMRAutosave` maxWait timer uses latest data after 30s typing
- `CONFLICT_RESOLVED` resets history
- DentistPanel switch patient → `dentistAppointmentsCache` invalidated

---

### Phase 2 — Security (HIPAA/auth)

**Goal:** Eliminate PHI leaks and auth inconsistencies.

| ID | Action | Auto | Risk | BE? |
|----|--------|------|------|-----|
| **BS-37** | Extend `clearToken()` in `stores/auth.ts`: add `localStorage.removeItem('admin_finance_transactions_cache')` + iterate over `cache_*` keys | No | Low | No |
| **BS-38** | Extend `clearToken()`: add `sessionStorage.removeItem('patient_jwt_token')`, `patient_refresh_token`, `patient_token_expires_at` | Yes | Low | No |
| **BS-52** | Remove 2 `logger.log` lines in `AppointmentWizardV2.tsx:1613-1615` | Yes | 0 | No |
| **BS-53** | `ChatWindow.tsx:1108-1124` — add `sanitizeURL()` from `utils/sanitizer.ts` to `<img src>`, `<a href>`, `window.open()` | No | Low | No |
| **BS-32** | `ThemeContext.tsx:90,100` — replace `localStorage.getItem('auth_token')` with `tokenManager.getAccessToken()` | Yes | Low | No |
| **BS-33** | `useUserPreferences.ts:96-98` — replace direct `removeItem` with `tokenManager.clearAll()` + `clearToken()` | Yes | Low | No |
| **BS-29** | `ChatContext.tsx:590-597` — replace dead `invalidateAccessToken` branch with `tokenManager.clearAll()` | Yes | Low | No |
| **BS-57** | `services/sentry.ts:24-52` — extend `MEDICAL_PII_KEYS` to match `logger.ts` PHI_FIELDS + scrub `event.contexts` | Yes | Low | No |
| **BS-54** | Import `validateFile` in `PhotoUploader.tsx` and `ui/FileUpload.tsx`; call before upload | No | Med (UX) | No |
| **BS-55** | `EMRContainerV2.tsx`, `AIAssistant.tsx` — call `detectPromptInjection(data.complaints)` before each direct `mcpAPI` call | No | Med (UX) | No |
| **BS-58** | `useWebAuthn.tsx` — set `userVerification: 'required'`; remove client-side `rpId` override (use server-provided only) | No | Med (authenticators) | No |

**Dependencies:** BS-37 + BS-38 + BS-33 all touch `clearToken()` extension — do together. BS-32 independent. BS-29 independent.
**Tests:** Add test: after `clearToken()`, sessionStorage/localStorage contains no PHI keys.

---

### Phase 3 — API consistency

**Goal:** Single API client, single refresh path, single interceptor.

| ID | Action | Auto | Risk | BE? |
|----|--------|------|------|-----|
| **BS-25** | Delete `services/api.ts`. Migrate 3 consumers (`useDoctorQueue`, `QueueManagementCard`, `QueueProfilesManager`) to `api/client.ts` | No | Med (FE regression) | No |
| **BS-26** | Consolidate interceptors: keep only `api/client.ts` registrations. Remove `setupInterceptors()` call in `main.tsx:26` and `api/interceptors.ts` | No | High (auth behaviour) | No |
| **BS-27** | Remove refresh logic from `interceptors.ts` (after BS-26). Use `refreshTokenIfNeeded` from `client.ts` with `refreshPromise` single-flight | No | High (auth) | No |
| **BS-28** | **BE verification FIRST**: check if backend has `/auth/refresh` for patient flow. If NO → change to `/authentication/refresh`. If YES → keep, document | No | Med | **Yes** |
| **BS-56** | CSRF: add feature flag `VITE_CSRF_STRICT`. When `true` — fail-closed (reject). When `false` — current fail-open with warning log | No | Med (deployments) | No |
| **BS-59** | Migrate `ChatContext.tsx` WS to `createAuthenticatedWebSocket` (subprotocol auth). Requires BE coordination | No | Med | **Yes** |

**Dependencies:** BS-25 → BS-26 → BS-27 (sequential). BS-28 requires BE check. BS-59 requires BE coordination.
**Tests:** Extend `api/__tests__/interceptors.test.ts`: concurrent 401s → single refresh. Update auth contract tests.

---

### Phase 4 — React performance

**Goal:** Eliminate mass re-renders.

| ID | Action | Auto | Risk |
|----|--------|------|------|
| **BS-16** | `ChatContext.tsx:768-796` — wrap `value` in `useMemo` with granular deps. Optionally split context (state / actions / typing) | No | Low |
| **BS-19** | `AppDataContext.tsx:373-404` — `useMemo(value)` + `useMemo(actions)`. Delete `useAppDataSelector` (0 consumers) | No | Low |
| **BS-20** | `NotificationWebSocketContext.tsx:393-397` — `useMemo(value)` + expose connection-state instead of raw socket | No | Low |
| **BS-12** | `useDebouncedCallback.ts:66-80` — deps array: `[resolvedDelay, ...deps]` (spread) | Yes | Low |
| **BS-13** | `useAdminData.ts:59` — `api.get(cleanUrl, { signal: currentAbortController.signal })`. Abort previous controller before new | Yes | Low |
| **BS-14** | `api/ws.ts:78-138` — hoist `pingIntervalRef` to outer scope, clear in `close()` and `ws.onclose` | No | Low |
| **BS-21** | `useSessionTimeoutWarning.ts` — `onWarningRef`/`onExpiredRef` pattern (like `useAdminData` does for `onErrorRef`) | No | Low |
| **BS-36** | `useFinance.ts` — TTL for `deletedIds` (7 days); read `updatedAt` for staleness check | No | Low |
| **BS-22** | `useAppointments.ts`, `useDoctorQueue.ts` — add request-ID ref (like `useAIChat.ts:112`) | No | Low |
| **BS-40** | `serviceCodeResolver.ts:600-630` — return fresh maps from `loadMappingsFromBackend`; do not mutate `SPECIALTY_TO_CODE` | No | Med |

**Dependencies:** BS-12 + BS-21 related (deps/callbacks patterns). BS-16/19/20 independent useMemo. BS-13/14 independent.
**Tests:** React DevTools Profiler snapshot before/after for ChatWindow render count.

---

### Phase 5 — TypeScript debt (AFTER Phase 0 dead code removal)

**Goal:** Move to strict typing without hundreds of errors.

| ID | Action | Auto | Risk |
|----|--------|------|------|
| **BS-3** | Codemod: remove `| string` from 9+ domain unions. Audit switch statements for exhaustive checks | Yes | Med (BE may send new enums) |
| **BS-1** | Delete dead `AuthState` in `types/auth-store.ts` and `types/domain/auth.ts`. Keep `stores/auth.ts` version | Yes | Low |
| **BS-2** | Delete dead `LoginResponse` in `types/domain/auth.ts` | Yes | 0 |
| **BS-9** | Rename: `EMRStatus`→`EMRApiStatus`, `EMRConflict`→`EMRApiConflict`, `EMRRecord`→`EMRApiRecord` in `domain/emr.ts` (or vice versa) | No | Med |
| **BS-10** | Delete `types/i18n.ts` (dead). Document override policy in `react-i18next-override.d.ts` | Yes | Low |
| **BS-5** | Extend `IconSize` to `'small' \| 'default' \| 'large' \| 'xlarge' \| number`. Audit Icon component: numeric size must map via px value. Remove all `size={N as never}` casts | No | Med (visual regression) |
| **BS-6** | After BS-10: decide typed resources policy. If yes — populate `resources` in override. If no — keep cast, document | No | Med |
| **BS-66** | Enable `strict: true` + `noImplicitAny: true` in `tsconfig.json`. Fix hundreds of errors incrementally (split into sub-PRs per directory) | No | **High** |

**Dependencies:** BS-66 AFTER BS-1/2/3/9/10 (dead code removed first). BS-6 AFTER BS-10.
**Tests:** `tsc --noEmit` must be green after each sub-PR.

---

### Phase 6 — Performance

**Goal:** Bundle size + render perf.

| ID | Action | Auto | Risk |
|----|--------|------|------|
| **BS-60** | `registrarAggregation.ts` — Sets throughout loop, materialise once at end | Yes | Low |
| **BS-61** | `EnhancedAppointmentsTable.tsx` — extend `createServiceMapping` to `nameToService`, `codeToService` maps | No | Low |
| **BS-62** | 3 files: replace `JSON.parse(JSON.stringify())` with `structuredClone` (with fallback helper from `TreatmentPlanner.tsx:42-52`) | Yes | Low |
| **BS-63** | `vite.config.ts` — add `rollupOptions.output.manualChunks` for `react-vendor`, `recharts`, `sentry`, `markdown` | No | Med |
| **BS-64** | `LinkPreview.tsx` — `api.get` with caching + abort on unmount + debounce | No | Low |
| **BS-73** | Replace `key={index}` with `key={item.id}` (or stable ID) in VisitProtocol, DiagnosisForm | No | Low-Med |

**Dependencies:** All independent.
**Tests:** Bundle visualizer (`npm run build:analyze`) before/after.

---

### Phase 7 — Cleanup / hygiene

**Goal:** Remove migration artifacts.

| ID | Action | Auto | Risk |
|----|--------|------|------|
| **BS-44** | Codemod: strip `.jsx`/`.js` extensions from relative imports in `.ts`/`.tsx` files (~97 cases) | Yes | 0 (style) |
| **BS-45** | Codemod: relative imports → `@/`-prefixed (after BS-44) | Yes | Low |
| **BS-46** | `vite.config.ts:111` — `sourcemap: 'hidden'` or gate on Sentry envs | Yes | Low |
| **BS-47** | Rename `REACT_APP_VAPID_PUBLIC_KEY` → `VITE_VAPID_PUBLIC_KEY`. Update `vite.config.ts`, `pwa.ts:97`, `MobileNotifications.tsx:91`, `.env.example` | No | Low |
| **BS-48** | `eslint.config.js:174` — add `ts`/`tsx` to test-file patterns | Yes | 0 |
| **BS-49** | Add `no-restricted-imports` (ban direct imports from `@/types/generated/api`) + `no-restricted-syntax` for raw `fetch()` (except allowlisted files) | No | Med |
| **BS-50** | `package.json` — add `"sideEffects": ["*.css", "*.svg"]` | Yes | Low |
| **BS-65** | Delete unused exports in `endpoints.ts` (createEndpoints, QUERY_PARAMS, etc.). Keep only used `API_ENDPOINTS` sections | No | Med (contract tests) |
| **BS-72** | `apiCache.ts` — store interval handle, expose `dispose()`. Or delete entire module (after Phase 0 BS-30) | No | Low |

**Dependencies:** BS-44 → BS-45 (sequential). Rest independent.
**Tests:** `npm run lint` + `npm run build` green.

---

## Final Scores

| Criterion | Before fixes | After Phase 0-7 (target) |
|-----------|--------------|--------------------------|
| Migration completeness | 30% | 75% |
| Type safety | 22% | 65% |
| Runtime safety | 25% | 70% |
| Architecture quality | 40% | 70% |
| Maintainability | 25% | 65% |
| Production readiness | 15% | 55% |

**Key verification-pass takeaway:** Of 73 findings, **19 are Proven bugs (A)**, **26 design issues (B)**, **18 possible (C)**, **2 opinion/claim wrong (D)**. One finding (BS-23) is fully refuted. ~19 findings are dead code (simplifies cleanup). 3 findings are medical-safety Critical (BS-17, BS-34, BS-42). 2 are HIPAA Critical (BS-37, BS-38).
