# Roles And Routing

This document reflects the frontend routing contract under `frontend/src/routing/`.
The code-first source of truth is:

- `frontend/src/routing/routeRegistry.js`
- `frontend/src/routing/routeSelectors.js`
- `frontend/src/routing/routeGuards.jsx`
- `frontend/src/routing/routeDocsSnapshot.js`

## Route Groups

### Public
- `/`
- `/login`
- `/health`
- `/queue/join`
- `/queue/join/:token`
- `/queue-board`
- `/display-board`
- `/display-board/:role`
- `/payment/success`
- `/payment/cancel`
- `/unauthorized`
- `/forbidden`
- `/not-found`

### Onboarding
- `/setup`

### Clinical
Canonical role homes:
- `Admin` -> `/admin`
- `Registrar` -> `/registrar`
- `Doctor` -> `/doctor`
- `Cashier` -> `/cashier`
- `Lab` -> `/lab`
- `cardio` -> `/doctor/cardiology`
- `derma` -> `/doctor/dermatology`
- `dentist` -> `/doctor/dentistry`
- `Patient` -> `/patient`

Shared clinical workspaces:
- `/clinical/scheduler`
- `/clinical/appointments`
- `/clinical/search`
- `/clinical/profile`
- `/clinical/security`
- `/clinical/security/two-factor`
- `/clinical/visits/:id`
- `/clinical/pickup/:patientId`

### Admin
Canonical admin IA now lives under `/admin/*`.

Primary admin routes:
- `/admin`
- `/admin/analytics`
- `/admin/users`
- `/admin/settings`
- `/admin/security`
- `/admin/audit`
- `/admin/notifications`
- `/admin/integrations/telegram`
- `/admin/activation`
- `/admin/file-management`
- `/admin/advanced-users`
- `/admin/user-select`

Additional admin subsections remain under `/admin/*` and are tracked in the route registry.

### Internal Demo
Internal demo surfaces are no longer part of production IA.

Canonical internal-demo routes:
- `/internal-demo/medilab`
- `/internal-demo/macos`
- `/internal-demo/integration`
- `/internal-demo/payment-test`
- `/internal-demo/css-test`
- `/internal-demo/buttons`

Policy:
- never visible in production navigation
- never used for role-home routing
- treated as internal-only surfaces
- available only when internal demo routing is enabled

## Compatibility Redirects

Legacy URLs still work, but they redirect to canonical destinations.

Examples:
- `/registrar-panel` -> `/registrar`
- `/doctor-panel` -> `/doctor`
- `/cashier-panel` -> `/cashier`
- `/lab-panel` -> `/lab`
- `/cardiologist` -> `/doctor/cardiology`
- `/dermatologist` -> `/doctor/dermatology`
- `/dentist` -> `/doctor/dentistry`
- `/scheduler` -> `/clinical/scheduler`
- `/appointments` -> `/clinical/appointments`
- `/search` -> `/clinical/search`
- `/profile` -> `/clinical/profile`
- `/security` -> `/clinical/security`
- `/visits/:id` -> `/clinical/visits/:id`
- `/pickup/:patientId` -> `/clinical/pickup/:patientId`
- `/settings` -> `/admin/settings`
- `/analytics` -> `/admin/analytics`
- `/audit` -> `/admin/audit`
- `/notifications` -> `/admin/notifications`
- `/telegram-integration` -> `/admin/integrations/telegram`
- `/advanced-users` -> `/admin/advanced-users`
- `/file-management` -> `/admin/file-management`
- `/user-select` -> `/admin/user-select`
- `/payment/test` -> `/internal-demo/payment-test`
- `/css-test` -> `/internal-demo/css-test`
- `/buttons` -> `/internal-demo/buttons`
- `/medilab-demo` -> `/internal-demo/medilab`
- `/macos-demo` -> `/internal-demo/macos`
- `/integration-demo` -> `/internal-demo/integration`
- `/old-login` -> `/login`

## Setup Gating

Setup precedence is enforced by routing guards, not by page-local logic:

1. Public and callback routes remain reachable before initialization.
2. When the app is not initialized, `clinical` and `admin` routes redirect to `/setup`.
3. When the app is initialized, `/setup` redirects to `/login`.
4. `/login` and `/setup` must not loop.

## Auth And Role Policy

- `public`: no auth required
- `authenticated`: any signed-in user
- `role-scoped`: signed-in user plus explicit allowed roles from the route registry

Role normalization:
- `Receptionist` is treated as `registrar`
- `Nurse` is treated as `doctor`

## Error Routes

Canonical system routes:
- `/unauthorized`
- `/forbidden`
- `/not-found`

## Notes

- This document is intentionally a contract summary, not a hand-maintained second route table.
- If route ownership, IA grouping, shell behavior, or compatibility rules change, update the routing registry first and then refresh this summary.
