# UX Remediation Plan

Static planning date: 2026-05-15
Repository: `C:\final`
Branch: `ux-remediation-plan-first-fix`
Scope: frontend UX planning plus one low-risk runtime UI fix. No backend, route, role, API, package, queue, payment, EMR, lab, auth, or patient-data semantics were changed.

## 1. Executive Summary

The frontend has a usable clinic operations foundation: a route registry SSOT, role-aware shell, macOS UI primitives, AppState primitives, and route/e2e coverage. The UX is still uneven because operational screens mix several UI layers, large role panels contain many workflows, and loading/empty/error states are inconsistent across pages and components.

Biggest user inconveniences:

- Some data-loading failures can look like empty data, which slows admin work and reduces trust.
- Role panels and specialty panels are large enough that staff workflows can hide primary actions below dense UI.
- Empty/error/loading state patterns vary by screen, so users cannot always tell whether data is loading, absent, filtered out, or failed.
- Forms and tables often rely on placeholders, disabled buttons, dense columns, or table empty rows instead of explicit state and recovery.
- Navigation is centralized, but route/sidebar changes have high blast radius and must not be treated as visual-only.

Highest-risk UX areas:

- Auth/RBAC behavior, route guards, role-home routing, queue fairness, payment status/API behavior, EMR/lab clinical state, diagnosis/prescription/AI medical copy, file upload, and patient medical data.

Safest first fixes:

- AppState polish in low-risk pages/components.
- Visible retryable errors where failures currently become empty states.
- Documentation and migration checklists.
- Small utility page state or copy fixes.

Live browser smoke was not run. This plan and first fix are based on static code inspection and requested validation commands.

## 2. Method and Limitations

Documents read:

