# ADR-0012: TypeScript Migration — Contract Recovery & Zero Debt

**Status:** Accepted
**Date:** 2026-07-23 (Phase F5 — zero debt achieved; Phase G — strict mode)
**Deciders:** Frontend team, Backend team, Engineering lead
**Supersedes:** Phase 0–A incremental JS-to-TS migration (PRs #2390–#2433)
**Related:** PRs #2433, #2444, #2446, #2447, #2449, #2450, #2451, #2452, #2453, #2454; Issue #2443 (closed)

**Scope:** Frontend TypeScript application only (`frontend/src/`). The backend (FastAPI/Python) was not part of this ADR. OpenAPI-generated types (`src/types/generated/api.ts`) are consumed by the frontend but their generation pipeline is out of scope.

**Effort:** ~10 PRs, ~120 commits, ~2 developer-weeks equivalent.

---

## Context

The clinic management system frontend comprised **774 mixed JS/JSX/TS/TSX
source files** with pervasive type debt:

- **413 files** annotated with `@ts-nocheck` (TypeScript compiler bypassed)
- **656 occurrences** of `any` casts (`as any`, `: any`)
- **~1197 TypeScript compiler errors** on a clean `tsc --noEmit`
- **ESLint errors** across the codebase
- No mechanism to prevent regression

The incremental Phase 0–A migration (PRs #2390–#2433, ~120 commits) had
successfully:

- Converted all 774 files to `.ts`/`.tsx` extensions
- Removed all 413 `@ts-nocheck` directives (PR #2433, "Phase B")
- Achieved 0 `tsc` errors

But the codebase still had 656 `any` casts that masked real type contracts.
The team faced a choice:

1. **Stop here** — declare "TypeScript migration complete" with 656 `any` casts
2. **Mechanical cleanup** — replace `any` with `Record<string, unknown>` everywhere
3. **Contract recovery** — invest in rebuilding real Props/hook/state contracts

Option 1 left the codebase with disguised JavaScript. Option 2 would have
introduced hundreds of downstream errors (TypeScript correctly requires
narrowing before accessing `.foo` on `unknown`). Option 3 was the only path
to genuine type safety, but required a disciplined multi-phase approach.

---

## Decision

### 1. Adopt the "Contract Recovery" methodology

Instead of mechanical `any` removal, use a 5-step cycle for each debt site:

```
locate → trace → infer → interface → replace → safe access
```

- **locate** — find the `any` cast site
- **trace** — follow every assignment (`setX(...)` calls, callers, JSX reads)
- **infer** — derive the real shape from API responses, defaults, reducers, JSX
- **interface** — write an explicit domain interface with index signatures
  for backend-driven dynamic fields
- **replace** — swap the `any` for the new interface
- **safe access** — update consumers with `?.` / `?? default` / `String()`

### 2. Dual API for backward-compatible component migration

For high-traffic components (Select, EMRTextField, MacOSTab), introduce a
dual API instead of a breaking change:

```tsx
interface SelectProps {
  /** @deprecated use onValueChange instead — kept for backward compat. */
  onChange?: (event: SelectChangeEvent) => void;
  /** New value-based handler — preferred. */
  onValueChange?: (value: SelectValue) => void;
}
```

The component emits both handlers. Migrate callers incrementally; the
`onChange` deprecation can be enforced later via ESLint rule.

### 3. Caller inventory via ts-morph

Before touching component Props, generate a **caller inventory** using
`scripts/f3-0-caller-inventory.mjs` (ts-morph based). For each component
with `}: any)` cast, the inventory reports:

- All JSX callers (`<ComponentName ... />`) and function-call callers
  (`renderName({...})`)
- Every prop name passed, with the inferred TypeScript type
- Conflicts (same prop name, different types across callers)
- Recommended canonical domain type

This eliminated the "create incompatible interface" failure mode where
an agent writes a Props interface that breaks 5 callers.

### 4. Domain interfaces with index signatures

All Props interfaces include `[key: string]: unknown` so backend-driven
dynamic fields ride along without forcing `as any`:

```ts
export interface QueueSpecialist {
  id: number | string;
  full_name?: string;
  specialty?: string;
  // ... canonical fields
  [key: string]: unknown; // backend may add fields
}
```

This is **not** the same as `Record<string, unknown>` — the canonical
fields are typed and enforced; only unknown extras are permissive.

### 5. CI Debt Gate with baseline=0

`scripts/type-debt-check.mjs` runs in CI on every PR. It enforces:

- **Hard baseline** — total `any` casts ≤ baseline (currently **0**)
- **TECH-DEBT documentation** — if any casts are added in the future,
  they MUST have a `TECH-DEBT(<id>)` comment within 3 lines above them

The baseline was progressively lowered: 31 → 29 → 25 → 20 → 18 → 12 → 8 → 4 → 0.

To reduce debt: fix casts → run `node scripts/type-debt-check.mjs --update`
→ commit the lower baseline. To add a new exception: add a `TECH-DEBT(...)`
comment AND update the baseline in the same PR.

### 6. Zero accepted technical debt (Phase F5 — complete elimination)

All 4 previously-documented casts were eliminated in Phase F5:

| File | Former cast | Resolution |
|------|-------------|------------|
| `types/react-i18next-override.d.ts` | `initReactI18next: any`, `i18n: any` | Replaced override with proper `CustomTypeOptions` module augmentation; wrapped `t()` in `useTranslation` to accept flat string keys |
| `components/integration/IntegrationDemo.tsx` | `Record<string, any>` | Created `IntegrationDemoQueueManager` interface extending `UseQueueManagerReturn` with demo-only fields |
| `utils/navigationReact.ts` | JSDoc `state?: any` | Changed JSDoc to `state?: unknown` |
| `components/dermatology/ProcedureTemplates.tsx` | Commented-out `as any` | Removed dead commented code |

**Zero explicit `any` casts remain** (`as any`, `: any`).

> **Note on implicit `any`:** `strict` and `noImplicitAny` remain disabled in `tsconfig.json`. This means implicit `any` (untyped function parameters, untyped variables) is NOT yet prohibited at the compiler level. The codebase has zero *explicit* `any` casts, but implicit `any` may still exist in untyped code paths. Enabling `strict: true` is tracked as a separate project (see Phase G below and Future Work).

---

## Phases Executed

| Phase | PR | Scope | Debt change |
|-------|-----|-------|-------------|
| Phase B | #2433 | Remove 413 `@ts-nocheck` | 413 → 0 `@ts-nocheck` |
| Phase C | #2444 | Mechanical contract hardening | 656 → 36 `any` casts (-94%) |
| Phase E | #2446 | Select/MacOSTab/EMRTextField dual API | 36 → 30 |
| Phase F0 | (commit) | i18next TECH-DEBT documentation | 30 → 30 (documented) |
| Phase F1 | #2449 | `useQueueManager` + `useChat` hook contracts | 30 → 20 (within PR #2449) |
| Phase F2 | #2449 | Nullable domain state (FileManager/AISettings/Discount) | 20 → 18 |
| Phase F3-0 | #2449 | Caller inventory (read-only) | 18 → 18 (no source changes) |
| Phase F3-1 | #2449 | 5 zero-conflict component Props | 18 → 12 (within PR #2451) |
| Phase F3-2 | #2450 | PatientCard + TeethChart conflict resolution | 12 → 8 |
| Phase F3-3 | #2451 | 10 Generic-domain components | 8 → 4 |
| Phase F4 | #2452 | Form.tsx FormContextValue + ValidationRules | 4 → 4 (refactored and documented, no net reduction) |
| Phase Final | #2453 | TECH-DEBT gate + ADR-0012 + Issue #2443 closure | 4 → 4 (locked in) |
| Phase F5 | #2454 | Eliminate remaining 4 casts (i18next, IntegrationDemo, JSDoc, commented code) | 4 → 0 |
| Phase G | this PR | ADR review corrections + strict-mode assessment (deferred) | 0 → 0 (assessment only) |

**Total: 656 → 0 `any` casts (-100%), 0 `@ts-nocheck`, 0 tsc, 0 eslint.**

---

## Architectural Outcomes

### Typed hook contracts

- `UseQueueManagerReturn` — 13 fields with real domain types
  (QueueSpecialist[], QueueData | null, QrData | null, etc.)
- `ChatContextValue` — 25 fields with corrected ChatReaction shape and
  Dispatch<SetStateAction> setters

### Typed Form API

- `FormContextValue` — 4 callable function signatures (was `{} as any`)
- `ValidationRule` + `ValidationRules` — backward-compatible with legacy
  `{ required: 'msg' }` shape via `Record<string, ValidationRule | string>`
- Shared `validateValueAgainstRules` helper (was duplicated 4x)

### Dual value-based component APIs

- `Select`: `onChange` (deprecated, event-like) + `onValueChange` (new, value-based)
- `EMRTextField`: same dual API pattern
- `MacOSTab`: `onTabChange: (id: TabId)` where `TabId = string | number`

### Domain state interfaces

- `AIStats`, `AIProviderFormData` (AISettings)
- `DiscountAnalytics` + 3 section interfaces (DiscountBenefitsManager)
- `FileManagerStats`, `FileStorageUsage` (FileManager)

### Component Props contracts (17 components)

- 5 zero-conflict components (EchoForm, QueuePositionCard, AppointmentFlow,
  WelcomeView, CartStepV2) — PR #2449
- 2 conflict-resolution components (PatientCard, TeethChart) — PR #2450
- 10 Generic-domain components (PhoneVerification, DentalPatientsTab,
  DoctorServiceSelector, renderStatCard, QueueTable, ComplaintsField,
  ModernQueueManager, PrescriptionEditor, EMRSmartFieldV2, Table) — PR #2451

### Tooling

- `scripts/f3-0-caller-inventory.mjs` — re-runnable ts-morph inventory
- `docs/f3-0-caller-inventory.md` — 933-line inventory report
- `scripts/type-debt-check.mjs` — CI gate with baseline + TECH-DEBT verification

---

## tsconfig.json — current state

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowJs": true,
    "checkJs": false,
    "jsx": "react-jsx",
    "strict": false,
    "noImplicitAny": false,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true
  }
}
```

**Strict flags NOT yet enabled** (separate future project):

- `strict: true` — would enable noImplicitAny, strictNullChecks, etc.
- `noUncheckedIndexedAccess: true` — would force narrowing on every
  array/object index access
- `exactOptionalPropertyTypes: true` — would distinguish `prop?: T` from
  `prop: T | undefined`
- `noImplicitOverride: true` — would require `override` keyword
- `noPropertyAccessFromIndexSignature: true` — would force bracket
  notation for index-signature fields

Enabling these is out of scope for the migration PR series. The current
state (0 tsc, 0 eslint, 4 documented casts) is the **migration endpoint**.
Further strictness is a **policy decision** for a separate ADR.

---

## Consequences

### Positive

- **Type safety without breaking changes** — dual API kept callers compiling
- **Documented debt** — every remaining cast has a TECH-DEBT ID and resolution path
- **Regression prevention** — CI gate blocks new undocumented casts
- **Reusable domain types** — `QueueSpecialist`, `PatientCardPatient`,
  `TableColumn`, etc. exported for future use
- **Inventory artifact** — `docs/f3-0-caller-inventory.md` is a living
  reference for future component refactors
- **DRY validation logic** — Form.tsx validation extracted to shared helper

### Negative

- **Index signatures accept any string key** — `[key: string]: unknown` means
  typos in field names won't be caught at compile time. Mitigated by typed
  canonical fields above the index signature.
  > **Recommendation:** New domain interfaces SHOULD avoid index signatures
  > unless the backend contract is demonstrably extensible. Existing index
  > signatures are a migration compromise and may be removed incrementally
  > as backend contracts are verified.
- **CI unit tests time out** — Frontend unit tests frequently exceed the
  15-minute CI job limit. PRs merge with `mergeable=True, state=unstable`
  when this happens (PR Required Gate fails but is non-blocking). This is
  a pre-existing CI infrastructure issue, not a migration regression.
- **`strict: false`** — full strict mode was NOT enabled during Phases B–F5.
  The migration achieved 0 tsc errors under the current loose config; enabling
  strict mode would surface new errors (implicit `any`, strict null checks,
  strict function types). Phase G (below) addresses this incrementally.

### Neutral

- **`allowJs: true`** retained — no JS files remain in `frontend/src/`, but
  the flag is kept for build-tool compatibility (some config files use JS).

---

## Risk Register

- **Dual APIs may remain indefinitely** if `onChange` deprecation is not
  enforced via ESLint rule. Mitigation: tracked in Future Work (long-term).
- **Index signatures can hide field-name typos** — `[key: string]: unknown`
  on domain interfaces allows arbitrary string keys without compile-time
  checking. Mitigation: recommendation added in Consequences section;
  strict Props interfaces tracked in Future Work.
- **Strict mode may surface substantial nullable-state debt** — enabling
  `strict: true` (Phase G) will introduce `strictNullChecks`, which may
  reveal dozens of unguarded null/undefined access patterns. Mitigation:
  Phase G enables strict flags incrementally.
- **Debt checker pattern is narrow** — the current regex matches `as any`
  and `: any` but NOT `Record<string, any>`, `Promise<any>`, or
  `Array<any>`. An experimental broader pattern surfaced 101 additional
  legacy sites. The experiment was reverted to avoid turning the migration
  PR into a large unrelated cleanup. A follow-up initiative is tracked
  under Future Work.

---

## Future Work

### Short-term (next quarter)

- **Phase G: Enable `strict: true`** — see Phase G section below for the
  incremental approach. This is the natural next step after zero-debt.
- **Tighten debt checker pattern** — the current `type-debt-check.mjs`
  matches `as any` and `: any` but NOT `Record<string, any>`,
  `Promise<any>`, or `Array<any>`. An experimental broader pattern
  surfaced 101 additional legacy sites and was reverted to avoid scope
  creep. A follow-up PR can tighten the pattern after cleaning up those
  sites.

### Long-term (next year)

- **Migrate `onChange` deprecation** — once all callers of Select/EMRTextField
  use `onValueChange`, remove the deprecated `onChange` handler and add an
  ESLint rule to prevent re-introduction.
- **Generate domain types from OpenAPI** — the backend has an OpenAPI spec
  (`src/types/generated/api.ts`). Currently the frontend defines parallel
  domain types by hand. A code generator could keep them in sync.
- **Strict Props interfaces** — remove `[key: string]: unknown` index
  signatures from components where the backend contract is fully known.
  This trades flexibility for compile-time field-name checking.

---

## Phase G — Strict Mode Assessment

Phase G assessed the feasibility of enabling `strict: true` in `tsconfig.json`.
The assessment was performed by temporarily enabling strict mode and counting
the resulting TypeScript compiler errors.

### Error breakdown (strict: true, all flags)

| Flag | Error count | Top error codes |
|------|-------------|-----------------|
| `strict: true` (all) | **10,098** | TS2339 (3583), TS7006 (3135), TS7031 (849), TS7053 (491) |
| `noImplicitAny: true` alone | 5,417 | TS7006, TS7031, TS7053 (implicit `any` on untyped params) |
| `strictNullChecks: true` alone | 4,998 | TS2339, TS2322, TS18047 (null/undefined access) |

### Interpretation

- **TS7006/TS7031** (3,984 errors) — untyped function parameters and destructured
  bindings. These are the bulk of the debt: hundreds of functions like
  `const handleChange = (e) => ...` where `e` is implicitly `any`. Fixing
  requires adding type annotations to ~2,000 function signatures.
- **TS2339** (3,583 errors) — property access on `unknown`/`null`/`undefined`.
  Many are downstream of the index-signature compromise (`[key: string]: unknown`)
  — accessing `.foo` on `unknown` requires narrowing. Fixing requires either
  type guards or explicit casts at each access site.
- **TS7016** (289 errors) — missing declaration files for untyped npm packages.
  Requires adding `@types/*` packages or writing custom `.d.ts` shims.

### Decision

**Phase G is deferred.** Enabling `strict: true` in one step would surface
10,098 errors — far too many for a single PR. The recommended approach is
incremental:

1. **G1: `noImplicitAny`** (5,417 errors) — batch-add type annotations to
   untyped function parameters. Estimated 3–5 days.
2. **G2: `strictNullChecks`** (4,998 errors, overlapping) — add null guards
   and optional chaining. Estimated 5–7 days.
3. **G3: Remaining strict flags** (`strictFunctionTypes`, `strictBindCallApply`,
   `strictPropertyInitialization`, `noImplicitThis`, `alwaysStrict`) —
   estimated 2–3 days.
4. **G4: Library type gaps** (289 errors) — add `@types/*` packages or
   custom `.d.ts` shims for untyped npm dependencies.

Total estimated effort: **2–3 developer-weeks** for full `strict: true`.

### Current state

`tsconfig.json` retains `strict: false` and `noImplicitAny: false`. The
codebase has zero *explicit* `any` casts (enforced by CI debt gate), but
*implicit* `any` is still permitted by the compiler. This is the accepted
endpoint of the Phase B–F5 migration; Phase G is a separate future project.

---

## References

- **Migration plan**: `docs/Tree_F.md` (Phase F contract recovery tree)
- **Caller inventory**: `docs/f3-0-caller-inventory.md`
- **Debt registry**: GitHub Issue #2443
- **CI gate**: `scripts/type-debt-check.mjs` + `.github/workflows/ci-cd-unified.yml`
- **Baseline**: `scripts/type-debt-baseline.json` (currently 0)
- **Phase PRs**: #2433, #2444, #2446, #2447, #2449, #2450, #2451, #2452, #2453, #2454
