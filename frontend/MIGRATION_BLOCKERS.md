# Migration Blockers — JS→TS Migration Stabilization Sprint

**Created:** 2026-07-17
**Branch:** `stabilization-sprint` (based on `phase-1-utils-api`)
**Reason:** Independent audit revealed that Phases 2-9 introduced semantic
damage via regex-patches and masked 96 ESLint errors via mass `@ts-nocheck`.
This sprint stabilizes the migration before continuing.

---

## Baseline at Phase 1 (2026-07-17)

| Metric | Value | Status |
|--------|-------|--------|
| TS/TSX files | 110 | ✅ |
| JS/JSX files | 663 | (not yet migrated — intentional) |
| `@ts-nocheck` files | 0 | ✅ |
| `tsc --noEmit` errors | 0 | ✅ |
| ESLint errors | **0** | ✅ (was 13, fixed in B2) |
| ESLint warnings | 2810 | (unchanged from main) |
| Tests passing | 864/864 | ✅ |

---

## Blocker list

### 🔴 Critical — must fix before any further migration

#### B1: Semantically damaged destructuring (Phase 2-9 only — not in Phase 1)

**Status:** NOT APPLICABLE at Phase 1 baseline. These damages were
introduced in Phase 2 by `scripts/patch-hooks.py` regex that converted
`paramName = null` → `paramName: unknown = null` — which in destructuring
context means "rename paramName to unknown", not "type paramName as unknown".

**Files affected (in phase-9-finalize, NOT in stabilization-sprint):**
- `src/hooks/useAsyncAction.ts` — loadingMessage, successMessage, onSuccess, onError
- `src/hooks/useApi.ts` — fallbackData, validate, transform, onMessage, onConnect, onDisconnect
- `src/hooks/useAdminData.ts` — initialData
- `src/hooks/useSafeInput.ts` — customValidator (2 places)
- `src/hooks/useEMRTelemetry.ts` — sessionId
- `src/hooks/useDoctorPanelState.ts` — initialTab
- `src/hooks/useNavigation.tsx` — activeItem

**Fix:** When migrating these files in future phases, use
`paramName = null as unknown` instead of `paramName: unknown = null`
in destructuring contexts. Or — better — type the parent object.

**Verification:** `grep -rn "^\s*[a-zA-Z]*:\s*\(unknown\|Record<string, unknown>\)\s*=" src/`
should return 0 lines.

---

### 🔴 High — must fix before merge of any new phase

#### B2: ESLint errors at Phase 1 baseline (13 errors)

**Status:** ✅ CLOSED (2026-07-17)

**Root cause:** ESLint config did not declare TS DOM lib types
(`BodyInit`, `RequestInit`, `NotificationOptions`, `NotificationPermission`)
as globals for `.ts`/`.tsx` files. Also, `no-undef` rule was running on
`.ts`/`.tsx` files where TypeScript already does this check via `tsc`.

**Fix applied (`eslint.config.js`):**
1. Added `parserOptions.project: './tsconfig.json'` so `@typescript-eslint/parser`
   reads the project's TS config (including `lib: ["DOM", "DOM.Iterable"]`)
2. Added explicit `globals` for TS DOM lib types that ESLint doesn't know
   about by default (`BodyInit`, `RequestInit`, `NotificationOptions`,
   `NotificationPermission`, `WebSocket`, `ServiceWorkerRegistration`, etc.)
3. Turned off `no-undef` for `.ts`/`.tsx` files — TypeScript already does
   this check via `tsc`. ESLint's `no-undef` doesn't understand TS type
   declarations (interfaces, types, DOM lib globals).
4. Updated infrastructure allowlist to include both `.js` and `.ts`
   variants of files that are allowed to use `console` / `localStorage`
   directly (`navigation.ts`, `client.ts`, etc.)

**Verification:** `npm run lint:check 2>&1 | grep "✖"` → `2810 problems (0 errors, 2810 warnings)`

---

### 🟡 Medium — technical debt, can be closed gradually

#### B3: 481 files with `@ts-nocheck` (in phase-9-finalize only)

**Status:** NOT APPLICABLE at Phase 1 baseline (0 files with @ts-nocheck).
Phase 2-9 will NOT use @ts-nocheck — they will be re-done with proper typing
in batches of ~30 files per PR.

**Plan:** Future phases will type files properly. No file gets @ts-nocheck
unless explicitly justified (e.g. third-party type definitions missing).

**Verification:** `grep -rl "@ts-nocheck" src/ | wc -l` → 0 (always)

---

#### B4: Uncovered hooks (no tests for hooks touched by migration)

**Status:** Open at Phase 1. The following hooks have no unit tests:
- `useAsyncAction` (does not exist yet at Phase 1 — will be created in Phase 2)
- `useApi` (does not exist yet at Phase 1)
- `useAdminData` (does not exist yet at Phase 1)
- `useSafeInput` (does not exist yet at Phase 1)

**Plan:** Before migrating each hook in Phase 2, write a unit test that
exercises its core behavior. The test must fail if destructuring is broken.

**Verification:** Each migrated hook has a corresponding test file in
`src/hooks/__tests__/` with at least 3 tests covering: happy path,
error path, options destructuring.

---

## Sprint goals

1. **Fix B2** — bring ESLint errors at Phase 1 from 13 → 0
2. **Establish migration rules** — document the regex patterns that are
   forbidden and the patterns that are safe
3. **Re-plan Phase 2** — instead of 61 hooks at once, do 5-10 hooks per PR
   with real typing and tests
4. **Update this document** after each goal is closed

## Forbidden patterns (learned from Phase 2-9 mistakes)

1. **MASS @ts-nocheck** — never add @ts-nocheck to more than 1 file per PR
   without explicit justification in commit message

2. **Regex patches that touch destructuring syntax** — the pattern
   `paramName = value` → `paramName: Type = value` is INVALID in
   destructuring context. It changes semantics from "default value"
   to "rename + default value".

3. **Claims of "0 errors" without verification** — always run the actual
   command and paste the output. Never trust cached or assumed results.

4. **Migrating more than 30 files per PR** — large PRs hide semantic
   damage. Smaller PRs force careful review.

## Safe patterns

1. **Type the parent object** instead of destructuring with type annotations:
   ```ts
   // BAD (in destructuring):
   const { x: unknown = null } = options;

   // GOOD:
   interface Options { x?: unknown; }
   const { x = null } = options as Options;
   ```

2. **Use `as` cast at call site** when receiving untyped data:
   ```ts
   // BAD:
   function foo(x = {}) { /* x is {} — no field access */ }

   // GOOD:
   function foo(x: Record<string, unknown> = {}) { /* x.field works */ }
   ```

3. **Write the test first** for any non-trivial hook — if the test is
   hard to write, the hook's API is probably wrong.
