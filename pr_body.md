## Summary

- Added `title` attributes (native browser tooltips) to the icon-only close buttons in `MacOSAlert.jsx` and `MacOSModal.jsx`.
- The buttons already had `aria-label`s for screen readers but lacked tooltips for sighted mouse users.

## Cyclic Execution Evidence

- Fresh main sync: `git checkout main && git pull`
- Clean workspace: `git status` shows clean before branch
- Branch: `palette/macos-alert-modal-close-tooltips`
- Scope gate: Modified only `frontend/src/components/ui/macos/MacOSAlert.jsx` and `frontend/src/components/ui/macos/MacOSModal.jsx`
- Red-check handling: Pre-commit PR body checks passing.

## Contract Impact

not applicable - No API changes.

## RBAC / Permissions

not applicable - No auth changes.

## Notification / Realtime

not applicable - No realtime changes.

## Frontend Resilience

not applicable - No data resilience changes.

## Scope Gate

- Allowed paths: `frontend/src/components/ui/macos/MacOSAlert.jsx`, `frontend/src/components/ui/macos/MacOSModal.jsx`
- Denied paths: All other paths.
- Migration/docs/test impact: No impact.
- Rollback note: Revert the PR if it causes issues.

## DevBrain Memory Impact

- [x] no durable memory update needed

## Validation

- Targeted tests or smoke run: Frontend tests (`pnpm test --run`)
- Result: 504 passed, 108 test files passed. No regressions introduced.
- Not checked: End-to-end Playwright tests as they are not currently running locally for this small change.
