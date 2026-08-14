## Summary

- Added `aria-busy={loading}` and `aria-live="polite"` attributes to the EnhancedAppointmentsTable wrapper (`.eat-table-scroll`).
- Screen reader users are now properly notified when the table is fetching data, rather than relying solely on the visual loading spinner.

## Cyclic Execution Evidence

- Fresh main sync: yes
- Clean workspace: inspected before edits; only `frontend/src/components/tables/EnhancedAppointmentsTable.tsx` and `.Jules/palette.md` changed.
- Branch: palette/aria-busy-table
- Scope gate: frontend UI changes only
- Red-check handling: fix any failed docs/gate check in this same PR before merge

## Contract Impact

not applicable - purely frontend accessibility change, no API or contracts affected.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

- Empty data proof: not applicable, does not affect data loading logic, only aria attributes.
- Partial data proof: not applicable, no data parsing changes.
- Forbidden secondary path behavior: not applicable - does not change routing
- Missing draft/resource behavior: not applicable - no new resource changes
- Stale route/deep-link behavior: not applicable - not changing routing

## Scope Gate

- Allowed paths: frontend/src/components/tables/EnhancedAppointmentsTable.tsx, .Jules/palette.md
- Denied paths: backend runtime, migrations
- Migration/docs/test impact: local `.Jules/palette.md` memory log added
- Rollback note: revert the DOM attribute changes in the table component

## DevBrain Memory Impact

- [x] no durable memory update needed
- [ ] PROJECT_MEMORY updated
- [ ] DEVBRAIN_STATUS updated
- [ ] AI Factory dossier/log/patch updated
- [ ] agent_gate routing rule updated
- [ ] indexes/artifacts refreshed locally
- [ ] regression matrix run

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm test --run`
- Result: passed
- Not checked: backend tests since no backend files changed.
