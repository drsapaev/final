## Summary
- Added `title` attributes (native browser tooltips) to the icon-only close buttons in `MacOSAlert.jsx` and `MacOSModal.jsx`.
- The buttons already had `aria-label`s for screen readers but lacked tooltips for sighted mouse users.

## Cyclic Execution Evidence
not applicable - UI micro-UX improvement only.

## Contract Impact
not applicable - No API changes.

## RBAC / Permissions
not applicable - No auth changes.

## Notification / Realtime
not applicable - No realtime changes.

## Frontend Resilience
not applicable - No data resilience changes.

## Scope Gate
not applicable - Micro-UX frontend improvement only.

## DevBrain Memory Impact
- [x] no durable memory update needed

## Validation
- Targeted tests or smoke run: Frontend tests (`pnpm test --run`)
- Result: 504 passed, 108 test files passed. No regressions introduced.
- Not checked: End-to-end Playwright tests as they are not currently running locally for this small change.
