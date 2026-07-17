# Migration Blockers — JS→TS Migration Stabilization Sprint

**Created:** 2026-07-17
**Branch:** `stabilization-sprint` (based on `phase-1-utils-api`)
**Reason:** Independent audit revealed that Phases 2-9 introduced semantic
damage via regex-patches and masked 96 ESLint errors via mass `@ts-nocheck`.
This sprint stabilizes the migration before continuing.

**Related documents:**
- [`docs/migration/DECISIONS.md`](./docs/migration/DECISIONS.md) — chronological decision log (WHY decisions were made)
- [`docs/migration/ADR-001`](./docs/migration/ADR-001-backend-ssot.md) — Backend = SSOT
- [`docs/migration/ADR-002`](./docs/migration/ADR-002-generated-dto-immutable.md) — Generated DTO immutable
- [`docs/migration/ADR-003`](./docs/migration/ADR-003-dto-mapper-domain.md) — DTO → Mapper → Domain
- [`docs/migration/ADR-004`](./docs/migration/ADR-004-no-ts-nocheck-policy.md) — No @ts-nocheck policy

**⚠️ PROCESS FROZEN (2026-07-17):** This document, the Definition of Done,
and the Migration Cycle are FROZEN. No more process changes until 3-5 PRs
are completed by the current rules. Only then evaluate what works and what
needs adjustment. (Per reviewer recommendation: avoid infinitely improving
the process instead of migrating code.)

---

## Baseline at Phase 1 (2026-07-17)

**Quality metrics (not file counts):**

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Migrated files | 110 / 773 (14.2%) | 773 / 773 (100%) | 🟡 In progress |
| Fully typed (of migrated) | 110 / 110 (100%) | 100% | ✅ |
| Legacy exceptions (of migrated) | 0 / 110 (0%) | < 8% | ✅ |
| `@ts-nocheck` files | 0 | 0 (always) | ✅ |

**Type Debt (categorized):**

| Pattern | ✅ External | ⚠️ Legacy | ❌ To-compile | Total | Target |
|---------|-------------|-----------|---------------|-------|--------|
| `any` (real code) | 0 | 17 | 0 | 17 | ↓ 0 |
| `any` (JSDoc only) | 4 | 0 | 0 | 4 | ↓ 0 |
| `as unknown as` | 0 | 9 | 0 | 9 | ↓ 0 |
| `@ts-expect-error` | 0 | 0 | 0 | 0 | 0 |
| `@ts-ignore` | 0 | 0 | 0 | 0 | 0 |
| `eslint-disable` | 0 | 6 | 0 | 6 | ↓ 0 |
| `TODO(TS-MIGRATION)` | 0 | 0 | 0 | 0 | 0 |
| `FIXME(TS)` | 0 | 0 | 0 | 0 | 0 |
| `@ts-nocheck` | 0 | 0 | 0 | 0 | 0 (always) |

**Test coverage:**

| Metric | Current | Target |
|--------|---------|--------|
| Total hooks | 61 (still .js) | 61 migrated to .ts |
| Hooks with unit tests | 5 / 61 | 61 / 61 |
| Total tests passing | 864 | 864+ (no regressions) |

**Process health:**

| Metric | Current | Target |
|--------|---------|--------|
| `tsc --noEmit` errors | 0 | 0 (always) |
| ESLint errors | 0 | 0 (always) |
| Files with semantic damage (regex) | 0 | 0 (always) |

> **Note on metrics:** Success is NOT measured by the number of `.ts` files.
> A file renamed to `.ts` with `@ts-nocheck` is NOT migrated — it's
> disguised JS. The real metrics are: % fully typed, % legacy exceptions,
> and Type Debt counts trending to 0.

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

### 🟡 Medium — type debt tracking

#### B5: Type Debt Register

**Status:** Open. Baseline measured at Phase 1 (2026-07-17).

Any new occurrence of the following patterns must either:
1. Be entered into the Type Debt Register (this section) with a category, OR
2. Be eliminated before merge.

**Tracked patterns:**
- `any` (type annotation or cast)
- `as unknown as` (double cast — usually a sign of wrong types)
- `@ts-expect-error`
- `@ts-ignore`
- `eslint-disable` (any rule)
- `// TODO(TS-MIGRATION)` (explicit marker for migration debt)
- `// FIXME(TS)` (explicit marker for known type issues)

