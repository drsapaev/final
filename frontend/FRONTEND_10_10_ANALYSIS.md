# Frontend 10/10 Analysis Matrix

Date: 2026-05-15

Repository scope: `frontend`

Method: static repo inspection, targeted source search, and manual review of representative frontend files. This document is for planning. It does not claim browser verification, production UX validation, or full clinical workflow review.

## Executive Summary

Current static frontend maturity score: **6.8 / 10.0**.

The frontend has a strong base: a centralized route registry, a canonical macOS UI layer, a documented UI Layer Contract, route contract tests, recent fixes for login, queue language, AI sidebar disclaimers, payment result pages, and shared AppState primitives.

The path to 10/10 is now less about one-off P0 fixes and more about controlled consolidation:

- migrate repeated loading, empty, and error states one safe screen at a time;
- reduce MUI and legacy design-system expansion;
- split the largest role panels into safer workflow slices;
- add visual, accessibility, and route smoke gates for critical flows;
- keep clinical workflows behavior-preserving while improving UI consistency.

The biggest current blockers to 10/10 are monolithic role panels, mixed UI layers, incomplete adoption of shared state primitives, and limited visual/E2E coverage for role-heavy workflows.

## Scoring Rubric

Scores use a 10.0-point scale:

| Score | Meaning |
| --- | --- |
| 9.5-10.0 | Production-excellent: canonical, tested, accessible, visually robust, low known risk. |
| 8.0-9.4 | Strong: minor inconsistencies remain, but the system is predictable. |
| 6.0-7.9 | Usable: clear strengths, but fragmentation or missing validation creates risk. |
| 4.0-5.9 | Meaningful risk: workflows work, but maintainability or UX safety is fragile. |
| <4.0 | Unstable or unsafe: unclear ownership, broken flows, or poor user trust. |

## Evidence Base

### Manually inspected

