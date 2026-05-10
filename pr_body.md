## Summary

- Added `aria-label` attributes to icon-only action buttons (Print, View, Edit, View EMR, More) in the `EnhancedAppointmentsTable` component.

## Contract Impact

- Canonical surface: not applicable - no backend change
- Request shape: not applicable - no backend change
- Response shape: not applicable - no backend change
- Status codes: not applicable - no backend change
- Frontend consumer: not applicable - no backend change
- Compatibility path or alias: not applicable - no backend change
- Contract proof: not applicable - purely frontend accessibility attribute changes, no API or contracts altered.

## RBAC / Permissions

- Roles allowed: not applicable - no backend change
- Roles denied: not applicable - no backend change
- Positive auth proof: not applicable - no backend change
- Negative auth proof: not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

- Event type or websocket channel: not applicable - no backend change
- Payload version / ack behavior: not applicable - no backend change
- Read/unread or delivery semantics: not applicable - no backend change
- Reconnect/resync proof: not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

- Empty data proof: not applicable - no logic change
- Partial data proof: not applicable - no logic change
- Forbidden secondary path behavior: not applicable - no logic change
- Missing draft/resource behavior: not applicable - no logic change
- Stale route/deep-link behavior: not applicable - no user-facing panel or frontend data flow changed, only added screen reader labels.

## Scope Gate

- Allowed paths: frontend/src/components/tables/EnhancedAppointmentsTable.jsx
- Denied paths: backend runtime, migrations, generated output
- Migration/docs/test impact: tested via existing frontend test suites
- Rollback note: revert the aria-label attribute additions

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm test` and `cd frontend && pnpm lint`
- Result: passed
- Not checked: backend validation, because no backend or contract files changed
