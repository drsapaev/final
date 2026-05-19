# UI/UX Hard Audit 2026-05-20 - Pass B: Role Workflow Usability

## Scope

Independent audit pass focused on role workflow usability. This pass reviewed tasks by role and did not use findings from Pass A or Pass C before completion.

Audit mode: report-only. No runtime, backend, frontend, API, RBAC, route, database, notification, or Telegram behavior was changed.

Primary skill: `clinic-ui-ux-master`.

References loaded:

- `.agents/skills/clinic-ui-ux-master/references/role-workflows.md`
- `.agents/skills/clinic-ui-ux-master/references/audit-matrix.md`
- `.agents/skills/clinic-ui-ux-master/references/implementation-slices.md`
- `.agents/skills/clinic-ui-ux-master/references/anti-patterns.md`
- `.agents/skills/clinic-ui-ux-master/references/report-templates.md`

Minimum route set reviewed:

- `/admin`
- `/admin/appointments`
- `/admin/audit`
- `/admin/user-select`
- `/registrar`
- `/doctor`
- `/cashier`
- `/lab`
- `/patient`
- `/queue/join`
- `/payment/success`
- `/payment/cancel`
- `/doctor/cardiology`
- `/doctor/dermatology`
- `/doctor/dentistry`

## Files And Routes Inspected

Role surfaces:

- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/pages/Appointments.jsx`
- `frontend/src/pages/Audit.jsx`
- `frontend/src/pages/UserSelect.jsx`
- `frontend/src/pages/RegistrarPanel.jsx`
- `frontend/src/pages/DoctorPanel.jsx`
- `frontend/src/pages/CashierPanel.jsx`
- `frontend/src/pages/LabPanel.jsx`
- `frontend/src/pages/PatientPanel.jsx`
- `frontend/src/pages/CardiologistPanelUnified.jsx`
- `frontend/src/pages/DermatologistPanelUnified.jsx`
- `frontend/src/pages/DentistPanelUnified.jsx`

Public flow surfaces:

- `frontend/src/pages/QueueJoin.jsx`
- `frontend/src/pages/PaymentSuccess.jsx`
- `frontend/src/pages/PaymentCancel.jsx`

Routing context:

- `frontend/src/routing/routeRegistry.js`

## Role Workflow Matrix

| Role/Flow | Main user task | Evidence inspected | Audit result |
| --- | --- | --- | --- |
| Admin | configure users, appointments, audit, settings | `AdminPanel.jsx`, `Appointments.jsx`, `Audit.jsx`, `UserSelect.jsx` | heavy page-local UI and legacy admin-support surfaces create consistency risk |
| Registrar | appointment and patient intake | `RegistrarPanel.jsx` | very large surface; workflow hierarchy needs focused role pass before broad edits |
| Doctor | clinical visit, current patient, EMR/reporting | `DoctorPanel.jsx` | critical flow has low accessibility marker density in static scan |
| Cashier | payment and receipt workflow | `CashierPanel.jsx` | payment-critical surface has no obvious accessibility markers in static scan |
| Lab | lab queues/results | `LabPanel.jsx` | smaller surface with visible loading/error handling patterns |
| Patient | patient-facing panel | `PatientPanel.jsx` | compact page, but low accessibility marker density |
| Queue | public QR join flow | `QueueJoin.jsx` | strong explicit state model, but complex public flow needs visual/keyboard QA |
| Payment success | payment confirmation/recovery | `PaymentSuccess.jsx` | comparatively strong status/error/loading semantics |
| Payment cancel | canceled payment recovery | `PaymentCancel.jsx` | recovery wording exists, but semantic alert/status treatment is weak |
| Specialty panels | cardiology, dermatology, dentistry | specialty unified pages | high-density clinical panels need separate role-specific audit slices |

## Positive Findings

### Payment success flow has explicit status handling

Evidence:

- `frontend/src/pages/PaymentSuccess.jsx` includes loading, error, success, and recovery states.
- It uses live/alert semantics in the payment lookup error path.
- It includes disabled action states while processing receipt-related actions.

Why it matters:

Payment success is a high-trust flow. The current structure is a better baseline than many other surfaces and should be preserved while improving visual consistency.

### Queue join flow has a clear state machine

Evidence:

- `frontend/src/pages/QueueJoin.jsx` includes states for loading, waiting, info, specialist selection, form, success, and error.
- It uses explicit form validation state and `aria-invalid`/`aria-describedby` patterns around patient input.
- It exposes public recovery actions when QR context is missing.

Why it matters:

The queue join flow is complex, but it already contains the right conceptual pieces. Future work should improve presentation and accessibility without replacing the queue logic.

### Lab panel has localized load/error handling

Evidence:

- `frontend/src/pages/LabPanel.jsx` has explicit load error messages and alert-style rendering.

Why it matters:

The lab flow looks like a safer candidate for a small usability refinement after the payment/queue critical public flows.

## Findings

### P1 - Cashier payment workflow needs a semantic/a11y pass

Evidence:

- `frontend/src/pages/CashierPanel.jsx`: 1482 lines, 99 inline style blocks, 0 static accessibility marker refs in the audit scan.

Impact:

Cashier workflow errors can directly affect payment confidence. A payment-critical panel should make current state, next action, disabled state, and error recovery unmistakable for keyboard and screen-reader users.

Safe direction:

Audit and improve only payment status messages, receipt action groups, disabled states, loading states, and error text. Do not change payment logic or API calls in the same PR.

### P1 - Doctor workflow has low visible accessibility evidence for a clinical-critical screen

Evidence:

- `frontend/src/pages/DoctorPanel.jsx`: 1449 lines, 100 inline style blocks, 1 static accessibility marker ref.

Impact:

Doctor workflow has high clinical risk because UI confusion can affect patient context, current encounter, EMR/reporting, or action selection.

Safe direction:

Start with current patient context, primary action hierarchy, loading/empty/error states, and keyboard navigation for the most common visit flow.

### P1 - Payment cancel is understandable but not strongly semantic

Evidence:

- `frontend/src/pages/PaymentCancel.jsx`: 123 lines, 16 inline style blocks, 0 static accessibility marker refs.
- Browser pass later can validate runtime semantics, but this independent source pass already shows weak semantic density.

Impact:

The flow tells the user that payment was not completed, but cancellation is a high-trust payment state. It should behave like a status/alert region with clear recovery actions and focus order.

Safe direction:

Make the canceled payment state a semantically announced status/alert, then verify keyboard order and mobile layout. Keep route and payment handling untouched.

### P1 - Large role panels make safe workflow review difficult

Evidence:

- `frontend/src/pages/RegistrarPanel.jsx`: 3585 lines
- `frontend/src/pages/AdminPanel.jsx`: 2837 lines
- `frontend/src/pages/DentistPanelUnified.jsx`: 3804 lines
- `frontend/src/pages/DermatologistPanelUnified.jsx`: 2549 lines
- `frontend/src/pages/CardiologistPanelUnified.jsx`: 2253 lines

Impact:

Large panels mix navigation, state, presentation, and workflow steps. Even when behavior is correct, it is hard to prove that the primary task path remains visible, accessible, and safe after edits.

Safe direction:

Do not rewrite these panels. Use small PRs that isolate one workflow area: header/action bar, empty state, patient context panel, table/filter row, status badge family, or one specialty-specific card group.

### P2 - Admin-support pages still carry legacy workflow feel

Evidence:

- `frontend/src/pages/Appointments.jsx`: 7 `legacy-` refs
- `frontend/src/pages/Audit.jsx`: 6 `legacy-` refs
- `frontend/src/pages/UserSelect.jsx`: 7 `legacy-` refs

Impact:

Admin/support users see inconsistent interaction density and visual language across closely related tasks.

Safe direction:

Migrate shared shell, filters, table states, and empty states first. Avoid changing appointment/audit data contracts.

### P2 - Patient panel needs a dedicated patient-readability pass

Evidence:

- `frontend/src/pages/PatientPanel.jsx`: compact page, low accessibility marker density.

Impact:

Patient-facing UI needs especially clear language, large touch targets, readable status, and forgiving recovery. Static source review is not enough to certify this route.

Safe direction:

Run a focused browser pass with actual or seeded patient session data before modifying behavior.

## Role-Specific Backlog

### P0

No confirmed P0 from static role workflow review alone. Authenticated browser QA is still required before declaring role panels safe.

### P1

- Cashier payment workflow semantic/a11y review.
- Doctor current-patient and visit action hierarchy review.
- Payment cancel semantic status/alert and recovery actions.
- Queue join public flow keyboard/mobile recovery QA.
- Authenticated visual QA for protected role panels before broad UI work.

### P2

- Admin-support legacy page convergence.
- Registrar panel workflow hierarchy decomposition.
- Specialty panel visual hierarchy slices by specialty.
- Patient panel patient-readability pass.

### P3

- Copy consistency for public recovery states.
- Icon, button density, and microcopy polish after P1/P2 fixes.

## Phased Plan

1. Payment cancellation recovery semantics.
2. Queue join public flow status/action visual consistency.
3. Cashier payment state and receipt action accessibility.
4. Doctor current patient and primary action hierarchy.
5. Registrar intake workflow audit slice.
6. Admin-support legacy surface convergence.
7. Specialty panels one at a time.

## Validation Plan

For follow-up implementation PRs:

- test the exact role route touched
- preserve route registry, RBAC, API, and backend contracts
- run `frontend` lint/build and targeted tests when components change
- run browser QA at mobile/tablet/desktop/wide viewports
- verify keyboard tab order and visible focus around the changed workflow
- verify empty, loading, error, forbidden, and disabled states for the changed workflow

## Stop Conditions

Stop and split the work if:

- a role workflow fix requires changing backend permissions or API contracts
- a payment/queue fix changes business logic instead of presentation semantics
- a large panel change touches more than one role task family
- authentication or seeded data is missing for browser verification
- a proposed UI change hides clinical/payment/queue status behind decorative UI
