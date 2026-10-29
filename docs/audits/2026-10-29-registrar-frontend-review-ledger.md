# Registrar frontend — cumulative code-review ledger

> **Status:** IN PROGRESS / documentation-only; not a release or approval report.
> **Started:** 2026-10-29 (Asia/Tashkent). **Repository:** `drsapaev/final`.
> **Baseline:** `main` at `9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1`.
> **Review type:** source inspection via GitHub file reads. **No runtime or automated tests were executed for these findings.**
> **Purpose:** retain every actionable review finding with source evidence, reproduce/verify it, and agree on a safe remediation sequence **after** the review inventory is complete.

## Execution boundary

- Mode: `direct_execute` for **one narrow, documentation-only review-ledger change**. No queue/clinical/payment behavior is modified.
- Authorized write scope: **this Markdown document only** on the dedicated audit branch; review evidence is read-only.
- Excluded: application source and tests, backend, migrations, configuration, production, deployments, live data, merges, and changes to queue ownership/fairness.
- Stop point: do not implement fixes in this audit PR. Reassess ownership and run the repository-mandated gate(s) before any later implementation PR involving queue/clinical/payment contracts.
- Validation for this documentation change: fetch the committed file and inspect the PR diff. CI and runtime tests remain unexecuted until explicitly checked; do not infer a green build.

## Status and severity legend

- `SOURCE-OBSERVED`: the described code path exists in the frozen baseline.
- `REPRO-PENDING`: an end-to-end or focused regression test still must demonstrate the user-visible effect.
- `CONFIRMED`: focused failing test or equivalent verified reproduction; **none yet**.
- `RESOLVED`: regression is fixed with tests and reviewed in a **separate fix PR**; no entries resolved yet.
- Severity P0–P3 is **provisional** until verification and triage; no P0/P1 demonstrated during this first pass.

## Findings index

| ID | Severity (provisional) | Area | Source observation | Status | Proposed fix/test batch |
| --- | --- | --- | --- | --- | --- |
| REG-FE-001 | P2 | Worklist row activation | Click/keyboard row activation invokes a logger-only callback rather than record preview | SOURCE-OBSERVED / REPRO-PENDING | Batch A: table interaction |
| REG-FE-002 | P2 | All-departments search | Search results omit the service-normalization step present in unfiltered results | SOURCE-OBSERVED / REPRO-PENDING | Batch B: pure worklist presentation |
| REG-FE-003 | P3 | Localization | `filteredAppointments` memo uses a translated fallback but does not depend on it | SOURCE-OBSERVED / REPRO-PENDING | Batch B: pure worklist presentation |

### REG-FE-001 — Row activation does not open details (P2 candidate)

**Code evidence:**

