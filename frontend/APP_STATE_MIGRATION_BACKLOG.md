# AppState Migration Backlog

This backlog tracks future migrations to the canonical macOS app-state primitives:

- `AppLoading`
- `AppEmpty`
- `AppError`

These primitives live in `frontend/src/components/ui/macos/AppState.jsx` and are exported from `frontend/src/components/ui/macos/index.js`. They are canonical for new loading, empty, and error UI in clinic operations screens.

Completed pilots:

- `frontend/src/pages/Health.jsx`
- `frontend/src/pages/Audit.jsx`

This document is search-based. The searches below identify recurring state patterns; selected candidates were spot-checked for risk and migration shape. It does not claim that every match was manually reviewed.

## Searches Run

```powershell
rg "Loading|Spinner|Skeleton|loading|isLoading|Загрузка|Загружается" frontend/src/pages frontend/src/components
rg "Empty|empty|No data|Нет данных|Ничего не найдено|Пусто|данные не" frontend/src/pages frontend/src/components
rg "Error|error|Ошибка|Не удалось|failed|failure|setError" frontend/src/pages frontend/src/components
rg "AppLoading|AppEmpty|AppError" frontend/src
```

## Inventory

### Loading

Repeated loading patterns found:

- Inline text such as `Загрузка...` or `Загрузка статуса...`.
- Boolean state names such as `loading`, `busy`, and `isLoading`.
- Local spinner markup using icon animation or CSS classes.
- `MacOSLoadingSkeleton` used directly in many admin surfaces.
- Shared or legacy loading helpers such as `components/common/Loading.jsx`, `components/AnimatedLoader.jsx`, and `components/admin/LoadingSkeleton.jsx`.

Representative files:

- `frontend/src/pages/Activation.jsx`
- `frontend/src/pages/Appointments.jsx`
- `frontend/src/pages/Search.jsx`
- `frontend/src/pages/PatientPickupView.jsx`
- `frontend/src/pages/AnalyticsPage.jsx`
- `frontend/src/components/admin/ActivationSystem.jsx`
- `frontend/src/components/admin/AISettings.jsx`
- `frontend/src/components/admin/DisplayBoardSettings.jsx`
- `frontend/src/components/admin/QueueLimitsManager.jsx`
- `frontend/src/components/admin/QueueProfilesManager.jsx`
- `frontend/src/components/admin/AdminSection.jsx`
- `frontend/src/components/admin/ServiceAuditHistory.jsx`
- `frontend/src/components/payment/PaymentManager.jsx`

### Error

Repeated error patterns found:

- `setErr`, `setError`, and `setMessage({ type: 'error' })` state handling.
- Inline blocks such as `legacy-error`, `styles.error`, and red utility classes.
- Toast-only API errors without a stable page-level error state.
- Local retry or reload actions embedded in page-specific error markup.
- Shared admin error wrappers that still use non-canonical UI layers.

Representative files:

- `frontend/src/pages/Activation.jsx`
- `frontend/src/pages/Appointments.jsx`
- `frontend/src/pages/Search.jsx`
- `frontend/src/pages/PatientPickupView.jsx`
- `frontend/src/components/admin/AdminSection.jsx`
- `frontend/src/components/admin/ActivationSystem.jsx`
- `frontend/src/components/admin/AISettings.jsx`
- `frontend/src/components/admin/QueueProfilesManager.jsx`
- `frontend/src/components/admin/DisplayBoardSettings.jsx`
- `frontend/src/components/common/ScheduleNextModal.jsx`
- `frontend/src/components/dialogs/PrintDialog.jsx`

### Empty

Repeated empty-state patterns found:

- Inline `Нет данных`, `Нет записей`, or `Ничего не найдено` text.
- Local empty components such as `AnalyticsEmptyState`, `PanelEmptyState`, and `components/admin/EmptyState.jsx`.
- Direct `MacOSEmptyState` usage where `AppEmpty` would be more canonical for page-level or panel-level app state.
- Table empty rows using `colSpan`.
- CSS-specific `.empty-state` blocks in chat, payment, EMR, and wizard areas.

Representative files:

- `frontend/src/pages/Activation.jsx`
- `frontend/src/pages/Appointments.jsx`
- `frontend/src/pages/Search.jsx`
- `frontend/src/pages/PatientPickupView.jsx`
- `frontend/src/pages/AnalyticsPage.jsx`
- `frontend/src/components/admin/ServiceAuditHistory.jsx`
- `frontend/src/components/admin/CloudPrintingManager.jsx`
- `frontend/src/components/common/Table.jsx`
- `frontend/src/components/payment/PaymentManager.jsx`
- `frontend/src/components/queue/QueueTable.jsx`

### Mixed State Blocks

Files with loading, empty, and error handling near each other:

