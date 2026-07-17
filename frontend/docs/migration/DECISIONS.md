# Migration Decision Log

This file records all significant decisions made during the JS→TS migration.
Unlike MIGRATION_BLOCKERS.md (which tracks blockers and process rules),
this file is a chronological log of WHY decisions were made — the context
that would otherwise be lost.

Format: each entry has Date, Decision, Reason, Alternative considered,
Status, and (when applicable) a link to a detailed ADR.

---

## 2026-07-17 — Phase 0–0.5

### D-001: Backend = SSOT for domain types
- **Decision:** All domain types (User, Patient, Appointment, roles, etc.)
  are generated from `backend/openapi.json` via `openapi-typescript`.
  Manual typing of domain entities is forbidden.
- **Reason:** Prevents drift between frontend types and backend API.
  When backend changes, frontend types update automatically via
  `npm run generate:api-types`.
- **Alternative considered:** Manual typing with TypeScript interfaces.
  Rejected — would require sync discipline that fails under time pressure.
- **Status:** Accepted
- **Detailed:** [ADR-001](./ADR-001-backend-ssot.md)

### D-002: Generated types are read-only
- **Decision:** Files in `src/types/generated/` are never edited by hand.
  A header warning + ESLint ignore + `linguist-generated` in .gitattributes
  protect them. CI gate `generate:api-types:check` fails if generated
  types are stale.
- **Reason:** Hand-edits would be lost on next regeneration. The header
  makes the rule explicit; CI enforces it.
- **Alternative considered:** Allow hand-edits with a `.patch` file.
  Rejected — too clever, breaks contributor onboarding.
- **Status:** Accepted
- **Detailed:** [ADR-002](./ADR-002-generated-dto-immutable.md)

### D-003: DTO → Mapper → Domain architecture for auth
- **Decision:** Generated DTOs (raw transport shapes from OpenAPI) are
  NOT re-typed to encode business invariants. Instead, domain types
  (discriminated unions) live in `auth.ts`, and mappers in `auth-mapper.ts`
  validate invariants at runtime, throwing `AuthInvariantViolationError`
  on backend law violations.
- **Reason:** Generated types reflect transport contract (which fields MAY
  appear). Domain invariants (e.g. "requires_2fa=true ⇒ no access_token")
  are semantic, not transport — they belong in a separate layer. If the
  backend ever violates an invariant, the mapper surfaces it loudly
  instead of silently corrupting state.
- **Alternative considered:** Re-type the OpenAPI schema as discriminated
  union directly. Rejected — would be overwritten on next generation,
  and conflates transport with semantics.
- **Status:** Accepted
- **Detailed:** [ADR-003](./ADR-003-dto-mapper-domain.md)

### D-004: openapi-typescript installed with --legacy-peer-deps
- **Decision:** `openapi-typescript@7.x` is installed with
  `--legacy-peer-deps` because it peer-depends on `typescript@^5.x` but
  the project uses `typescript@6.0.3`.
- **Reason:** Empirically verified that the tool works correctly with
  TS 6 — it uses only stable Compiler API surface (`factory.createKeywordTypeNode`,
  `SyntaxKind.*`) unchanged since TS 4.x. The peer dep is conservative.
- **Alternative considered:** Downgrade to TS 5.x. Rejected — would block
  other project goals. Find an alternative generator. Rejected —
  openapi-typescript is the de-facto standard.
- **Status:** Accepted (temporary — re-evaluate when openapi-typescript
  bumps peer dep to ^6 or removes it)
- **Action item:** Periodically check openapi-typescript release notes;
  remove `--legacy-peer-deps` once upstream supports TS 6 officially.

---

## 2026-07-17 — Stabilization Sprint

### D-005: No @ts-nocheck policy
- **Decision:** `@ts-nocheck` is forbidden in new code. Existing files
  with `@ts-nocheck` (from the abandoned Phase 2-9) were excluded by
  resetting to Phase 1 baseline. Phase 2-redo will not use `@ts-nocheck`.
- **Reason:** `@ts-nocheck` disables TypeScript entirely for a file.
  The Phase 2-9 disaster showed that 481 files with `@ts-nocheck` is
  worse than no migration at all — it creates the illusion of migration
  while providing none of the safety.