- [WorklistView.tsx L289–L301](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/views/WorklistView.tsx#L289-L301) passes an `onRowClick` callback that calls only `logger.info(...)`; comment indicates a details dialog could be opened, but no detail action is invoked.
- [EnhancedAppointmentsTable.tsx L211–L223](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/components/tables/EnhancedAppointmentsTable.tsx#L211-L223) forwards a supplied `onRowClick` to `DataTable`, making the callback part of the row-activation contract.
- [useRegistrarRowActions.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/useRegistrarRowActions.ts) already supplies `openRecordPreview` and a working `view` action for explicit action controls.

**Potential impact:** a registrar clicks/keyboard-activates a row expecting to inspect the record, but nothing visible happens. Do not conflate this with the separate explicit `view` action, which may still work.

**Reproduction / fail-first test:** render `WorklistView` with one synthetic record; trigger the table row with a pointer and Enter/Space; assert an intentional details action occurs (or, if UX contract specifies non-actionable rows, assert row activation/focus affordance is absent). Check actual `DataTable` semantics and accessibility before selecting the remedy.

**Preferred remediation:** after verifying the intended UX, either wire row activation to `openRecordPreview` through an explicit prop/callback, or remove the misleading row-activation wiring. Preserve separate `view` and `edit` workflows, and verify keyboard activation and click-on-action-button behavior.

### REG-FE-002 — Search bypasses all-departments service normalization (P2 candidate)

**Code evidence:**

- [registrarWorklistRows.ts L275–L294](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarWorklistRows.ts#L275-L294) returns `sortRegistrarRowsForPresentation(searched)` directly when `searchQuery` is present. The no-query path applies `filterServicesByDepartment(..., null, services)` to each row.
- [registrarServiceFilter.ts](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/registrar/registrarServiceFilter.ts) explicitly has a fallback from `queue_numbers[].service_name` when the aggregate `services` array is empty.

**Potential impact:** for an aggregated patient with no `services` array but queue numbers that can provide service codes, all-departments view may show services *before* entering a search term and omit them *after* searching. Only a **display** problem is alleged; there is no evidence of a backend queue/appointment mutation.

**Reproduction / fail-first test:** in `registrarWorklistRows.test.ts`, use synthetic data with a stable patient key, `queue_numbers` containing a service-name/code resolvable by `toServiceCode`, and `services: []`. Compare `computeRegistrarWorklistRows` with `searchQuery: ''` versus a query matching the patient; assert that the displayed services are equal. First establish that this data shape is supported by the current adapter/API.

**Preferred remediation:** apply the *same* presentation-only postprocessing to searched and unsearched aggregated rows, without changing queue identity, grouping, timing, ordering or server-owned routing. Regression test both search branches and multi-record aggregates.

### REG-FE-003 — Localized fallback not tracked by memo (P3 candidate)

**Code evidence:**

- [RegistrarPanel.tsx L259–L268](https://github.com/drsapaev/final/blob/9ef2c9376ada9a7c3049ad595d9f2fb5bd6b64b1/frontend/src/pages/RegistrarPanel.tsx#L259-L268) passes `tI18n('registrarPanel.rp_unknown_patient')` into `computeRegistrarWorklistRows`, while the `useMemo` dependency array omits that resolved translated string and the translator/language.

**Potential impact:** when UI language changes without a concurrent change to the listed dependencies, a record lacking the patient display name may retain a fallback label in the previous language. Scope is limited to display text, not patient identity or data persistence.

**Reproduction / fail-first test:** render a registrar worklist with one **synthetic** record whose patient name is unavailable; change locale while keeping appointment/service/profile references stable; assert the fallback text updates. Do not add a test that passes solely because data reload changes an unrelated dependency.

**Preferred remediation:** compute `fallbackPatientLabel` as a render value and include that value in the memo dependency array; keep translated fallbacks separate from canonical patient data.

## Review coverage

### Actually inspected in first pass (source reads; not an exhaustive audit)

- `frontend/src/pages/RegistrarPanel.tsx`
- `frontend/src/pages/registrar/registrarWorklistRows.ts`
- `frontend/src/pages/registrar/registrarServiceFilter.ts`
- `frontend/src/pages/registrar/useRegistrarWizard.ts`
- `frontend/src/pages/registrar/useRegistrarNavigation.ts`
- `frontend/src/pages/registrar/useRegistrarRowActions.ts`
- `frontend/src/pages/registrar/useRegistrarHotkeys.ts`
- `frontend/src/pages/registrar/views/WorklistView.tsx`
- `frontend/src/pages/registrar/views/RegistrarDialogsLayer.tsx`
- `frontend/src/components/tables/EnhancedAppointmentsTable.tsx`
- `frontend/src/utils/registrarAggregation.ts`
- `frontend/src/utils/logger.ts`
- `frontend/src/api/registrar.ts`
- Focused source-contract / worklist test files were partially inspected to identify regression-test owners.

### Outstanding review slices (not yet audited)

1. Registration and editing: `AppointmentWizardV2`, wizard state, save/error paths and patient lookup.
2. Queue read-model: `useRegistrarWorklistData`, `registrarQueueAdapter`, `QueueView`, queue profile navigation; read-only comparison with canonical backend DTOs and ADR-001.
3. Record actions: `useRegistrarActions`, status/identity/error handling, cancellation, call/complete/reschedule.
4. Display and usability: `WelcomeView`, table renderers, modal accessibility, loading/empty/error states.
5. API/privacy/performance: registrar API adapter, outbound requests, auth boundaries, PHI-safe diagnostics, existing tests/e2e.

Any further findings receive the next stable ID (`REG-FE-004`, etc.), a source-SHA anchor, an impact scenario, a reproduction/test, and a status. If refuted, mark **NOT A BUG** with evidence rather than silently deleting the row.

## Remediation plan — execute only after review triage

1. **Freeze and verify:** complete relevant review slices; fetch latest `main` and compare the old anchored evidence with the new baseline. Confirm each candidate using a fail-first focused unit/component/e2e test; close false positives without editing application code.
2. **Triage risk and ownership:** address confirmed P0/P1 before P2/P3. If any fix touches queue ownership/fairness, clinical lifecycle, payment truth, authentication or API contracts, run the repository-required execution gate and inspect canonical source, ADRs and backend tests before editing.
3. **Batch A — interaction:** `REG-FE-001`; decide desired row-click UX, add keyboard/pointer regression, smallest implementation change, review, CI.
4. **Batch B — view model/localization:** `REG-FE-002` + `REG-FE-003` only if they remain purely presentation-level and independently tested; avoid altering backend SSOT and identity.
5. **Additional batches:** one bounded fix PR per validated domain/root cause; never introduce a speculative blanket refactor or mix unrelated source fixes into this ledger PR.
6. **Validation:** relevant Vitest components/contracts, `tsc`/ESLint, affected Playwright flows with synthetic data, relevant queue contract tests, PR quality gates, `git diff --check`, and code review. Record **actual commands/results**; do not claim tests passed without execution.
7. **Closure:** update each ledger row with root cause, test evidence, fix PR/commit SHA, review outcome, and resolution status. Keep this audit PR as the index; merge it only when repository review and CI policy permit. Do not deploy as part of this audit.

## Change log

| Date | Ledger revision | Added / updated | Verification |
| --- | --- | --- | --- |
| 2026-10-29 | Initial | Three provisional source-observed findings; coverage, scope and remediation plan | GitHub source reads only; remote commit/PR diff verification pending |

## End-of-review acceptance criteria

- Every finding has a unique stable ID and a final disposition: `CONFIRMED`, `NOT A BUG`, `DUPLICATE`, or `RESOLVED`.
- Confirmed defects have focused regression tests; no test exists merely to silence a failure.
- Changes preserve backend queue fairness, identities, clinical/payment ownership, RBAC, and privacy guardrails.
- Fix PRs are reviewed, all required CI is green, and the final ledger links to those PRs/commits.
- This document by itself is **not evidence** that the registrar workflow is safe or fully audited.