**Categories (must be assigned to each register entry):**

| Category | Symbol | Acceptable? | Example |
|----------|--------|-------------|---------|
| **External library** | ✅ | Yes — library doesn't ship types | `import x from 'untyped-lib'; const y: any = x;` |
| **Legacy API** | ⚠️ | Conditional — track for backend cleanup | Backend returns untyped JSON; `as any` until schema is added to OpenAPI |
| **"To make it compile"** | ❌ | No — must be refactored before merge | `function foo(x: any) { return x.bar; }` — should be `interface X { bar: unknown }` |

**Baseline at Phase 1 (2026-07-17):**

| Pattern | Total | ✅ External | ⚠️ Legacy | ❌ To-compile |
|---------|-------|-------------|-----------|---------------|
| `any` (real code) | 17 | 0 | 17 (panelPrint.ts) | 0 |
| `any` (JSDoc only) | 4 | 4 (harmless — `@returns {Promise<any>}` in JSDoc) | — | — |
| `as unknown as` | 9 | 0 | 9 (panelPrint.ts, mcpTest.ts) | 0 |
| `@ts-expect-error` | 0 | — | — | — |
| `@ts-ignore` | 0 | — | — | — |
| `eslint-disable` | 6 | 0 | 6 (panelPrint.ts, registrarAggregation.ts) | 0 |
| `TODO(TS-MIGRATION)` | 0 | — | — | — |
| `FIXME(TS)` | 0 | — | — | — |
| `@ts-nocheck` | 0 | — | — | — |

**Register (live entries):**

| File:Line | Pattern | Category | Reason | Resolution |
|-----------|---------|----------|--------|------------|
| `services/panelPrint.ts:*` (17 occurrences) | `any` | ⚠️ Legacy | 1140-line file with heterogeneous print payload shapes; proper typing requires modeling the full print pipeline | Phase 9 cleanup (after decomposition) |
| `utils/registrarAggregation.ts:178` | `any` | ⚠️ Legacy | Heterogeneous aggregation result shape; tightening requires modeling the full aggregation pipeline | Phase 9 cleanup |
| `utils/mcpTest.ts:18` | `as unknown as` | ⚠️ Legacy | Dead test code (manual integration scaffold); method names don't match actual mcpClient API — pre-existing inconsistency | Delete file in Phase 9 (verify no consumers first) |
| `api/mcpClient.ts:33`, `api/health.ts:10,20`, `utils/navigationReact.ts:23` | `any` (JSDoc) | ✅ External | JSDoc `@returns {Promise<any>}` — not real code; cosmetic only | Clean up JSDoc in Phase 9 |

**Policy:**
- New PRs must not INCREASE these counts without a register entry.
- Each entry must include: file, line, pattern, **category**, reason, expected resolution date.
- ❌ "To make it compile" category is FORBIDDEN in new code — must be refactored.
- The register is reviewed at the end of each sprint.

**Verification (run before each PR merge):**
```bash
echo "=== Type Debt Register check ==="
echo "any (real code): $(grep -rn ': any\b\|<any>\|as any\b' src/ --include='*.ts' --include='*.tsx' | grep -v '@ts-nocheck' | grep -v '^.*\* @' | wc -l)"
echo "any (JSDoc only): $(grep -rn ': any\b\|<any>\|as any\b' src/ --include='*.ts' --include='*.tsx' | grep -v '@ts-nocheck' | grep '^.*\* @' | wc -l)"
echo "as unknown as: $(grep -rn 'as unknown as' src/ --include='*.ts' --include='*.tsx' | grep -v '@ts-nocheck' | wc -l)"
echo "@ts-expect-error: $(grep -rn '@ts-expect-error' src/ --include='*.ts' --include='*.tsx' | wc -l)"
echo "@ts-ignore: $(grep -rn '@ts-ignore' src/ --include='*.ts' --include='*.tsx' | wc -l)"
echo "eslint-disable: $(grep -rn 'eslint-disable' src/ --include='*.ts' --include='*.tsx' | grep -v '@ts-nocheck' | wc -l)"
echo "TODO(TS-MIGRATION): $(grep -rn 'TODO(TS-MIGRATION)' src/ --include='*.ts' --include='*.tsx' | wc -l)"
echo "FIXME(TS): $(grep -rn 'FIXME(TS)' src/ --include='*.ts' --include='*.tsx' | wc -l)"
echo "@ts-nocheck: $(grep -rl '@ts-nocheck' src/ | wc -l)"
```
If any count is HIGHER than the baseline above, the PR must either:
- Add a register entry (with category) explaining the increase, OR
- Refactor to avoid the new debt.

