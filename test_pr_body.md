## Summary

🎨 Palette: Add `aria-invalid` to core form controls.
Added the `aria-invalid={!!error}` attribute to the core form control components in `src/components/ui/macos/` (`Input.tsx`, `Textarea.tsx`, `Checkbox.tsx`, `Select.tsx`). These form controls previously supported an `error` prop for visual styling (red borders), but did not communicate this invalid state to assistive technologies like screen readers. Adding `aria-invalid` ensures visually impaired users are properly informed when form validation fails.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only ui/macos components changed
- Branch: palette-form-aria-invalid
- Scope gate: allowed ui/macos form component files
- Red-check handling: fix any failed unit tests in this same PR before merge

## Contract Impact

not applicable - UI accessibility improvement only, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - this only adds an aria-attribute without altering runtime application logic or layout.

## Scope Gate

- Allowed paths: frontend/src/components/ui/macos/Input.tsx, frontend/src/components/ui/macos/Textarea.tsx, frontend/src/components/ui/macos/Checkbox.tsx, frontend/src/components/ui/macos/Select.tsx
- Denied paths: backend runtime, migrations, generated output
- Migration/docs/test impact: none expected
- Rollback note: revert the component changes

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm test --run src/components/ui/macos/`
- Result: passed
- Not checked: runtime backend behavior, because no runtime files changed
