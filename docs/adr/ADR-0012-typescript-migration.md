# ADR-0012: TypeScript Migration — Contract Recovery & Debt Gate

**Status:** Accepted
**Date:** 2026-07-23
**Deciders:** Frontend team, Backend team, Engineering lead
**Supersedes:** Phase 0–A incremental JS-to-TS migration (PRs #2390–#2433)
**Related:** PRs #2433, #2444, #2446, #2447, #2449, #2450, #2451, #2452; Issue #2443

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

### 5. CI Debt Gate with baseline + TECH-DEBT documentation

`scripts/type-debt-check.mjs` runs in CI on every PR. It enforces:

- **Hard baseline** — total `any` casts ≤ baseline (currently 4)
- **TECH-DEBT documentation** — every remaining `any` cast MUST have a
  `TECH-DEBT(<id>)` comment within 3 lines above it

```ts
// TECH-DEBT(i18n-001): i18next instance type is complex; left as any for now.
// Re-evaluate after library upgrade or proper module augmentation.
i18n: any;
```

To reduce debt: fix casts → run `node scripts/type-debt-check.mjs --update`
→ commit the lower baseline. To add a new exception: add a `TECH-DEBT(...)`
comment AND update the baseline in the same PR.

### 6. Accepted technical debt (4 documented casts)

| File | Cast | ID | Resolution path |
|------|------|----|-----------------|
| `types/react-i18next-override.d.ts:6` | `initReactI18next: any` | `i18n-001` | Library upgrade |
| `types/react-i18next-override.d.ts:13` | `i18n: any` | `i18n-001` | Library upgrade |
| `components/integration/IntegrationDemo.tsx:23` | `Record<string, any>` | `integration-demo-001` | Demo rewrite (pre-existing broken fields) |
| `utils/navigationReact.ts:23` | JSDoc `state?: any` | (none — documentation only) | Not code, no action needed |

No production code contains undocumented `any` casts.

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
| Phase F4 | #2452 | Form.tsx FormContextValue + ValidationRules | 4 → 4 (final, all documented) |

**Total: 656 → 4 `any` casts (-99.4%), 0 `@ts-nocheck`, 0 tsc, 0 eslint.**

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
- **4 casts remain** — `react-i18next` (2), `IntegrationDemo` (1),
  `navigationReact` JSDoc (1). All documented; further reduction requires
  library upgrade or demo rewrite.
- **CI unit tests time out** — Frontend unit tests frequently exceed the
  15-minute CI job limit. PRs merge with `mergeable=True, state=unstable`
  when this happens (PR Required Gate fails but is non-blocking). This is
  a pre-existing CI infrastructure issue, not a migration regression.
- **`strict: false`** — full strict mode is NOT enabled. The migration
  achieved 0 tsc errors under the current loose config; enabling strict
  mode would surface new errors and is a separate project.

### Neutral

- **`allowJs: true`** retained — no JS files remain in `frontend/src/`, but
  the flag is kept for build-tool compatibility (some config files use JS).

---

## Future Work

### Short-term (next quarter)

- **Enable `strict: true`** in a dedicated PR with batched fixes for any
  new errors surfaced. This is the natural next step but requires its own
  migration plan (estimated 1–2 weeks of focused work).
- **i18next library upgrade** — re-evaluate `react-i18next-override.d.ts`
  casts after upgrading to a version with better TypeScript support.
- **IntegrationDemo rewrite** — the demo file uses fields that don't exist
  on `UseQueueManagerReturn` (e.g. `generateQRCode`, `error`, `success`).
  Either fix the demo to use real fields or delete it.

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

## References

- **Migration plan**: `docs/Tree_F.md` (Phase F contract recovery tree)
- **Caller inventory**: `docs/f3-0-caller-inventory.md`
- **Debt registry**: GitHub Issue #2443
- **CI gate**: `scripts/type-debt-check.mjs` + `.github/workflows/ci-cd-unified.yml`
- **Baseline**: `scripts/type-debt-baseline.json` (currently 4)
- **Phase PRs**: #2433, #2444, #2446, #2447, #2449, #2450, #2451, #2452