❌ Category debt is NEVER acceptable in new code.

---

## Definition of Done (per PR)

Every PR in the migration must satisfy ALL of the following before merge:

- [ ] **`tsc --noEmit` passes** — 0 errors. Paste the actual command output in the PR description.
- [ ] **`npm run lint:check` passes** — 0 errors (warnings are OK if unchanged from baseline). Paste the `✖ N problems (0 errors, M warnings)` line.
- [ ] **Review generated diff** — manually read every changed line. This is the most important check. The regex-migration disaster happened because nobody read the diff. If a script was used, explain in the PR what the script does and confirm each file was reviewed. Pay special attention to:
  - Destructuring patterns (the `paramName = value` → `paramName: Type = value` bug)
  - Dependency arrays in React hooks (`useEffect(..., [deps])`)
  - Import paths (`.js` → `.ts` extensions in dynamic imports)
  - Type assertions (`as any`, `as unknown as`) — each must have a reason
- [ ] **No new `@ts-nocheck`** — `grep -rl "@ts-nocheck" src/ | wc -l` must not increase.
- [ ] **No new `any` without a comment** — each new `any` must have an inline `// reason: ...` comment or a B5 register entry with category. ❌ "To make it compile" category is forbidden.
- [ ] **No new `as unknown as` without a comment** — same as above.
- [ ] **All existing tests pass** — `npm run test:run` must show `864/864` (or whatever the current count is).
- [ ] **Tests added for uncovered critical code** — if the PR migrates a hook/utility/component that has no tests, add at least 3 tests (happy path, error path, options destructuring).
- [ ] **PR is fully reviewable** — there is no hard file-count limit, but the PR must remain fully reviewable by a human reviewer. Guidance:
  - ~30 files of mechanical changes (e.g. `.js` → `.ts` rename with no logic change) is reviewable
  - ~12 files with architectural changes (new types, refactored APIs) is reviewable
  - If the reviewer would skim instead of read, the PR is too large — split it
  - When in doubt, err on the side of smaller PRs
- [ ] **No regex patches that touch destructuring syntax** — the pattern `paramName = value` → `paramName: Type = value` is FORBIDDEN in destructuring context. Use `paramName = value as Type` or type the parent object.
- [ ] **Mass-change preview rule** (if a script is used to apply changes across multiple files):
  1. Run the script on 5 sample files first
  2. Manually review each of the 5 outputs
  3. If all 5 are correct, run on the rest
  4. After the full run, manually spot-check 5 more random files
  5. Document this process in the PR description

**PR description template:**
```
## What this PR does
[1-3 sentences]

## Verification
- `tsc --noEmit`: [paste output]
- `npm run lint:check`: [paste ✖ line]
- `npm run test:run`: [paste Test Files / Tests line]

## Type Debt Register impact
- `any` (real code): [baseline 17] → [new count] ([change])
- `as unknown as`: [baseline 9] → [new count] ([change])
- `@ts-nocheck`: 0 → 0 (no change)
- New register entries: [list or "none"]

## Diff review
- [ ] I read every changed line
- [ ] No destructuring patterns were altered semantically
- [ ] No new `any`/`as unknown as` without B5 entry
- [ ] (If script was used) Preview on 5 files reviewed; full run spot-checked

## Definition of Done checklist
- [ ] tsc --noEmit passes
- [ ] ESLint 0 errors
- [ ] Review generated diff (most important)
- [ ] No new @ts-nocheck
- [ ] No new any without comment
- [ ] All tests pass
- [ ] Tests added for uncovered code
- [ ] PR is fully reviewable
- [ ] No destructuring regex patches
- [ ] Mass-change preview rule followed (if applicable)
```

---