- `AGENTS.md`
- `.cursorrules`
- `UI_UX_audit_for_GPT.md`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/APP_STATE_MIGRATION_BACKLOG.md`
- `frontend/package.json`
- `frontend/src/App.jsx`
- `frontend/src/routing/routeRegistry.js`
- `frontend/src/routing/__tests__/routeContract.test.js`
- `frontend/src/components/ui/macos/index.js`
- `frontend/src/components/ui/macos/AppState.jsx`
- `frontend/src/components/ui/macos/__tests__/AppState.test.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/components/auth/LoginFormStyled.jsx`
- `frontend/src/pages/QueueJoin.jsx`
- `frontend/src/pages/PaymentSuccess.jsx`
- `frontend/src/pages/PaymentCancel.jsx`
- `frontend/src/pages/Health.jsx`
- `frontend/src/pages/Audit.jsx`
- `frontend/src/pages/Activation.jsx`
- `frontend/src/pages/RegistrarPanel.jsx`
- `frontend/src/pages/PatientPanel.jsx`
- `frontend/src/pages/LabPanel.jsx`

### Search commands run

```powershell
rg "@mui|design-system|components/ui/macos|MacOS|Modern|Tailwind|className=|style=\{\{" frontend/src
rg "AppLoading|AppEmpty|AppError|Loading|Spinner|Skeleton|Empty|No data|Нет данных|Ошибка|Не удалось|Загрузка" frontend/src
rg "aria-|role=|tabIndex|onClick|button|label|htmlFor" frontend/src/pages frontend/src/components
rg "locale|i18n|lang|language|Навбат|очеред|диагноз|заключ|чернов" frontend/src
rg "describe\(|it\(|test\(|render\(|screen\." frontend/src
rg "SIDEBAR_PRESETS|routes|path:|element:" frontend/src/routing frontend/src/App.jsx
```

### Key search-derived facts

| Finding | Evidence |
| --- | --- |
| Route registry is centralized. | `routeRegistry.js` has 72 `path:` entries and 72 `component:` entries. |
| Route tests exist. | `routeContract.test.js` checks unique routes, role home routes, public route roles, compatibility redirects, setup redirects, and AI sidebar disclaimer copy. |
| macOS UI is widely used. | `rg -l "components/ui/macos|ui/macos" frontend/src` found 121 files. |
| Runtime MUI remains. | `rg -l "@mui|Mui" frontend/src/pages frontend/src/components` found 16 runtime/example component files. |
| AppState primitives exist but adoption is early. | `AppLoading`, `AppEmpty`, and `AppError` are used in `Health.jsx`, `Audit.jsx`, the primitive file, exports, and tests. |
| Repeated state patterns remain. | Search found 238 files with loading patterns, 90 with empty patterns, and 278 with error patterns. |
| Legacy state UI remains. | Search found 62 files with `MacOSLoadingSkeleton`, `MacOSEmptyState`, `legacy-error`, `empty-state`, or common no-data text. |
| Test files exist but are not comprehensive for UI flows. | 63 `*.test.*` or `*.spec.*` files found under `frontend/src`. |
| Large monolith panels remain. | Largest pages include `RegistrarPanel.jsx` 193 KB, `DentistPanelUnified.jsx` 164 KB, `AdminPanel.jsx` 129 KB, `DermatologistPanelUnified.jsx` 123 KB, `CardiologistPanelUnified.jsx` 105 KB. |

## Frontend Class Scorecard

| Class | Score | Current state | 10/10 target |
| --- | ---: | --- | --- |
| 1. UI layer consistency / design system | 7.0 | macOS UI is canonical and documented; recent payment pages moved away from MUI. Legacy design-system, MUI, inline styles, utility classes, and page-local patterns remain. | New app UI only expands macOS primitives; legacy layers shrink through small PRs; no new MUI in app pages. |
| 2. App shell, routing, navigation UX | 8.1 | Central route registry, role home tests, setup redirect tests, sidebar presets, AI sidebar disclaimer. App shell uses macOS theme and sidebar. | Add role smoke coverage and visual checks for shell/sidebar across key roles. |
| 3. Role workflow UX | 6.3 | Role-specific areas exist, but the largest workflows are monolithic and contain mixed state, demo fallback, and local translation logic. | Split by workflow slices; each role surface has predictable states, actions, and validation. |
| 4. Forms, tables, filters, data density | 6.4 | Many tables/forms are functional and dense enough for staff work. No canonical `Field` or `DataTable` yet; many page-local forms and table empty states remain. | Shared form/table primitives with consistent labels, validation, empty rows, pagination, and keyboard behavior. |
| 5. Loading / empty / error / forbidden states | 6.7 | `AppLoading`, `AppEmpty`, `AppError` exist and have pilots in `Health.jsx` and `Audit.jsx`. Many local state patterns remain. | Page-level and panel-level states use AppState primitives unless a local pattern is explicitly justified. |
| 6. Accessibility and keyboard UX | 6.5 | Good signs in landing, queue, route guards, AppState, and many aria labels. Some div-based button patterns and unverified role-panel keyboard behavior remain. | Critical flows pass manual keyboard and screen-reader smoke; icon-only controls have accessible names. |
| 7. Responsive layout and visual robustness | 6.4 | Landing and some public flows are responsive; app shell has responsive constraints. Large panels and dense tables need visual regression and mobile/tablet smoke. | Critical role screens have desktop/tablet/mobile smoke and no overlapping or clipped UI states. |
| 8. Copy, i18n, clinical safety microcopy | 7.0 | Queue fallback language and AI sidebar disclaimer were fixed. Locale files exist. Some large panels still keep local translation maps and demo/fallback text. | Product-wide language rules are predictable; AI/clinical copy consistently marks draft/support behavior. |
| 9. Performance, bundle, runtime stability | 6.2 | Vite, lazy routes, and Speed Insights dependency exist. Large panels, MUI remnants, and broad imports increase runtime and bundle risk. Build was not run for this analysis. | Bundle budgets, route-level smoke, and chunk review prevent regressions. Large role panels are split gradually. |
| 10. Testing, QA gates, maintainability | 6.8 | Route contracts, AppState tests, queue accessibility tests, API guardrails, and Vitest scripts exist. Visual regression and E2E coverage are not yet systematic. | CI gates cover lint, unit, route contracts, critical E2E, visual smoke, and accessibility checks by workflow risk. |

Average class score: **6.7 / 10.0**.

## Product-zone Heatmap

| Zone | Score | Evidence | Main gap to 10/10 |
| --- | ---: | --- | --- |
| Public landing | 8.0 | Landing has tests, accessibility labels, localized content, and polished product copy. | Needs visual regression and responsive browser proof. |
| Login / onboarding | 8.6 | `/login` resolves to `LoginFormStyled`; legacy `Login.jsx` delegates to canonical form. | Auth flow remains high-risk and should keep contract/smoke tests around 2FA and redirects. |
| Public queue / QR join | 7.7 | Language consistency and accessibility were improved; queue logic is rich and public-facing. | High complexity; needs browser smoke and locale policy guardrails before further UI changes. |
| Payments | 7.1 | Success/cancel result pages now use macOS UI and broken support navigation was fixed. | PaymentWidget/Cashier payment surfaces still contain mixed UI and high domain risk. |
| App shell / sidebar / navigation | 8.0 | Central registry, sidebar presets, macOS shell, route contract tests, AI disclaimer tests. | Need visual/role smoke and sidebar polish without route architecture rewrites. |
| Admin workflows | 6.4 | Many admin components use macOS primitives; route ownership is clear. | `AdminPanel.jsx` is large; admin utilities still have local state patterns and some MUI. |
| Registrar workflows | 5.7 | Rich registrar workflow exists with queue/payment integration. | `RegistrarPanel.jsx` is very large and mixes demo fallback, local i18n, queue, payment, and state logic. |
| Doctor / specialty workflows | 5.9 | Separate doctor and specialty panels exist; AI disclaimer is present in sidebar. | Clinical-heavy monoliths and MUI specialty components need dedicated review. |
| Lab workflows | 6.0 | `LabPanel.jsx` delegates to lab workbench components and has clear API error copy. | Lab report generator still uses MUI; lab domain is clinical-heavy and needs careful slice-by-slice UI work. |
| EMR / AI-assisted clinical UI | 6.1 | AI assistant has draft notice and sidebar disclaimer. | Clinical copy, AI output boundaries, and MUI/legacy UI need a dedicated safety review. |
| Patient-facing UI | 6.8 | Patient panel avoids fake lab results and explains unavailable real data. | Patient UI still mixes Tailwind-style classes/local empty states; family relations use MUI. |
| Technical/status pages | 8.2 | `Health.jsx` and `Audit.jsx` use AppState primitives. | `Activation.jsx` is the next low-risk state migration candidate. |

Average product-zone score: **6.9 / 10.0**.

Overall score uses 60% frontend class score and 40% product-zone score: **6.8 / 10.0**.

## Current Strengths

- Canonical UI direction is now documented in `frontend/DESIGN_SYSTEM.md`.
- `components/ui/macos` has broad adoption and exports the core app primitives.
- Route ownership is centralized in `routeRegistry.js`.
- Route contract tests protect key routing invariants and AI sidebar disclaimer copy.
- P0 trust issues from the earlier audit were addressed:
  - canonical login screen;
  - queue fallback language consistency;
  - AI sidebar disclaimer.
- Payment success/cancel result pages are closer to the macOS UI layer.
- `AppLoading`, `AppEmpty`, and `AppError` exist, are exported, and have focused tests.
- Two runtime pilots (`Health.jsx`, `Audit.jsx`) prove AppState primitives can be used safely.

## Top Risks And Gaps

1. **Large role panels limit safe iteration.**
   - `RegistrarPanel.jsx`, `DentistPanelUnified.jsx`, `AdminPanel.jsx`, `DermatologistPanelUnified.jsx`, and `CardiologistPanelUnified.jsx` are large enough that UI fixes can easily become behavior changes.

2. **UI layer fragmentation remains.**
   - Runtime MUI still appears in 16 page/component files.
   - Legacy `design-system`, `Modern*`, inline styles, and Tailwind-like utility classes still exist.

3. **AppState adoption is early.**
   - Only `Health.jsx` and `Audit.jsx` are migrated pilots.
   - Repeated loading/error/empty state patterns remain across pages and components.

4. **Clinical-heavy flows need dedicated safety review.**
   - EMR, lab, registrar, queue, and doctor workflows mix clinical or payment semantics with dense UI.

5. **Testing is strongest around routing and selected components, not full workflows.**
   - Route contract tests are good.
   - Visual regression, browser smoke, and role happy-path E2E are still not systematic.

6. **Performance risk is structural.**
   - Lazy routing helps, but huge panels and remaining MUI-heavy components keep bundle/runtime risk high.

## Roadmap To 10/10

### P0: Preserve Trust And Baseline Safety

Goal: no regression in already-fixed P0 trust flows.

Recommended PRs:

1. Add a docs/CI checklist that treats these as protected frontend flows:
   - `/login`
   - `/queue/join`
   - `/payment/success`
   - `/payment/cancel`
   - AI sidebar/nav labels
2. Add lightweight route/smoke tests only if existing test harness supports them without backend changes.
3. Keep all auth, queue, payment, AI, and role behavior changes out of visual cleanup PRs.

Acceptance criteria:

- No route path changes.
- No backend/API contract changes.
- Existing route contract tests remain green.
- Each protected flow has at least static or component-level regression coverage.

### P1: Finish Canonical UI Primitives Adoption

Goal: turn the current UI contract into real repeatable runtime UI.

Recommended PR sequence:

1. `Activation.jsx` AppState migration.
   - Use `AppLoading`, `AppEmpty`, and `AppError`.
   - Do not change activation API calls, role gate, or filters.

2. `Search.jsx` AppState migration.
   - Replace local no-results and error states.
   - Preserve query behavior and navigation.

3. `PatientPickupView.jsx` AppState migration.
   - Replace page-level loading/error/empty blocks.
   - Preserve route params and patient data rendering.

4. `Appointments.jsx` AppState migration.
   - Replace `legacy-error` and empty table state.
   - Preserve filters, columns, and request behavior.

5. `ServiceAuditHistory.jsx` or another small admin utility migration.
   - Prefer one small admin component per PR.

6. Define `Field` only when migrating one concrete form.
   - Do not build a broad form framework first.

7. Define `DataTable` only when migrating one concrete low-risk table.
   - Do not change shared table semantics globally.

Acceptance criteria:

- One runtime page/component per PR.
- Imports from `frontend/src/components/ui/macos`.
- No backend, API, route, guard, role, or domain logic changes.
- Lint/test/build run for runtime PRs unless explicitly scoped narrower.

### P2: Reduce UI Layer Fragmentation

Goal: shrink legacy UI surface without mass refactor.

Recommended PR sequence:

1. Inventory all runtime MUI users and classify by risk:
   - low-risk admin/status;
   - payment-adjacent;
   - queue-adjacent;
   - clinical-heavy.

2. Migrate one low-risk MUI component to macOS UI.
   - Candidate pool: non-clinical admin utility or example-only surface.
   - Do not start with EMR, lab report generation, queue manager, or dental treatment planning.

3. Convert page-local large inline style blocks only when touching the screen for a specific state or workflow.

4. Stop expansion of `frontend/src/design-system` in new app-page work.

Acceptance criteria:

- MUI runtime file count trends downward.
- No package removal until all runtime usage is gone.
- No new parallel component systems.

### P3: Role Panel Decomposition

Goal: make large panels maintainable while preserving clinical workflows.

Recommended order:

1. Registrar panel dedicated dossier.
   - Map data loading, demo fallback, queue events, payment actions, tabs, and local i18n.
   - Do not refactor yet.

2. Registrar first slice.
   - Extract one purely visual subpanel or state block.
   - Preserve queue/payment semantics.

3. Admin panel slice.
   - Extract one low-risk admin table/section or migrate one AppState block.

4. Doctor/specialty panels.
   - Use clinical safety review before UI migration.

5. Lab workflows.
   - Start with visual-only state rendering; leave report generation and print semantics untouched.

Acceptance criteria:

- Each PR states the role, workflow, and stop condition.
- No cross-role refactor.
- No changes to clinical, payment, queue, or lab data semantics.

### P4: Verification And 10/10 Gates

Goal: make future score improvements mechanically checkable.

Recommended work:

1. Add critical route browser smoke:
   - login;
   - queue join;
   - payment success/cancel;
   - admin shell;
   - one registrar path;
   - one doctor path;
   - one lab path.

2. Add visual regression snapshots for:
   - app shell/sidebar;
   - AppState primitives;
   - payment result pages;
   - public queue join;
   - one table-heavy admin page.

3. Add accessibility smoke:
   - keyboard tab order;
   - focus visible;
   - alert/status live regions;
   - icon-only buttons have names.

4. Add bundle review:
   - run `npm run build`;
   - run `npm run analyze` if stable;
   - track MUI-heavy chunks and large role-panel chunks.

Acceptance criteria:

- Critical workflows have repeatable smoke coverage.
- Accessibility regressions are caught before merge.
- Bundle regressions are visible in PR review.

## Top 10 Next PR Targets

| Rank | Target | Type | Risk | Why next | Do not change |
| --- | --- | --- | --- | --- | --- |
| 1 | `frontend/src/pages/Activation.jsx` | AppState migration | Low | Already identified in backlog; simple loading/error/empty states. | Activation API, RoleGate, filters. |
| 2 | `frontend/src/pages/Search.jsx` | AppState migration | Low | Local error/no-results blocks, non-role page. | Search API, result grouping, navigation. |
| 3 | `frontend/src/pages/PatientPickupView.jsx` | AppState migration | Low/Medium | Page-level loading/error blocks. | Route params, patient token/session logic. |
| 4 | `frontend/src/pages/Appointments.jsx` | AppState migration | Medium | `legacy-error` and table empty state. | Filters, columns, fallback request behavior. |
| 5 | `frontend/src/components/admin/ServiceAuditHistory.jsx` | AppState migration | Low | Small audit-history panel with existing macOS state components. | History fetch/rendering semantics. |
| 6 | MUI runtime inventory doc | Planning | Low | Needed before removing MUI safely. | Runtime code. |
| 7 | One low-risk MUI component migration | UI slice | Medium | Reduces UI fragmentation. | Package deps, domain behavior. |
| 8 | `Field` primitive pilot | Primitive + one form | Medium | Forms need consistency, but only with a concrete form. | Global form rewrite. |
| 9 | `DataTable` primitive pilot | Primitive + one table | Medium | Table empty/error states repeat widely. | Shared table behavior unless target is explicit. |
| 10 | Registrar panel dossier | Analysis | High | Necessary before any large registrar refactor. | Runtime code in dossier PR. |

## Product-zone Notes

### Public landing

Landing has strong product copy, localized content, accessible nav labels, and tests. It is closer to marketing quality than the internal panels are to operational UI consistency. The next gain is not more visual polish; it is visual regression and responsive proof.

### Login / onboarding

The double-login risk is resolved at the frontend level: `/login` points to `LoginFormStyled`, and legacy `Login.jsx` delegates to it. Future changes must preserve 2FA and token flow contracts.

### Public queue / QR join

The queue join page is public, complex, and behavior-sensitive. Language consistency was improved, and there are visible accessibility patterns such as alerts and labels. Do not use it for broad UI cleanup; only dedicated public-queue prompts should touch it.

### Payments

Payment result pages are now visually closer to the app style. Deeper payment UI remains in cashier and payment widgets. Future changes must be visual-only unless a payment-domain prompt explicitly allows behavior changes.

### App shell / navigation

The route registry and route tests are one of the frontend's strongest assets. Improvements should focus on smoke coverage and sidebar consistency, not route architecture rewrites.

### Admin

Admin has broad functionality and many macOS components, but also large files and repeated state patterns. Good candidates are small admin utilities, not the whole `AdminPanel.jsx`.

### Registrar

Registrar is the highest-risk UX area outside clinical EMR/lab. It combines queue, appointments, payments, demo fallback, local language maps, and large UI blocks. It needs a dossier before any runtime refactor.

### Doctor / specialty

Doctor and specialty panels are clinical-heavy and large. Changes need clinical workflow review, especially where AI, diagnosis, templates, photos, or treatment plans are involved.

### Lab

Lab has better component boundaries than some role panels, but report generation and print behavior are domain-sensitive. State rendering can be improved first; report semantics should be preserved.

### EMR / AI

AI draft labeling improved in nav and assistant surfaces. A dedicated EMR/AI safety pass should check all places where AI can suggest diagnosis, treatment, ICD codes, image analysis, or clinical text.

### Patient-facing

Patient panel has a good trust posture by not showing fake lab results. The main gaps are consistency with canonical AppState and removal of mixed utility/local styles over time.

### Technical/status pages

Health and Audit are good pilots. Activation is the next safest target to keep momentum without touching clinical workflows.

## What Not To Do

- No mass panel refactor.
- No backend/API contract changes in UI cleanup PRs.
- No route, role, guard, auth, queue, payment, EMR, or lab behavior changes as part of visual cleanup.
- No new MUI usage in app pages.
- No new parallel design-system layer.
- No package removals until runtime usage is proven gone.
- No global table/form rewrites without a concrete low-risk pilot.
- No claims of accessibility or visual completion without browser or automated evidence.

## Future Validation Strategy

For documentation-only PRs:

```powershell
git diff --check
rg "Frontend 10/10 Analysis|Scorecard|Product-zone Heatmap|No mass panel refactor" frontend
git status --short
```

For runtime UI PRs:

```powershell
cd frontend
npm run lint:check
npm run test:run
npm run build
```

For visual or UX-sensitive PRs, add browser smoke or Playwright checks for the touched route. If backend is required, state whether the smoke was skipped or run against a real local backend.

## Recommended Prompt #11

Implement a small AppState migration for `frontend/src/pages/Activation.jsx`.

Guardrails:

- Use `AppLoading`, `AppEmpty`, and `AppError` from `frontend/src/components/ui/macos`.
- Modify exactly one runtime page.
- Preserve `getActivationStatus`, `/activation/list`, `RoleGate`, filters, table columns, and refresh behavior.
- Do not touch backend, routes, auth, payment, queue, EMR, lab, or role panels.
- Validate with `git diff --check`, `npm run lint:check`, `npm run test:run`, and `npm run build`.

This is the smallest useful next step toward 10/10 because it continues the proven Health/Audit pilot path without entering role-panel or clinical-heavy territory.
