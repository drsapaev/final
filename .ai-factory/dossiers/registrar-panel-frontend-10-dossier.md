# RegistrarPanel Frontend 10/10 Dossier

Generated: 2026-05-15
Mode: dossier
Scope: first runtime registrar refactor planning only

## Purpose

This dossier is the execution boundary for the first registrar frontend 10/10 slice. `RegistrarPanel.jsx` is role-, queue-, payment-, and workflow-sensitive, so runtime changes must start from a visual-only extraction with no route, API, queue, payment, RBAC, or clinical behavior changes.

## Canonical Anchors

- `frontend/FRONTEND_10_10_ANALYSIS.md`: current frontend score is 6.8/10 with target 9.5-10/10.
- `frontend/DESIGN_SYSTEM.md`: macOS UI layer is the canonical runtime UI layer.
- `frontend/src/components/ui/macos`: canonical primitives for touched UI.
- `frontend/src/components/ui/macos/AppState.jsx`: canonical loading, empty, and error primitives.
- `frontend/src/routing/routeRegistry.js`: registrar route contract and legacy redirect ownership.
- `frontend/src/routing/__tests__/routeContract.test.js`: route contract validation.
- `frontend/APP_STATE_MIGRATION_BACKLOG.md`: state cleanup order and AppState guidance.

## Route Contract

- Route id: `registrar-home`.
- Path: `/registrar`.
- Component: `RegistrarPanel`.
- Auth: role-scoped.
- Allowed roles: `Admin`, `Registrar`.
- Home roles: `registrar`, `receptionist`.
- Owner: `clinical.registrar`.
- Legacy redirect: `/registrar-panel`.
- Layout: hidden sidebar, registrar preset, page title `Registrar Panel`.

Do not change route paths, role names, route owner metadata, layout metadata, or compatibility redirects in the first registrar slice.

## Workflow Map

`frontend/src/pages/RegistrarPanel.jsx` is a large monolithic screen that owns:

- Date and query state from `useSearchParams`.
- View switching through `view`, legacy `tab`, `welcome`, and `queue`.
- Patient deep-link loading from a URL patient id.
- Appointment loading, demo fallback, refresh, and auto-refresh cooldown.
- Queue profile loading through `ModernTabs` and queue tag filtering.
- Search, status, active department/tab, date, and pagination filtering.
- Aggregated patient rows through `aggregateRegistrarPatients`.
- Queue actions, payment actions, cancel actions, print ticket flow, force majeure flow, and appointment wizard completion refresh.
- Local Russian/Uzbek i18n through `localStorage.getItem('ui_lang')`.
- Welcome dashboard, quick actions, queue manager view, table view, and supporting dialogs.

## API Boundaries

RegistrarPanel currently calls or depends on these API boundaries:

- `api.get('/registrar/doctors')`
- `api.get('/registrar/services')`
- `api.get('/registrar/queue-settings')`
- `api.get('/registrar/departments?active_only=true')`
- `api.get('/registrar/queues/today', { params: { target_date } })`
- `fetch('/api/v1/patients/:id')`
- `fetch('/api/v1/departments/active')`
- `POST /api/v1/registrar/queue/:id/start-visit`
- `POST /api/v1/registrar/visits/:id/complete`
- `POST /api/v1/appointments/:id/complete`
- `POST /api/v1/registrar/visits/:id/mark-paid`
- `POST /api/v1/registrar/queue/entry/:id/mark-paid`
- `POST /api/v1/appointments/:id/mark-paid`
- `POST /visits/:id/status`
- `POST /online-queue/entries/:id/cancel`
- `PUT /appointments/:id`
- `DELETE /appointments/:id`

Do not modify these endpoints, request payloads, fallback order, token behavior, retry behavior, or local optimistic updates in a visual cleanup PR.

## State And Query Params

High-sensitivity state:

- `currentView`, `activeTab`, `searchQuery`, `statusFilter`, selected date, and patient URL id.
- `dataSource`, `appointments`, `appointmentsLoading`, pagination, selected rows, and cooldown refs.
- `queueProfiles`, `dynamicDepartments`, doctors, services, and department filtering.
- `showPaymentDialog`, `showPaymentManager`, `cancelDialogOpen`, `printDialog`, `wizardOpen`, `forceMajeureModal`.
- Local paid override TTL and status transition state.

Do not change query parameter names, default view logic, URL replacement behavior, refresh cadence, queue sorting, aggregation behavior, or selected-row semantics in the first slice.

## High-Risk No-Touch Areas

- `loadAppointments` and demo/API fallback behavior.
- Queue tag/profile resolution, department service matching, queue sorting, and `queue_time`.
- `aggregateRegistrarPatients` usage and deduplication assumptions.
- Payment, cancel, start-visit, complete, no-show, and mark-paid actions.
- `PaymentDialog`, `PaymentManager`, `CancelDialog`, `PrintDialog`, `AppointmentWizardV2`, `ModernQueueManager`, and `ForceMajeureModal` callbacks.
- Local i18n keys unless the slice is explicitly copy-only and reviewed.
- Any logging policy change that could affect audit trails or PHI handling.

## First Safe Visual-Only Slice

Recommended first runtime slice:

1. Extract the local data source/status indicator into a small presentational component such as `RegistrarDataSourceIndicator`.
2. Props only: `dataSource`, `count`, `paginationTotal`, and `onRetry`.
3. Use existing macOS UI primitives only.
4. Preserve all conditional logic and labels from the current block.
5. Keep `loadAppointments`, filtering, data source state, queue events, payment actions, and dialogs untouched.

Alternative later candidates after the first slice passes:

- Extract only the visual header/date filter block, preserving all search param writes.
- Extract only a table empty/loading state block, preserving `filteredAppointments`, `appointmentsLoading`, `activeTab`, and `dataSource`.
- Extract welcome quick action visuals only if callbacks stay owned by `RegistrarPanel`.

## Execution Brief

Execution mode for the first registrar runtime slice: `gate` or `handoff`.

First-touch file:

- `frontend/src/pages/RegistrarPanel.jsx`

Reference-only files:

- `frontend/src/routing/routeRegistry.js`
- `frontend/src/routing/__tests__/routeContract.test.js`
- `frontend/src/components/ui/macos/*`
- `frontend/src/components/registrar/*`
- `frontend/src/utils/registrarPatientAggregation.js`
- `frontend/src/utils/ssotServiceMapping.js`

Narrow validation target:

- `git diff --check -- frontend\src\pages\RegistrarPanel.jsx`
- Static check that `loadAppointments`, queue/payment/cancel endpoint strings, `ModernQueueManager`, `PaymentDialog`, `PaymentManager`, `CancelDialog`, and `AppointmentWizardV2` references remain present.
- `npm.cmd run lint:check`
- `npm.cmd run test:run`
- `npm.cmd run build`
- If a browser target is available, smoke `/registrar` only with live role credentials resolved from the environment, never guessed from docs.

## Stop Conditions

Stop before editing or expanding if:

- A route, role, backend API, queue, payment, EMR, lab, or RBAC behavior change becomes necessary.
- Queue profile ownership or department mapping is unclear.
- A visual extraction requires changing `loadAppointments`, payment/cancel/start-visit behavior, aggregation, or query params.
- A test needs credentials that cannot be resolved from live local state.
- The slice touches more than one runtime file without a fresh gate/handoff.

## No Runtime Edit Confirmation

Task 40 creates this dossier only. No registrar runtime source file was edited in this task.
