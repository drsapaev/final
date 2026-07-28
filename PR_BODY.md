## Summary
- Added aria-invalid to ui components
- No contract changes

## Cyclic Execution Evidence
- Fresh main sync: yes
- Clean workspace: yes
- Branch: palette/aria-invalid-inputs
- Scope gate: ui components
- Red-check handling: fix before merge

## Contract Impact
not applicable - UI component attribute changes only, no API contract changes.

## RBAC / Permissions
not applicable - UI components only, no auth changes.

## Notification / Realtime
not applicable - UI components only, no realtime changes.

## Frontend Resilience
not applicable - purely stylistic a11y attributes on components, no data flow changes.

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/
- Denied paths: backend
- Migration/docs/test impact: none
- Rollback note: revert the UI components changes

## Validation
- Targeted tests or smoke run: ran pnpm lint:check and tested the specific components
- Result: passed
- Not checked: backend tests
