# UI/UX Hard Audit 2026-05-20 - Pass A: Design-System Drift

## Scope

Independent static audit pass focused on design-system drift only. This pass did not use findings from Pass B or Pass C.

Audit mode: report-only. No runtime, backend, frontend, API, RBAC, route, database, notification, or Telegram behavior was changed.

Primary skill: `clinic-ui-ux-master`.

References loaded:

- `.agents/skills/clinic-ui-ux-master/references/design-system-convergence.md`
- `.agents/skills/clinic-ui-ux-master/references/design-token-inventory.md`
- `.agents/skills/clinic-ui-ux-master/references/audit-matrix.md`
- `.agents/skills/clinic-ui-ux-master/references/anti-patterns.md`
- `.agents/skills/clinic-ui-ux-master/references/report-templates.md`

Minimum project context inspected:

- `AGENTS.md`
- `.cursorrules`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/THEME_SYSTEM_GUIDE.md`
- `frontend/src/routing/routeRegistry.js`
- active role panels and public clinical/payment/queue pages under `frontend/src/pages`

## UI Layer Inventory

The frontend is not a single clean UI layer yet. It has several overlapping style systems:

- design-system docs and tokens under `frontend/DESIGN_SYSTEM.md`, `frontend/THEME_SYSTEM_GUIDE.md`, `frontend/src/design-system`, and `frontend/src/theme`
- macOS-style and unified CSS layers under `frontend/src/styles`
- legacy CSS classes, mostly around older admin/scheduler/audit/user-select surfaces
- MUI islands in selected dashboard, queue, dental, payment, lab, and theme files
- large page-local inline style systems in role panels and AI/admin components

Route registry anchors inspected:

- `/queue/join` in `frontend/src/routing/routeRegistry.js`
- `/payment/success` in `frontend/src/routing/routeRegistry.js`
- `/payment/cancel` in `frontend/src/routing/routeRegistry.js`
- `/admin`, `/admin/appointments`, `/admin/audit`, `/admin/user-select`
- `/registrar`, `/doctor`, `/cashier`, `/lab`, `/patient`
- `/doctor/cardiology`, `/doctor/dermatology`, `/doctor/dentistry`

## Static Inventory Evidence

Top `style={{` hotspots in `frontend/src`:

| File | Count |
| --- | ---: |
| `frontend/src/pages/DentistPanelUnified.jsx` | 265 |
| `frontend/src/pages/AdminPanel.jsx` | 260 |
| `frontend/src/components/ai/RiskAssessment.jsx` | 188 |
| `frontend/src/components/analytics/AIAnalytics.jsx` | 179 |
| `frontend/src/components/ai/SmartScheduling.jsx` | 177 |
| `frontend/src/components/ai/DrugInteractionChecker.jsx` | 171 |
| `frontend/src/pages/DermatologistPanelUnified.jsx` | 171 |
| `frontend/src/components/ai/QualityControl.jsx` | 158 |
| `frontend/src/components/ai/AnalyticsInsights.jsx` | 155 |
| `frontend/src/components/ai/VoiceToText.jsx` | 146 |
| `frontend/src/components/admin/DepartmentManagement.jsx` | 127 |
| `frontend/src/pages/QueueJoin.jsx` | 124 |
| `frontend/src/pages/CardiologistPanelUnified.jsx` | 121 |
| `frontend/src/components/admin/GroupPermissionsManager.jsx` | 120 |
| `frontend/src/pages/DoctorPanel.jsx` | 100 |
| `frontend/src/pages/CashierPanel.jsx` | 99 |

Active route/page drift snapshot:

| Surface | Lines | Inline styles | Legacy refs | MUI refs | A11y refs |
| --- | ---: | ---: | ---: | ---: | ---: |
| `frontend/src/pages/AdminPanel.jsx` | 2837 | 260 | 0 | 0 | 11 |
| `frontend/src/pages/RegistrarPanel.jsx` | 3585 | 84 | 1 | 0 | 6 |
| `frontend/src/pages/DoctorPanel.jsx` | 1449 | 100 | 0 | 0 | 1 |
| `frontend/src/pages/CashierPanel.jsx` | 1482 | 99 | 0 | 0 | 0 |
| `frontend/src/pages/LabPanel.jsx` | 442 | 6 | 0 | 0 | 1 |
| `frontend/src/pages/PatientPanel.jsx` | 147 | 7 | 0 | 0 | 0 |
| `frontend/src/pages/QueueJoin.jsx` | 1610 | 124 | 0 | 0 | 9 |
| `frontend/src/pages/PaymentSuccess.jsx` | 456 | 23 | 0 | 0 | 2 |
| `frontend/src/pages/PaymentCancel.jsx` | 123 | 16 | 0 | 0 | 0 |
| `frontend/src/pages/CardiologistPanelUnified.jsx` | 2253 | 121 | 0 | 0 | 2 |
| `frontend/src/pages/DermatologistPanelUnified.jsx` | 2549 | 171 | 0 | 0 | 1 |
| `frontend/src/pages/DentistPanelUnified.jsx` | 3804 | 265 | 0 | 0 | 31 |

Top `legacy-` hotspots:

| File | Count |
| --- | ---: |
| `frontend/src/styles/macos.css` | 19 |
| `frontend/src/pages/Scheduler.jsx` | 8 |
| `frontend/src/pages/Appointments.jsx` | 7 |
| `frontend/src/pages/UserSelect.jsx` | 7 |
| `frontend/src/pages/Audit.jsx` | 6 |
| `frontend/src/components/layout/Nav.jsx` | 3 |
| `frontend/src/components/laboratory/LabResultsManager.jsx` | 2 |
| `frontend/src/pages/RegistrarPanel.jsx` | 1 |

Top MUI import hotspots:

| File | Count |
| --- | ---: |
| `frontend/src/components/queue/OnlineQueueManager.jsx` | 11 |
| `frontend/src/components/dashboard/Dashboard.jsx` | 11 |
| `frontend/src/components/dental/TreatmentPlanner.jsx` | 9 |
| `frontend/src/components/ai/MCPMonitor.jsx` | 9 |
| `frontend/src/components/examples/UnifiedCard.tsx` | 8 |
| `frontend/src/components/dental/ToothModal.jsx` | 8 |
| `frontend/src/pages/PaymentTest.jsx` | 3 |
| `frontend/src/theme/augmentation.ts` | 3 |
| `frontend/src/components/examples/UnifiedButton.tsx` | 3 |

Hardcoded color and CSS function hotspots exist both in token/theme files and in consumer files. Token files are expected to contain raw color values; consumer hotspots need convergence review. Notable consumer files include:

- `frontend/src/components/wizard/AppointmentWizard.css`
- `frontend/src/components/emr-v2/DoctorTemplatesPanel.css`
- `frontend/src/components/filters/ModernFilters.css`
- `frontend/src/pages/Landing.css`
- `frontend/src/components/AppointmentsTable.jsx`
- `frontend/src/pages/Search.jsx`
- `frontend/src/pages/DisplayBoardUnified.jsx`
- `frontend/src/components/buttons/ModernButton.css`
- `frontend/src/components/forms/ModernSelect.css`
- `frontend/src/components/auth/LoginFormStyled.jsx`

## Findings

### P1 - Large role panels are acting as local design systems

Evidence:

- `frontend/src/pages/AdminPanel.jsx`: 260 inline style blocks
- `frontend/src/pages/DoctorPanel.jsx`: 100 inline style blocks
- `frontend/src/pages/CashierPanel.jsx`: 99 inline style blocks
- `frontend/src/pages/RegistrarPanel.jsx`: 84 inline style blocks
- `frontend/src/pages/DentistPanelUnified.jsx`: 265 inline style blocks
- `frontend/src/pages/DermatologistPanelUnified.jsx`: 171 inline style blocks
- `frontend/src/pages/CardiologistPanelUnified.jsx`: 121 inline style blocks

Impact:

Role-critical surfaces can drift visually and behaviorally because spacing, color, status, hover, and layout decisions are repeated locally instead of flowing through the canonical design system.

Safe direction:

Start with non-behavioral convergence slices: cards, section headers, status badges, empty states, action bars, and button groups. Do not change data flow, role permissions, route contracts, or service calls in the same PR.

### P1 - Queue and payment public flows still bypass tokens in places

Evidence:

- `frontend/src/pages/QueueJoin.jsx`: 124 inline style blocks
- `frontend/src/pages/PaymentSuccess.jsx`: 23 inline style blocks
- `frontend/src/pages/PaymentCancel.jsx`: 16 inline style blocks

Impact:

These are high-trust public flows. Inconsistent status colors, spacing, and action hierarchy can create clinical/payment misunderstanding even when the underlying logic is correct.

Safe direction:

Converge status containers, recovery actions, and mobile action stacks first. Keep queue and payment logic untouched.

### P1 - MUI islands remain in active product areas

Evidence:

- `frontend/src/components/queue/OnlineQueueManager.jsx`: 11 MUI import refs
- `frontend/src/components/dashboard/Dashboard.jsx`: 11 MUI import refs
- `frontend/src/components/dental/TreatmentPlanner.jsx`: 9 MUI import refs
- `frontend/src/components/dental/ToothModal.jsx`: 8 MUI import refs
- `frontend/src/components/payment/PaymentWidget.jsx`: MUI import refs
- `frontend/src/components/laboratory/LabReportGenerator.jsx`: MUI import refs

Impact:

MUI components can carry typography, spacing, elevation, focus, and density rules that do not match the project tokens. This makes role workflows feel mixed even when each component is individually polished.

Safe direction:

Do not remove MUI in one sweep. Add a no-new-MUI policy for clinic runtime UI, then migrate one component family at a time.

### P2 - Legacy classes persist in admin/support surfaces

Evidence:

- `frontend/src/pages/Scheduler.jsx`: 8 `legacy-` refs
- `frontend/src/pages/Appointments.jsx`: 7 `legacy-` refs
- `frontend/src/pages/UserSelect.jsx`: 7 `legacy-` refs
- `frontend/src/pages/Audit.jsx`: 6 `legacy-` refs
- `frontend/src/styles/macos.css`: 19 `legacy-` refs

Impact:

Admin/support screens can look older than clinical role panels, which increases perceived inconsistency and makes visual QA less predictable.

Safe direction:

Migrate one low-risk page at a time, starting with shared shells, filter bars, tables, empty states, and toolbar controls.

### P2 - Consumer CSS still has hardcoded color/style hotspots

Evidence:

Consumer files with raw colors or CSS color functions include `AppointmentWizard.css`, `AppointmentsTable.jsx`, `Search.jsx`, `DisplayBoardUnified.jsx`, `ModernButton.css`, `ModernSelect.css`, and several EMR/filter/auth files.

Impact:

Even when tokens exist, bypassing them makes dark/light theme behavior, contrast hardening, and visual consistency more expensive.

Safe direction:

Separate expected token definitions from consumer violations. Then migrate consumer colors to semantic variables one file family at a time.

## First 5 Safest Convergence Slices

1. `PaymentCancel` recovery state semantics and tokenized action layout.
2. `QueueJoin` public error/success/status containers and button styles.
3. `Appointments`, `Audit`, and `UserSelect` legacy class cleanup as one admin-support visual slice.
4. `AdminPanel` stat cards, action bars, and status badges only.
5. `CashierPanel` payment status/receipt action styling only.

## Validation Plan

For any follow-up implementation PR derived from this pass:

- run `npm run lint:check` in `frontend` if frontend code changes
- run `npm run test:run -- --coverage` in `frontend` if logic/components change
- run `npm run build` in `frontend`
- run targeted browser QA for the changed routes at `375x812`, `768x1024`, `1280x800`, and `1920x1080`
- verify no route contract, API, RBAC, backend, migration, notification, Telegram, or payment logic changed unless explicitly scoped

## Stop Conditions

Stop and split the work if a proposed fix:

- touches clinical/payment/queue logic while trying to fix styles
- introduces a new UI framework or duplicate token system
- changes route registry, RBAC, API payloads, or backend behavior
- needs authenticated role data that is not available for browser verification
- requires broad rewrites of large role panels instead of a small visual slice
