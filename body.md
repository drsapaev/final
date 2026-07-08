🎨 Palette: Add ARIA labels to Modal close buttons

## Summary

- Added `aria-label="Закрыть"` and `title="Закрыть"` to the native close `button` instances in `frontend/src/components/common/Modal.jsx`.
- These buttons are rendered with an "×" character and had no accessible name. This causes screen readers to read out unhelpful generic names (like "button") or the raw character "times" instead of clarifying that it closes the modal.
- Provides a clear accessible name to screen readers indicating the action ("Закрыть").
- Provides a native browser tooltip for visual users using a mouse.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only frontend components changed
- Branch: palette/modal-close-accessibility
- Scope gate: allowed frontend component files; denied backend runtime, migrations, and generated output
- Red-check handling: fix any failed docs/gate check in this same PR before merge

## Contract Impact

not applicable - purely visual accessibility change, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

- Empty data proof: not applicable, visual change
- Partial data proof: not applicable, visual change
- Forbidden secondary path behavior: not applicable
- Missing draft/resource behavior: not applicable
- Stale route/deep-link behavior: not applicable

## Scope Gate

- Allowed paths: frontend/src/components/**
- Denied paths: backend runtime, migrations, generated output
- Migration/docs/test impact: frontend tests run to confirm no regressions
- Rollback note: revert the frontend component changes

## Validation

- Targeted tests or smoke run: frontend tests (Vitest) and linter checks run locally
- Result: passed
- Not checked: runtime app behavior, beyond the visual/accessible label addition
