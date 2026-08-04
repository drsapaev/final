## Summary

- Added `aria-label="Закрыть"` and `title="Закрыть"` to the icon-only Close button that appears when the `Modal` component is in `fullscreen` size.
- Ensure screen readers and tooltips have standard accessible information matching similar `Alert.tsx` close buttons.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only `Modal.tsx` modified
- Branch: palette-modal-close-a11y
- Scope gate: allowed `frontend/src/components/ui/macos/Modal.tsx`; denied all backend, unrelated frontend code, DB migrations.
- Red-check handling: fix any CI failed check in this same PR.

## Contract Impact

not applicable - this is a pure UI accessibility change, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed. (UI semantics updated)

## Scope Gate

- Allowed paths: `frontend/src/components/ui/macos/Modal.tsx`
- Denied paths: backend runtime, unrelated frontend code, DB migrations, generated output
- Migration/docs/test impact: none needed
- Rollback note: revert `Modal.tsx`

## DevBrain Memory Impact

- [x] no durable memory update needed

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm lint:check` and `cd frontend && pnpm test --run` executed locally.
- Result: passed, ignoring unrelated pre-existing failures.
- Not checked: runtime browser behavior as this does not affect rendering or functionality.