- **Alternative considered:** Allow `@ts-nocheck` with a register entry.
  Rejected — register discipline failed in practice; the count grew
  from 0 to 481 in one session.
- **Status:** Accepted
- **Detailed:** [ADR-004](./ADR-004-no-ts-nocheck-policy.md)

### D-006: Regex patches that touch destructuring syntax are forbidden
- **Decision:** The pattern `paramName = value` → `paramName: Type = value`
  is FORBIDDEN in destructuring context. It changes semantics from
  "default value" to "rename + default value", making `paramName`
  undefined in the function body.
- **Reason:** This exact bug damaged 7+ files in Phase 2. ESLint caught
  it as `no-redeclare: 'unknown' is already defined`, but the errors
  were ignored because `@ts-nocheck` masked them and nobody read the diff.
- **Alternative considered:** Allow regex patches with mandatory review.
  Rejected — review discipline failed in practice.
- **Status:** Accepted
- **Replacement pattern:** Type the parent object:
  ```ts
  interface Options { x?: unknown; }
  const { x = null } = options as Options;
  ```

### D-007: tsc compensates for ESLint no-undef:off in .ts/.tsx
- **Decision:** ESLint `no-undef` rule is turned off for `.ts`/`.tsx`
  files. TypeScript's `tsc --noEmit` (TS2304: Cannot find name) performs
  the equivalent check.
- **Reason:** ESLint's `no-undef` doesn't understand TS type declarations
  (interfaces, types, DOM lib globals). It was reporting false positives
  for `BodyInit`, `RequestInit`, `NotificationOptions`, etc. TypeScript
  already checks for undefined references via the compiler.
- **Alternative considered:** Add all DOM types as ESLint globals.
  Rejected — duplicates `lib.dom.d.ts`, creates maintenance burden.
- **Verification:** Created test file with `undefinedVariable` reference;
  `tsc` caught it (TS2304). Created test file with DOM types; `tsc`
  resolved them via `lib: ["DOM", "DOM.Iterable"]` in tsconfig.
- **Status:** Accepted (verified equivalent)

### D-008: Mass-change preview rule
- **Decision:** Any script that modifies multiple files must be previewed
  on 5 sample files first, manually reviewed, then run on the rest.
  After the full run, 5 more random files are spot-checked.
- **Reason:** The Phase 2-9 regex disaster could have been caught by
  previewing on 5 files — the destructuring rename bug was visible in
  the first file it touched.
- **Alternative considered:** Ban all scripts. Rejected — some
  mechanical changes (e.g. `.js` → `.ts` rename) are safe with scripts
  if previewed.
- **Status:** Accepted

### D-009: Type Debt Register with categories
- **Decision:** All `any`, `as unknown as`, `@ts-expect-error`,
  `@ts-ignore`, `eslint-disable`, `TODO(TS-MIGRATION)`, `FIXME(TS)`
  occurrences must be registered with a category: ✅ External library,
  ⚠️ Legacy API, or ❌ To-compile (forbidden).
- **Reason:** Not all `any` is equal. `any` because a library ships no
  types is acceptable. `any` because the code is too complex to type is
  conditional. `any` to silence a type error is never acceptable.
  Categories make the debt actionable.
- **Alternative considered:** Single counter (e.g. "21 any"). Rejected —
  provides no signal for prioritization.
- **Status:** Accepted

### D-010: Reset to Phase 1 baseline (abandon Phase 2-9)
- **Decision:** Discard all work from Phase 2-9 (61 hooks, 5 contexts,
  45 UI components, 380 domain components, etc.) and restart from
  Phase 1 baseline using the new process.
- **Reason:** Phase 2-9 introduced 481 `@ts-nocheck` files, 7+ semantic
  damages from regex patches, and 96 masked ESLint errors. Fixing these
  in place would take longer than redoing with proper discipline.
- **Alternative considered:** Fix Phase 2-9 in place. Rejected —
  the damage was too widespread; the process that created it was broken.
- **Status:** Accepted
- **Cost:** ~6 hours of work discarded. Lesson learned: process > speed.
