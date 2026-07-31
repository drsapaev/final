## Summary

- Refactored `LanguageSwitcher.jsx` to use React state for hover/focus instead of direct DOM manipulation.
- Added semantic roles (`menu`, `menuitem`), and implemented `Escape` key handling to close the dropdown.
- Fixed keyboard accessibility and screen reader support (added `aria-haspopup`, `aria-expanded`, and `aria-label`).
- Visuals are identical, but interaction and screen reader structure are vastly improved.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only frontend/src/components/LanguageSwitcher.jsx changed
- Branch: palette/language-switcher-a11y
- Scope gate: allowed frontend UI components; denied backend runtime, migrations, and generated output
- Red-check handling: fix any failed docs/gate check in this same PR before merge

## Contract Impact

not applicable - UI refactoring only, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

- Empty data proof: not applicable - purely presentational changes.
- Partial data proof: not applicable - no data fetched.
- Forbidden secondary path behavior: not applicable - no routing changes.
- Missing draft/resource behavior: not applicable - no API requests.
- Stale route/deep-link behavior: not applicable - no routing changes.

## Scope Gate

- Allowed paths: frontend/src/components/LanguageSwitcher.jsx
- Denied paths: backend runtime, migrations, generated output
- Migration/docs/test impact: none expected
- Rollback note: revert the frontend file changes

## Validation

- Targeted tests or smoke run: ran `pnpm test` and `pnpm lint` in the `frontend` directory.
- Result: passed
- Not checked: visual behavior in the main app, as `LanguageSwitcher.jsx` is not actively imported/rendered in the current main tree.
