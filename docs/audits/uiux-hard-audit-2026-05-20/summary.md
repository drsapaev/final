# UI/UX Hard Audit 2026-05-20 - Summary

## Scope

This summary combines three independent `clinic-ui-ux-master` audit passes only after each pass was completed:

- Pass A: design-system drift
- Pass B: role workflow usability
- Pass C: browser visual/accessibility QA

Audit mode: report-only. No runtime, backend, frontend, API, RBAC, route, database, notification, Telegram, or payment behavior was changed.

Reports:

- `docs/audits/uiux-hard-audit-2026-05-20/pass-a-design-system-drift.md`
- `docs/audits/uiux-hard-audit-2026-05-20/pass-b-role-workflow-usability.md`
- `docs/audits/uiux-hard-audit-2026-05-20/pass-c-browser-visual-accessibility.md`

## Overall Verdict

The frontend has usable foundations and several good state-handling patterns, especially around payment success and queue error recovery. The main issue is not one broken component. The main issue is UI layer fragmentation:

- large role pages act as local design systems
- older `legacy-` surfaces still exist in admin/support flows
- MUI islands remain in active product areas
- public queue/payment flows are visually stable but still need semantic hardening
- protected role panels could not be browser-certified without safe auth/session data

This is not a rewrite recommendation. The safest path is a sequence of small PR slices, each limited to one role, surface, or state family.

## Deduplicated Backlog

### P0

No confirmed P0 was found in this audit. However, protected role panels remain uncertified in browser QA because auth/session data was unavailable. That unknown should block any claim that the full clinical UI is visually clean.

### P1

1. Authenticated role-panel browser QA is missing for Admin, Registrar, Doctor, Cashier, Lab, Patient, and specialty routes.
2. Cashier payment workflow needs semantic/a11y review before further payment UI polish.
3. Doctor current-patient and visit action hierarchy needs a focused clinical usability pass.
4. Public payment cancel state needs stronger semantic status/alert treatment.
5. Queue join public flow should get a focused status/action/mobile/keyboard pass.
6. Large role panels need small design-system convergence slices, not broad rewrites.
7. MUI islands in active product areas need a no-new-MUI policy and staged migration.

### P2

1. Admin-support pages still contain legacy classes and older visual patterns.
2. Consumer files still bypass design tokens with hardcoded colors and local style decisions.
3. Registrar panel needs workflow hierarchy decomposition.
4. Specialty panels need one-specialty-at-a-time visual hierarchy passes.
5. Patient panel needs patient-readability and accessibility verification with real/seeded session data.

### P3

1. Public recovery-state copy and button grouping can be made more consistent.
2. Icon/button density can be polished after P1/P2 semantics are fixed.
3. Screenshot artifact capture should be standardized for UI PRs.

## Top 10 Fixes

1. Add a safe local authenticated QA path for protected role panels and rerun browser matrix.
2. Improve `PaymentCancel` semantic status/alert behavior and recovery action accessibility.
3. Stabilize `QueueJoin` public status containers, recovery actions, and mobile action layout.
4. Audit and harden `CashierPanel` payment states, receipt actions, disabled states, and error messaging.
5. Audit `DoctorPanel` current patient context, primary action hierarchy, and keyboard path.
6. Migrate `Appointments`, `Audit`, and `UserSelect` away from legacy visual classes.
7. Converge `AdminPanel` cards, section headers, action bars, and status badges.
8. Split Registrar UI improvement into workflow slices instead of page-wide edits.
9. Tackle specialty panels separately: cardiology, dermatology, then dentistry.
10. Inventory active MUI usage and enforce no-new-MUI for clinic runtime UI unless explicitly approved.

## Recommended Small PR Slices

### PR-UX-1 - Payment cancel semantics

Scope:

- `frontend/src/pages/PaymentCancel.jsx`
- optional small shared status component only if one already exists and fits

Goal:

- add semantic status/alert treatment
- verify keyboard order and mobile layout
- do not touch payment logic or API calls

Validation:

- `frontend` lint/build
- browser screenshots for `/payment/cancel` at `375x812`, `768x1024`, `1280x800`, `1920x1080`

### PR-UX-2 - Queue join public recovery states

