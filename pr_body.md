## Summary

- Added `aria-label` attributes to icon-only action buttons (Print, View, Edit, View EMR, More) in the `EnhancedAppointmentsTable` component.

## Contract Impact

not applicable - purely frontend accessibility attribute changes, no API or contracts altered.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed.

## Scope Gate

- Allowed paths: frontend/src/components/tables/EnhancedAppointmentsTable.jsx
- Denied paths: backend runtime, migrations, generated output
- Migration/docs/test impact: tested via existing frontend test suites
- Rollback note: revert the aria-label attribute additions

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm test` and `cd frontend && pnpm lint`
- Result: passed
- Not checked: backend validation, because no backend or contract files changed
