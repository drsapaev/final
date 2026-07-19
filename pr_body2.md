💡 What: Added `aria-label` attributes to the toggle, theme, and language buttons in the `UnifiedSidebar` component to match their existing localized `title` text.

🎯 Why: When the sidebar is collapsed, these buttons become icon-only. Without `aria-label`s, screen readers have no accessible text to read, making it difficult for visually impaired users to interact with these core navigation features.

📸 Before/After: Visuals remain entirely unchanged; this is an underlying HTML semantics improvement.

♿ Accessibility: The sidebar toggle, theme switcher, and language selector are now fully accessible to screen readers, providing clear context of their function in both expanded and collapsed states.

## Summary

- Add `aria-label` attributes to UnifiedSidebar icon-only buttons.
- Match existing localized `title` text to ensure screen reader accessibility.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only `UnifiedSidebar.jsx` changed
- Branch: `jules-palette-a11y-sidebar-buttons-v3`
- Scope gate: allowed frontend UI component edits; denied backend runtime and migrations
- Red-check handling: fixed any failed checks in this same PR before merge

## Contract Impact

not applicable - UI accessibility improvement only, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - purely HTML attributes (aria-labels) were added, no user-facing panel data flow changed.

## Scope Gate

- Allowed paths: `frontend/src/components/layout/UnifiedSidebar.jsx`
- Denied paths: backend runtime, frontend routing, migrations, generated output
- Migration/docs/test impact: frontend tests run to confirm no regressions
- Rollback note: revert the `UnifiedSidebar.jsx` changes

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm test --run`
- Result: passed
- Not checked: runtime backend behavior, because no backend files changed
