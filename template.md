## Summary

- Added `aria-busy={loading}` to the native `<Button>` component (`frontend/src/components/ui/native/Button.jsx`).
- This small change ensures all native buttons properly communicate their processing status to screen readers.

## Contract Impact

not applicable - purely a UI accessibility attribute addition; no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed.

## Scope Gate

- Allowed paths: frontend/src/components/ui/native/Button.jsx
- Denied paths: backend runtime, unrelated frontend files
- Migration/docs/test impact: none; isolated UI change
- Rollback note: revert the aria-busy addition

## Validation

- Targeted tests or smoke run: ran local unit tests for the Button component
- Result: passed
- Not checked: runtime app behavior, because only a UI attribute was changed
