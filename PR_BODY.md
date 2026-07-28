**💡 What:** Added `aria-invalid={!!error}` to the `Input`, `Textarea`, and `Select` components within `frontend/src/components/ui/macos/`.
**🎯 Why:** To ensure that screen readers properly announce form validation error states on these controls, improving accessibility for visually impaired users.
**📸 Before/After:** Screen readers previously did not consistently read out the error state of these fields automatically. With `aria-invalid`, they now detect and announce it properly when validation fails.
**♿ Accessibility:** Enhanced ARIA attribute adherence for native accessibility notifications.

## Summary
- Added `aria-invalid` attribute to macos UI components (Input, Textarea, Select).
- Improves accessibility by letting screen readers announce form validation error states.

## Cyclic Execution Evidence
- Fresh main sync: yes
- Clean workspace: yes
- Branch: palette/aria-invalid-inputs-v2
- Scope gate: allowed paths: frontend/src/components/ui/macos/
- Red-check handling: fix any before merge

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