Scope:

- `frontend/src/pages/QueueJoin.jsx`
- existing token/component usage only

Goal:

- converge missing-QR, error, success, and recovery action presentation
- keep queue state machine and service calls untouched

Validation:

- `frontend` lint/build
- browser QA for missing-QR state
- happy-path QA only if safe QR fixture is available

### PR-UX-3 - Admin-support legacy cleanup

Scope:

- `frontend/src/pages/Appointments.jsx`
- `frontend/src/pages/Audit.jsx`
- `frontend/src/pages/UserSelect.jsx`
- existing CSS/token files only if needed

Goal:

- remove visible legacy drift from shared admin-support surfaces
- preserve data loading, route registry, and permissions

Validation:

- `frontend` lint/build
- browser QA for protected routes with authenticated admin session

### PR-UX-4 - Cashier payment workflow accessibility

Scope:

- `frontend/src/pages/CashierPanel.jsx`

Goal:

- improve payment status, disabled, loading, receipt, and error state semantics
- do not change payment business logic

Validation:

- authenticated cashier browser QA
- keyboard/focus checks
- lint/build

### PR-UX-5 - Doctor current-patient workflow

Scope:

- `frontend/src/pages/DoctorPanel.jsx`

Goal:

- clarify current patient context and primary visit actions
- improve visible focus and empty/loading/error states

Validation:

- authenticated doctor browser QA
- lint/build

### PR-UX-6 - Design-system convergence for one large panel at a time

Scope:

- start with `frontend/src/pages/AdminPanel.jsx`, then specialty panels separately

Goal:

- replace local stat card, badge, header, action bar, and empty-state styles with existing design-system primitives
- no route/API/RBAC behavior changes

Validation:

- focused screenshots before/after
- lint/build

## Evidence Highlights

Static evidence:

- `AdminPanel.jsx`: 260 inline style blocks
- `DentistPanelUnified.jsx`: 265 inline style blocks
- `DermatologistPanelUnified.jsx`: 171 inline style blocks
- `CardiologistPanelUnified.jsx`: 121 inline style blocks
- `QueueJoin.jsx`: 124 inline style blocks
- `CashierPanel.jsx`: 99 inline style blocks
- `DoctorPanel.jsx`: 100 inline style blocks
- `Appointments.jsx`, `Audit.jsx`, and `UserSelect.jsx` retain `legacy-` references
- active MUI islands exist in queue, dashboard, dental, payment, lab, and theme files

Browser evidence:

- tested 15 routes across 4 viewports
- protected role routes redirected to `/login`
- login redirect path had no detected horizontal overflow, console errors, failed network responses, or unnamed icon buttons
- `/queue/join` missing-QR state had no detected overflow/errors and exposed alert/live regions
- `/payment/success` missing-payment state had no detected overflow/errors and exposed alert/live regions
- `/payment/cancel` had no detected overflow/errors but had `alerts=0`

## Remaining Unknowns

- actual protected role panels were not browser-inspected because safe auth/session data was unavailable
- queue join happy path needs valid clinic QR context or a safe fixture
- payment success happy path needs a valid payment ID/test fixture
- role-specific empty/loading/error/forbidden states need seeded data for full certification
- MUI migration cost should be estimated per component family before implementation

## Expected Runtime Impact Of Fix Strategy

This audit does not change runtime behavior. The recommended implementation strategy should keep review risk low because each PR slice is limited to one surface or state family.

Expected benefit after follow-up PRs:

- fewer one-off style decisions in role panels
- more predictable visual QA
- better mobile and keyboard behavior in high-trust public flows
- easier branch protection confidence because UI changes become smaller and more testable

## Follow-Up Recommendations

1. Create a safe authenticated browser QA fixture for local Admin, Registrar, Doctor, Cashier, Lab, Patient, and specialty roles.
2. Add a project rule that UI PRs touching role panels must include screenshot evidence for at least mobile and desktop.
3. Add a no-new-MUI policy for clinic runtime UI unless explicitly approved.
4. Convert static drift searches into an optional report-only workflow or npm script after the first fixes land.
5. Keep every UI cleanup PR narrow: one role, one route family, or one state family.