- `frontend/FRONTEND_FUNCTION_CLASSIFICATION_AUDIT.md`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/APP_STATE_MIGRATION_BACKLOG.md`
- `UI_UX_audit_for_GPT.md`
- `AGENTS.md`
- `.cursorrules`
- `.agents/skills/clinic-frontend-design/SKILL.md`
- `.agents/skills/clinic-frontend-design/agents/openai.yaml`
- `frontend/package.json`

Files manually inspected:

- `frontend/src/pages/Activation.jsx`
- `frontend/src/pages/Search.jsx`
- `frontend/src/components/admin/ServiceAuditHistory.jsx`
- `frontend/src/components/ui/macos/AppState.jsx`
- `frontend/src/components/ui/macos/index.js`
- `frontend/src/components/admin/ServiceCatalog.jsx` references for `ServiceAuditHistory`

Static searches run:

| Search | Match lines | Files matched | Notes |
| --- | ---: | ---: | --- |
| UX/state patterns | 7857 | 410 | Loading, empty, error, disabled, aria, placeholder, `colSpan`. |
| Navigation/sidebar | 3161 | 284 | Route metadata, labels, icons, tooltips, sidebar/navigation. |
| Forms/validation | 10774 | 428 | Required fields, validation, disabled states, form controls. |
| Tables/lists | 2171 | 209 | Tables, filters, search, pagination, empty list states. |
| UI layer fragmentation | 18619 | 410 | MUI, Modern, inline style, Tailwind-like classes, macOS usage. |
| Role/critical surfaces | 7029 | 314 | Role panels, queue, payment, EMR, lab, AI, upload, pickup. |
| AppState/macOS state primitives | 244 | 45 | Existing `AppLoading`, `AppEmpty`, `AppError`, skeleton/alert states. |

Search commands used PowerShell counting equivalents around the mandatory `rg` patterns. This plan separates search-based inventory from manual inspection. Not every search match was manually reviewed.

Dev servers were not running. Browser smoke was not performed. Runtime behavior was inferred from source, not from a live clinic session.

Workflow guard note:

- The broad gate could not resolve the new plan document because it did not exist yet.
- The runtime fix was rerun through `agent_gate.py` with known root cause `frontend/src/components/admin/ServiceAuditHistory.jsx`.
- The gate returned a narrow override for that single runtime file; this plan document is the explicit primary output requested by the user.

## 3. UX Problem Taxonomy

Navigation/orientation:

- Route registry is strong, but hidden/contextual routes and query-tab role panels can confuse future cleanup.
- Sidebar/app shell changes are high risk because route access, nav visibility, and role homes are centralized.
- Current route clarity should be improved only through dedicated shell/route PRs with route tests.

Loading/empty/error:

- AppState primitives exist, but local loading text, empty rows, skeletons, direct alerts, and silent failures remain widespread.
- A failed fetch should not look like "no data".
- Empty states need context: not loaded, filtered out, no records yet, or no permission.

Forms/validation:

- Many fields depend on placeholder text and disabled buttons.
- Future fixes should add visible labels, field-level validation, required/optional clarity, and disabled-state reasons.
- Auth and clinical forms are high risk and need dedicated validation.

Tables/lists:

- Table empty rows using `colSpan` are common.
- Dense admin/clinical tables need scan hierarchy, status clarity, and consistent empty/error states.
- Shared table primitives are medium/high risk because many screens consume them.

Role workflow friction:

- Admin, Registrar, Doctor, Cashier, Lab, Patient, and specialty panels have very different workflow priorities.
- Monolithic panels make small changes hard to review.
- Each role-panel PR must choose one tab/state/action and one validation target.

Public flow friction:

- Landing and health pages are lower risk.
- Login is critical because auth/RBAC is sensitive.
- Queue and payment public flows are critical despite being public-facing.

Trust/safety copy:

- AI copy must keep draft/non-diagnosis framing.
- Payment result copy must not imply a state the backend has not confirmed.
- Queue errors must preserve backend-owned status and fairness semantics.

Accessibility:

- Icon-only buttons, custom card buttons, placeholder-only inputs, and disabled actions need review.
- Existing AppState primitives provide a more consistent baseline with `role`, `aria-live`, and clearer structure.

Visual consistency:

- `components/ui/macos` is canonical for new clinic app work.
- MUI, `Modern*`, `frontend/src/design-system`, inline styles, and utility classes remain legacy compatibility surfaces.
- No mass refactor; migrate one safe slice per PR.

Clinical operations speed:

- Staff screens need clear primary actions, scan-friendly states, and fast recovery.
- False empty states are especially costly because staff may stop looking for needed operational history.

Backend-contract/SSOT risk:

- Frontend must not become SSOT for auth, roles, queue, payment, EMR, lab, patient data, audit, activation, or AI outputs.

## 4. Findings by Product Zone

| Zone | User inconvenience | Evidence/file | Risk | Proposed fix | Validation |
| --- | --- | --- | --- | --- | --- |
| Public / Marketing UI | Lower operational risk, but public copy can drift from current app capabilities. | `Landing.jsx`, `landingContent.js` | Low | Copy-only review after route links are checked. | `git diff --check`, build if runtime changed. |
| Auth / Onboarding | Any visual ambiguity can affect trust, but semantics are critical. | `LoginFormStyled.jsx`, `ChangePasswordRequired.jsx`, `.cursorrules` | Critical | Dedicated auth UX review only; no opportunistic edit. | Auth tests, route smoke, manual auth smoke. |
| App Shell / Navigation | Current route/sidebar clarity matters, but changes have high blast radius. | `App.jsx`, `routeRegistry.js`, `routeSelectors.js` | High | Route/sidebar characterization tests before UI edits. | Route contract tests, build, route smoke. |
| Routing / Route SSOT | Hidden/contextual routes need documentation, not casual nav changes. | `routeRegistry.js`, `routeGuards.jsx` | Critical | Docs/test-only PR for hidden route contract. | Route tests and ownership tests. |
| Admin / Owner | Admin utilities mix CRUD, status, settings, and audit surfaces. | `AdminPanel.jsx`, `components/admin/*` | High/Critical | Start with small utility AppState fixes, not panel rewrites. | Targeted component test/build. |
| Registrar | Queue, payment, appointments, cancellation, and patient aggregation share one large surface. | `RegistrarPanel.jsx`, `AppointmentWizardV2.jsx` | Critical | Dedicated dossier before runtime edits. | Registrar smoke, queue/payment parity. |
| Doctor | Queue, visits, AI, and clinical actions are easy to slow down. | `DoctorPanel.jsx`, EMR hooks | Critical | Review-first; only one non-clinical slice later. | Clinical/doctor tests and smoke. |
| Cashier | Payment status and receipts must stay backend-owned. | `CashierPanel.jsx`, `components/payment/*` | Critical | Visual-only payment-result PR later, not status logic. | Payment e2e/manual callback smoke. |
| Lab | Lab queue/report states can imply clinical availability. | `LabPanel.jsx`, `components/laboratory/*` | Critical | Dedicated lab workflow review. | Lab smoke and build. |
| Patient | Patient data, pickup, and lab result display are sensitive. | `PatientPanel.jsx`, `PatientPickupView.jsx` | Critical | Only small visible state copy after token/data review. | Patient route/smoke with safe data. |
| EMR / Doctor workflows | Autosave/conflict/diagnosis/prescription states are safety-critical. | `components/emr-v2/*`, specialty panels | Critical | Review-first; no general UI cleanup. | EMR tests and manual clinical smoke. |
| Queue-sensitive flows | Queue UI affects fairness and expectations. | `QueueJoin.jsx`, `DisplayBoardUnified.jsx`, queue hooks/services | Critical | Test/copy characterization first. | Queue e2e/manual smoke. |
| Payment-sensitive flows | Payment result copy can mislead users about status. | `PaymentSuccess.jsx`, `PaymentCancel.jsx`, `PaymentManager.jsx` | Critical | Visual-only review after status contract check. | Payment e2e/manual callback smoke. |
| AI-assisted features | AI labels/disclaimers affect clinical trust. | `components/ai/*`, `admin-ai-settings` | High/Critical | Preserve draft/non-diagnosis framing. | AI copy review, route disclaimer tests. |
| Internal / utility pages | Good proving ground for AppState and accessibility fixes. | `Activation.jsx`, `Search.jsx`, `Health.jsx`, `Audit.jsx` | Low/Medium | Small AppState/label/retry slices. | Lint/test/build. |
| UI primitives / design system | Shared primitives can improve consistency but affect many pages. | `components/ui/macos/*`, `DESIGN_SYSTEM.md` | Medium/High | Dedicated primitive PRs only. | Primitive tests, build, visual smoke if run. |

## 5. Findings by Role

### Admin / Owner

Top tasks: user management, doctors, services, queue settings, activation, audit, payment provider settings, AI settings.

Friction points:

- Admin screens mix CRUD, audit, status, and configuration workflows.
- Some small components still have weak empty/error recovery.
- Large `AdminPanel.jsx` should not be the first runtime target.

Must not change:

- Roles, permissions, activation semantics, service payloads, queue settings, payment provider behavior, audit records.

Safe next UI slices:

- `ServiceAuditHistory.jsx` visible failure state.
- `Activation.jsx` label/copy/AppState polish.
- One admin utility empty state after endpoint review.

### Registrar

Top tasks: create appointments, register patients, manage queue entry, coordinate payment/cancellation.

Friction points:

- `RegistrarPanel.jsx` and `AppointmentWizardV2.jsx` are large and hard to scan.
- Queue/payment adjacency makes even copy changes risky.
- Staff needs clear next action and status ownership.

Must not change:

- Queue sorting, `queue_time`, payment status, cancellation endpoint choice, visit creation payloads.

Safe next UI slices:

- Docs/dossier first.
- Test characterization before runtime edits.

### Doctor

Top tasks: see queue, open visit, document encounter, review EMR, use AI assistance cautiously.

Friction points:

- Doctor and specialty panels combine queue, EMR, printing, AI, and clinical fields.
- Any unclear state can affect clinical workflow speed.

Must not change:

- Clinical state, diagnosis/prescription content, EMR autosave/conflict handling, AI medical meaning.

Safe next UI slices:

- Dedicated review of one non-clinical display state.
- No first-fix candidate in this PR.

### Cashier

Top tasks: review invoices, take payment, print receipts, confirm status.

Friction points:

- Payment states must be exact and backend-confirmed.
- Visual polish can accidentally imply payment success/failure.

Must not change:

- Payment status, receipt, mark-paid/refund endpoints, provider behavior.

Safe next UI slices:

- Payment result page copy/display only after contract check.

### Lab

Top tasks: see lab queue, manage reports/templates, print or update results.

Friction points:

- Lab state and report availability have clinical meaning.
- Queue/report merges need careful validation.

Must not change:

- Lab report status, result payloads, queue/report linking, print payloads.

Safe next UI slices:

- Dedicated lab review first.

### Patient

Top tasks: view patient panel, pickup data, see relevant status/results.

Friction points:

- Empty/error states must not leak or misstate patient data.
- Access/token failures need precise recovery copy.

Must not change:

- Patient access rules, tokens, displayed medical data semantics.

Safe next UI slices:

- PatientPickupView loading/error shell only after token review.

### Cardio / Derma / Dentist

Top tasks: specialty-specific clinical workflows, queue, EMR, print, AI-assisted sections.

Friction points:

- Specialty panels are large clinical-heavy monoliths.
- Staff scanning and clinical correctness are tightly coupled.

Must not change:

- Specialty medical fields, treatment plan/diagnosis meaning, queue, EMR, print payloads, AI text.

Safe next UI slices:

- Dedicated dossier per panel before runtime edits.

## 6. Top UX Issues

| Rank | Issue | User impact | Risk | Files | Proposed PR | Acceptance criteria |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | Failed admin audit-history load looks like no history. | Admin may believe no service changes exist. | Low | `ServiceAuditHistory.jsx` | First fix in this PR. | Failed fetch renders retryable `AppError`; empty history remains separate. |
| 2 | AppState usage is inconsistent across safe utility pages. | Users relearn loading/error patterns. | Low | `Activation.jsx`, `Search.jsx` | One page per PR. | State UI uses AppState and preserves behavior. |
| 3 | Search initial and no-result guidance could be clearer. | Staff may not know minimum useful query or next action. | Low | `Search.jsx` | Empty/error/accessibility polish. | Search API/navigation unchanged. |
| 4 | Activation page uses utility classes and weak control labeling. | Admin status filtering is less accessible. | Low | `Activation.jsx` | Label/disabled/AppState polish. | RoleGate, API calls, filters unchanged. |
| 5 | Table empty rows are widespread. | Empty vs filtered vs loading is unclear. | Medium | tables/admin components | One table state per PR. | Table semantics unchanged. |
| 6 | Route/sidebar hidden routes need characterization. | Future nav edits can hide important admin paths. | Medium/High | route tests/docs | Test-only PR. | Current hidden route contract documented. |
| 7 | Registrar workflow is dense and high-risk. | Slower appointment/queue/payment work. | Critical | `RegistrarPanel.jsx`, `AppointmentWizardV2.jsx` | Dossier first. | No runtime edit until slices are proven. |
| 8 | Queue copy and language consistency need review. | Public users may misunderstand queue state. | Critical | `QueueJoin.jsx` | Test/copy characterization first. | No queue semantics changed. |
| 9 | Payment result states need contract-checked clarity. | Users may misunderstand payment outcome. | Critical | payment pages/components | Visual-only PR after review. | No payment status/API changes. |
| 10 | AI clinical framing must remain explicit. | Medical trust/safety risk. | Critical | AI/EMR/sidebar surfaces | Copy review with clinical constraints. | Draft/non-diagnosis framing preserved. |

## 7. Safe Fix Backlog

Low-risk candidates:

| Title | Allowed files | Forbidden files | Risk | Effort | Validation | Acceptance criteria | Stop conditions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Service audit load failure state | `frontend/src/components/admin/ServiceAuditHistory.jsx` | Service API, catalog payloads, routes | Low | S | lint/test/build | Failed fetch shows retryable error; empty stays empty. | Need API contract change. |
| Activation control label polish | `frontend/src/pages/Activation.jsx` | API, RoleGate, routes | Low | S | lint/test/build | Select/refresh have clearer labels; filtering unchanged. | Changes activation semantics. |
| Search no-result guidance | `frontend/src/pages/Search.jsx` | Search API, navigation | Low | S | lint/test/build | No-result state helps refine query; routes unchanged. | Changes result grouping/navigation. |
| Search input accessibility | `frontend/src/pages/Search.jsx` | Search API, navigation | Low | XS | lint/test/build | Input/button labels and disabled reason clearer. | Behavior changes. |
| Health/Audit docs example | `frontend/APP_STATE_MIGRATION_BACKLOG.md` | Runtime files | Low | XS | `git diff --check` | Backlog reflects completed pilots. | Runtime changes needed. |
| Internal demo route notes | `frontend/UX_REMEDIATION_PLAN.md` or future docs | Runtime routes | Low | XS | `git diff --check` | Demo routes documented as internal. | Route change needed. |
| UI-layer inventory docs | docs only | Runtime files | Low | S | marker `rg` | Current layers documented. | Claims live verification. |
| Monolith decomposition dossier | docs only | Runtime files | Low | M | `git diff --check` | One role panel mapped for future slices. | Runtime changes requested. |
| Utility page empty copy | one small utility page | routes/API | Low | S | lint/test/build | Empty copy distinguishes filtered/no-data. | Domain logic appears. |
| AppState candidate checklist | `frontend/APP_STATE_MIGRATION_BACKLOG.md` | Runtime files | Low | S | marker `rg` | Candidates and risk stay current. | Needs runtime proof. |

Medium-risk candidates:

| Title | Allowed files | Forbidden files | Risk | Effort | Validation | Acceptance criteria | Stop conditions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Admin utility table empty state | one `components/admin/*` table component | `AdminPanel.jsx`, APIs | Medium | S | lint/test/build | Empty/filtered state clear. | CRUD payload touched. |
| `Appointments.jsx` empty/error polish | `frontend/src/pages/Appointments.jsx` | appointment API/flow | Medium | S | targeted tests/build | Filters/table unchanged. | Appointment behavior changes. |
| `PatientPickupView` shell error polish | `PatientPickupView.jsx` | token/data logic | Medium/High | S | build/manual smoke | Token handling unchanged. | Patient data semantics touched. |
| `ActivationSystem` load state | `ActivationSystem.jsx` | activation actions/API | Medium | S | build | Initial load canonical. | Create/revoke/extend touched. |
| `AISettings` initial load state | `AISettings.jsx` | provider save/test/copy | Medium | S | build | Provider behavior unchanged. | AI policy copy changes. |
| `CloudPrintingManager` empty grid | `CloudPrintingManager.jsx` | print/test API | Medium | S | build | Empty printer state clearer. | Print payload touched. |
| Route hidden/sidebar characterization | route tests only | route runtime | Medium | S | route tests | Current contract captured. | Runtime route edit requested. |
| Low-risk admin form required labels | one admin form component | backend validation/API | Medium | M | lint/test/build | Labels clearer; validation unchanged. | Field semantics touched. |

High-risk candidates:

| Title | Allowed files | Forbidden files | Risk | Effort | Validation | Acceptance criteria | Stop conditions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| App shell current route clarity | shell/sidebar files only | route registry unless test-scoped | High | M | route tests/build/smoke | Current route clearer. | Role/route visibility changes. |
| Payment result visual copy | `PaymentSuccess.jsx`, `PaymentCancel.jsx` | payment services/API/routes | High/Critical | S | payment e2e/manual smoke | Copy/display only. | Status semantics touched. |
| QueueJoin copy characterization | tests/docs first | `QueueJoin.jsx`, queue API | High/Critical | M | queue tests | Current behavior captured. | Queue semantics touched. |
| Role panel empty state slice | one role panel tab/state | broader panel/API | High | M | panel smoke/build | One state clearer. | Workflow behavior changes. |
| Shared table primitive empty state | shared table primitive | consumers without tests | High | M | broad tests/build | Consumers unaffected. | Table actions/sorting touched. |

Critical candidates:

| Title | Allowed files | Forbidden files | Risk | Effort | Validation | Acceptance criteria | Stop conditions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Auth/RBAC UX changes | auth file plus auth tests only | routes/roles unless scoped | Critical | M | auth tests/smoke | Auth semantics preserved. | Token/2FA/RBAC touched. |
| Queue domain UI behavior | dedicated queue slice | unrelated queue surfaces | Critical | L | queue e2e/manual smoke | Fairness and `queue_time` preserved. | Allocation/status touched. |
| Payment status/API UI | dedicated payment slice | unrelated payment files | Critical | L | payment e2e/manual smoke | Backend status remains SSOT. | Payment state logic touched. |
| EMR/lab clinical state UI | dedicated clinical slice | unrelated clinical files | Critical | L | clinical/lab validation | Clinical state unchanged. | Diagnosis/result semantics touched. |
| AI medical copy | one reviewed copy surface | EMR/domain logic | Critical | M | copy review/tests | Draft framing preserved. | Medical claim changes. |
| File upload/patient data UI | one upload/data surface | API/access rules | Critical | M | patient/security smoke | Access/data semantics unchanged. | Privacy contract unclear. |

## 8. First 10 Recommended PRs

| Order | Branch name | Exact scope | Files allowed | Files forbidden | Validation commands | Manual smoke |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `ux-service-audit-error-state` | Show retryable failure state for service audit history. | `ServiceAuditHistory.jsx` | API/routes/catalog behavior | `git diff --check`; frontend lint/test/build | Not required unless dev server is already up. |
| 2 | `docs-appstate-candidate-checklist` | Update AppState migration checklist with current risks. | `APP_STATE_MIGRATION_BACKLOG.md` | Runtime files | `git diff --check`; marker `rg` | None. |
| 3 | `ux-activation-control-labels` | Label/filter/refresh clarity in activation page. | `Activation.jsx` | API/RoleGate/routes | frontend lint/test/build | Optional. |
| 4 | `ux-search-empty-guidance` | Search no-result and initial guidance. | `Search.jsx` | Search API/navigation | frontend lint/test/build | Optional. |
| 5 | `test-hidden-route-nav-contract` | Characterize hidden/contextual route nav behavior. | route tests only | route runtime | route tests | None. |
| 6 | `ux-admin-utility-empty-state` | One low-risk admin utility table empty state. | one admin component | `AdminPanel.jsx`, API | frontend lint/test/build | Optional. |
| 7 | `docs-registrar-monolith-dossier` | Registrar/appointment wizard decomposition dossier. | docs only | runtime files | `git diff --check` | None. |
| 8 | `test-queue-join-copy-baseline` | Characterize current queue copy/accessibility. | queue tests only | queue runtime/API | targeted tests | None. |
| 9 | `ux-payment-result-visual-review` | Payment result copy/display only. | payment result pages | payment services/API/routes | payment e2e/build | Required. |
| 10 | `docs-specialty-panel-dossiers` | Dossiers for cardio/derma/dentist panels. | docs only | runtime files | `git diff --check` | None. |

## 9. Do Not Touch Yet List

These areas need dedicated review before runtime changes:

- `frontend/src/pages/RegistrarPanel.jsx`
- `frontend/src/components/wizard/AppointmentWizardV2.jsx`
- `frontend/src/pages/DoctorPanel.jsx`
- `frontend/src/pages/CardiologistPanelUnified.jsx`
- `frontend/src/pages/DermatologistPanelUnified.jsx`
- `frontend/src/pages/DentistPanelUnified.jsx`
- EMR and `frontend/src/components/emr-v2/*`
- `frontend/src/pages/LabPanel.jsx`
- `frontend/src/pages/CashierPanel.jsx` and payment status behavior
- `frontend/src/pages/QueueJoin.jsx` and queue fairness behavior
- `frontend/src/routing/routeGuards.jsx`, RBAC, route registry behavior
- File upload and patient medical data surfaces
- AI medical copy, diagnosis, prescription, and clinical recommendation text

## 10. First Fix Selection

Selected first fix:

- `frontend/src/components/admin/ServiceAuditHistory.jsx`

Why this is the safest high-value fix:

- It is one small admin utility component, not a role-panel monolith.
- It uses existing `components/ui/macos` AppState primitives.
- It does not change the service API call, request payload, route, role, catalog behavior, sorting, expansion, or displayed audit row fields.
- It improves real user convenience: a failed audit-history load no longer looks like empty history.
- It gives admins a direct retry action without leaving the service catalog flow.

Implementation:

- Add local `errorMessage` state.
- Clear the error when retrying.
- On fetch failure, preserve logging and render `AppError` with a retry button.
- Keep the existing `AppEmpty` state for true empty history.

Risk classification:

- Low runtime UI risk.
- Medium operational value because audit-history failures affect admin trust.
- Backend-contract sensitivity is low because no endpoint, payload, or data interpretation changed.

Stop conditions:

- Do not change `servicesService.getServiceHistory`.
- Do not change service catalog data shape.
- Do not change expansion behavior or audit row field formatting.
- Do not edit `ServiceCatalog.jsx` unless a compile error proves it is required.

## 11. Validation Plan

Docs-only:

- `git diff --check`
- Marker `rg` for plan headings and selected first fix.

Low-risk UI:

- `cd frontend && npm.cmd run lint:check`
- `cd frontend && npm.cmd run test:run`
- `cd frontend && npm.cmd run build`

Route/app shell:

- Route contract tests, route ownership tests, RBAC parity, build, route smoke.

Auth:

- Auth tests, route smoke, manual auth smoke.

Queue/payment:

- Targeted e2e and manual smoke. Protect queue fairness and payment status semantics.

EMR/lab/patient data:

- Dedicated clinical or lab workflow validation before runtime edits.

Scope inspection:

- Confirm `frontend/UX_REMEDIATION_PLAN.md` exists.
- Confirm exactly one runtime component changed.
- Confirm no backend, route, API, role, package, dependency, queue, payment, EMR, lab, or patient-data semantics changed.

## 12. Acceptance Criteria

This plan is complete when:

- Every finding category is tied to a file, route area, or product zone.
- Each candidate has risk and validation guidance.
- The first fix is justified and implemented in exactly one runtime component.
- High-risk areas are explicitly blocked from casual modification.
- Runtime changes outside the selected first fix are absent.
- Validation results are reported honestly.

First fix acceptance criteria:

- Failed service-history loads render a visible `AppError`.
- The retry action calls the same existing `loadHistory` flow.
- Empty history still renders `AppEmpty`.
- Loading still renders `AppLoading`.
- Audit row rendering, field formatting, expansion behavior, and API request remain unchanged.