## Sprint goals

1. **Fix B2** — bring ESLint errors at Phase 1 from 13 → 0 ✅ CLOSED (2026-07-17)
   - Verified: 11 no-undef errors compensated by `tsc` (TS2304 Cannot find name)
   - Verified: 2 no-console errors resolved by infrastructure allowlist (.ts variant added)
   - Verified: ESLint DOM globals were redundant (removed — tsc knows them via lib.dom.d.ts)
   - No errors were masked without compensation
2. **Establish migration rules** — documented in "Forbidden patterns" and "Definition of Done" sections ✅
3. **Establish Type Debt Register (B5)** — baseline measured, policy documented, categories introduced ✅
   - Categories: ✅ External library / ⚠️ Legacy API / ❌ To-compile (forbidden)
   - Patterns tracked: `any`, `as unknown as`, `@ts-expect-error`, `@ts-ignore`, `eslint-disable`, `TODO(TS-MIGRATION)`, `FIXME(TS)`
4. **Establish migration cycle** — documented 10-step cycle (read → contract test → invariants → types → migrate → diff review → tsc → eslint → tests → PR) ✅
5. **Establish mass-change preview rule** — 5-file preview → manual review → full run → spot-check ✅
6. **Re-plan Phase 2** — instead of 61 hooks at once, do 5-10 hooks per PR
   with real typing and tests (next sprint — NOT started yet, per reviewer
   recommendation to let the process settle first)
7. **Update this document** after each goal is closed

## Forbidden patterns (learned from Phase 2-9 mistakes)

1. **MASS @ts-nocheck** — never add @ts-nocheck to more than 1 file per PR
   without explicit justification in commit message

2. **Regex patches that touch destructuring syntax** — the pattern
   `paramName = value` → `paramName: Type = value` is INVALID in
   destructuring context. It changes semantics from "default value"
   to "rename + default value".

3. **Claims of "0 errors" without verification** — always run the actual
   command and paste the output. Never trust cached or assumed results.

4. **Migrating more than ~30 files per PR** — large PRs hide semantic
   damage. Smaller PRs force careful review. (See DoD for nuanced guidance —
   file count is not absolute; reviewability is the real metric.)

5. **Mass automatic changes without preview** — any script that modifies
   multiple files must be previewed on 5 sample files first, manually
   reviewed, then run on the rest. See DoD "Mass-change preview rule".

6. **❌ "To make it compile" `any`** — never use `any` to silence a type
   error. Either type it properly (`unknown`, `Record<string, unknown>`,
   or a real interface) or add a B5 register entry with a real category
   (External library or Legacy API).

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

4. **Read the code before migrating** — understand what the code does,
   what invariants it relies on, what contract tests protect it. Only
   then write types. This prevents "I added types but broke semantics".

---

## Migration cycle (per file or small batch)

The migration cycle for each file (or batch of 5-10 related files):

```
1. Read the code
   ↓  (understand what it does, what it imports, what it exports)
2. Read the contract test
   ↓  (if one exists; understand what invariants it protects)
3. Understand the invariants
   ↓  (what must remain true after migration? what would break callers?)
4. Write the types
   ↓  (interfaces, type aliases, generics — before touching the .js file)
5. Migration
   ↓  (rename .js → .ts, apply types, fix any tsc errors)
6. Diff review
   ↓  (manually read every changed line — most important step)
7. tsc --noEmit
   ↓  (must be 0 errors)
8. ESLint
   ↓  (must be 0 errors; warnings OK if unchanged)
9. Tests
   ↓  (all existing pass; new tests added for uncovered critical paths)
10. PR
    ↓  (with DoD checklist + Type Debt Register impact)
```

**Key insight:** Step 1 (read the code) comes BEFORE step 5 (migration).
This is the opposite of the regex-mass-migration approach that broke
Phase 2-9. Understanding the code first prevents semantic damage.

**Batch size:** 5-10 files per PR. If files are tightly coupled (e.g.
a hook + its test + its consumer), they belong in the same PR. If files
are independent, they can be in separate PRs.

**Time budget:** Expect ~30-60 minutes per file for proper migration
(read + types + migrate + review + tests). 5 files = ~3-5 hours. This
is intentional — slow migration is safe migration.
