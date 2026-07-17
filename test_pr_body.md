## Summary

- Added the `aria-invalid` attribute to the underlying native `<input>` element in the custom MacOS UI `Input` component.
- Added the `aria-invalid` attribute to the underlying native `<textarea>` element in the custom MacOS UI `Textarea` component.
- Bound both attributes to the `error` prop state (`!!error`).

## Cyclic Execution Evidence

- Fresh main sync: yes
- Clean workspace: yes
- Branch: palette/a11y-form-controls
- Scope gate: passed
- Red-check handling: passed

## Contract Impact

not applicable - no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed structurally (only ARIA properties added).

## Scope Gate

- Allowed paths: frontend/src/components/ui/macos/Input.jsx, frontend/src/components/ui/macos/Textarea.jsx
- Denied paths: other paths
- Migration/docs/test impact: none
- Rollback note: trivial code revert

## DevBrain Memory Impact

- [x] no durable memory update needed
- [ ] PROJECT_MEMORY updated
- [ ] DEVBRAIN_STATUS updated
- [ ] AI Factory dossier/log/patch updated
- [ ] agent_gate routing rule updated
- [ ] indexes/artifacts refreshed locally
- [ ] regression matrix run

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm test --run src/components/ui/macos/__tests__/MacOSInput.test.jsx`
- Result: passed
- Not checked: comprehensive manual screen reader testing