- `frontend/src/pages/Activation.jsx`
- `frontend/src/pages/Appointments.jsx`
- `frontend/src/pages/Search.jsx`
- `frontend/src/pages/PatientPickupView.jsx`
- `frontend/src/pages/AnalyticsPage.jsx`
- `frontend/src/components/admin/AdminSection.jsx`
- `frontend/src/components/admin/ActivationSystem.jsx`
- `frontend/src/components/admin/AISettings.jsx`
- `frontend/src/components/admin/QueueProfilesManager.jsx`
- `frontend/src/components/payment/PaymentManager.jsx`

### Table Empty States

Files with table-level or list-level empty state patterns:

- `frontend/src/pages/Appointments.jsx`
- `frontend/src/pages/Audit.jsx` already migrated
- `frontend/src/components/common/Table.jsx`
- `frontend/src/components/ui/macos/MacOSTable.jsx`
- `frontend/src/components/tables/EnhancedAppointmentsTable.jsx`
- `frontend/src/components/admin/ServiceCatalog.jsx`
- `frontend/src/components/admin/QueueLimitsManager.jsx`
- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/pages/RegistrarPanel.jsx`

### Form and API Error States

Files with form or API error patterns that need extra care:

- `frontend/src/components/admin/QueueProfilesManager.jsx`
- `frontend/src/components/common/ScheduleNextModal.jsx`
- `frontend/src/components/dialogs/PrintDialog.jsx`
- `frontend/src/components/auth/ForgotPassword.jsx`
- `frontend/src/components/auth/PhoneVerification.jsx`
- `frontend/src/components/security/TwoFactorManager.jsx`
- `frontend/src/pages/auth/ChangePasswordRequired.jsx`

## Risk Classification

### Low Risk

Good next candidates when the file has simple fetch -> state -> render behavior:

- Technical/status pages.
- Small admin utility components.
- Small pages with local `loading`, `err`, and empty data states.
- Components that already use macOS primitives and have isolated loading/empty blocks.

### Medium Risk

Use a dedicated small PR and inspect behavior carefully:

- Dashboards.
- Pages with filters, tables, pagination, or multiple sections.
- Shared components used by several admin pages.
- Payment-adjacent visual states where payment API behavior is untouched.
- Admin utility pages with create/update/delete actions.

### High Risk

Needs dedicated review before any migration:

- Role panels.
- `QueueJoin`.
- EMR.
- Lab.
- Registrar workflows.
- Payment domain logic.
- Auth/login flows.
- Shared table primitives used broadly across the app.

## Recommended Migration Order

No mass refactor.

1. Phase A: small non-clinical pages with simple loading/error/empty states.
2. Phase B: table empty/error states in low-risk admin pages.
3. Phase C: payment-adjacent visual states only, without payment API or domain changes.
4. Phase D: role panels one slice at a time, after a dedicated route/workflow review.
5. Phase E: clinical-heavy flows only after dedicated review and behavior-specific validation.

## Top 10 Candidate Migrations

| Rank | File | Current state pattern | Recommended primitive | Risk | Effort | Acceptance criteria | Do not change |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `frontend/src/pages/Activation.jsx` | Inline loading text, inline error box, inline no-data text | `AppLoading`, `AppError`, `AppEmpty` | Low | S | Loading/status/list empty states render through AppState primitives; API calls and Admin `RoleGate` remain unchanged | Activation API calls, filter behavior, roles |
| 2 | `frontend/src/pages/Appointments.jsx` | `legacy-error`, refresh button busy text, table `colSpan` empty row | `AppError`, `AppEmpty`; only use `AppLoading` for an initial table state if behavior stays identical | Medium | S | Error and empty table state use AppState primitives; date/search filtering and table columns are unchanged | `/appointments` fallback request, filters, advanced table toggle, appointment flow |
| 3 | `frontend/src/pages/Search.jsx` | Local error box and no-results block | `AppError`, `AppEmpty`; keep button spinner as-is unless local-only | Low | S | No-results and search error states use AppState primitives; search query behavior is unchanged | Search API calls, result grouping, navigation |
| 4 | `frontend/src/pages/PatientPickupView.jsx` | Full-page loading and error blocks with local styles | `AppLoading`, `AppError` | Low/Medium | S | Loading/error page states use AppState primitives; pickup token handling and displayed patient data stay unchanged | Route params, pickup/session logic, patient data rendering |
| 5 | `frontend/src/components/admin/AdminSection.jsx` | Shared loading skeleton and error block using native `Card`/utility classes | `AppLoading`, `AppError` or a wrapper using macOS `Card` | Medium | M | Existing consumers still render; section loading/error states use canonical primitives | Component API, reload action semantics, consumers |
| 6 | `frontend/src/components/admin/ServiceAuditHistory.jsx` | Direct `MacOSLoadingSkeleton` and `MacOSEmptyState` for a small audit-history panel | `AppLoading`, `AppEmpty`; consider `AppError` only if adding visible error remains behavior-preserving | Low | S | Loading and empty history states use AppState primitives; history fetch/rendering is unchanged | `servicesService.getServiceHistory`, expansion behavior, history row fields |
| 7 | `frontend/src/components/admin/ActivationSystem.jsx` | Full loading return and `setMessage({ type: 'error' })` blocks | `AppLoading`, possibly `AppError` for load failure only | Low/Medium | S | Initial loading state is canonical; action messages remain unchanged unless explicitly scoped | Create/revoke/extend activation behavior, clipboard behavior |
| 8 | `frontend/src/components/admin/AISettings.jsx` | Full loading return and message-driven error display | `AppLoading`, possibly `AppError` for load failure only | Low/Medium | S | Initial loading state is canonical; provider save/test behavior remains unchanged | AI provider settings, test API, copy that affects AI policy |
| 9 | `frontend/src/components/admin/QueueLimitsManager.jsx` | Full loading return and table/list empty state string | `AppLoading`, `AppEmpty` | Medium | M | Initial loading and queue status empty state use primitives; limit calculations and save/reset behavior are unchanged | Queue domain limits, utilization logic, API calls |
| 10 | `frontend/src/components/admin/CloudPrintingManager.jsx` | Repeated grid empty state through `MacOSEmptyState`; loading only in action buttons | `AppEmpty` for grid empty state | Medium | S | Empty printer lists use AppState primitives; print/test actions are unchanged | Printer API calls, print payloads, toast behavior |

## Dedicated Review Items

These are not good immediate candidates despite search hits:

- `frontend/src/pages/AdminPanel.jsx`: very large role panel; migrate one tab or state block only after a dedicated prompt.
- `frontend/src/pages/RegistrarPanel.jsx`: role workflow and queue/payment adjacency; needs dedicated review.
- `frontend/src/pages/DoctorPanel.jsx`, `CardiologistPanelUnified.jsx`, `DentistPanelUnified.jsx`, `DermatologistPanelUnified.jsx`: clinical workflow risk.
- `frontend/src/pages/LabPanel.jsx` and `frontend/src/components/laboratory/*`: lab workflow risk.
- `frontend/src/pages/QueueJoin.jsx`: public queue behavior and language/locale risk.
- `frontend/src/components/emr-v2/*`: clinical-heavy EMR state, AI suggestions, and draft behavior.
- `frontend/src/components/payment/PaymentManager.jsx`: payment-adjacent; visual-only migration later, no domain logic changes.
- `frontend/src/components/common/Table.jsx` and `frontend/src/components/ui/macos/MacOSTable.jsx`: shared primitives; changing them affects many screens.
- Auth and 2FA files such as `LoginFormStyled.jsx`, `ForgotPassword.jsx`, `PhoneVerification.jsx`, and `TwoFactorManager.jsx`: auth-sensitive.

## Hard Rules For Future Migrations

- One runtime page or component per PR.
- No backend changes.
- No API behavior changes.
- No route, role, or guard changes.
- No table, filter, sorting, or pagination semantic changes.
- No mass panel refactor.
- Preserve copy meaning unless existing copy is unsafe or unclear.
- Prefer `AppLoading`, `AppEmpty`, and `AppError` from `frontend/src/components/ui/macos`.
- Keep local button busy labels when they are action-specific and not page-level app state.
- Run `git diff --check`, `npm.cmd run lint:check`, `npm.cmd run test:run`, and `npm.cmd run build` for runtime migration PRs unless the prompt narrows validation.

## Example AppState Migration PR Template

```markdown
## Summary
- Migrates exactly one page/component from local loading/error/empty UI to `AppLoading`, `AppEmpty`, and/or `AppError`.
- Preserves data fetching, table/filter behavior, routes, roles, and business logic.

## Scope
- Target: `frontend/src/...`
- AppState primitives used:
- Runtime files changed:
- Tests changed, if any:

## Behavior Preserved
- API calls:
- Route/role behavior:
- Table/filter/pagination semantics:
- Copy meaning:

## Validation
- `git diff --check`:
- `npm.cmd run lint:check`:
- `npm.cmd run test:run`:
- `npm.cmd run build`:
- Not checked:

## Explicitly Not Changed
- Backend:
- Routing:
- Auth/RBAC:
- Payment/queue/EMR/lab logic:
- Other pages/panels:
```

## Suggested Prompt #11 Target

Use `frontend/src/pages/Activation.jsx` as the next runtime candidate if it is still unchanged. It is a small non-clinical page with simple loading, error, and empty states, making it a good follow-up after `Health.jsx` and `Audit.jsx`.
