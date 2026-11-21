## Summary
**What:** Added `aria-hidden="true"` and `focusable="false"` to decorative SVGs (loading spinners, progress rings) within `Button.tsx` and `Progress.tsx`. Also added a journal entry to `.Jules/palette.md`.
**Why:** Screen readers were potentially announcing redundant or confusing "unlabeled graphic" information for purely visual elements, despite the parent containers already correctly conveying the loading or progress state via ARIA attributes (`aria-busy`, `aria-valuenow`).
**Before/After:** No visual changes. Purely accessibility improvements.
**Accessibility:** Prevents screen readers from redundantly announcing purely decorative SVGs when the parent element already handles communicating the state via ARIA attributes.

## Cyclic Execution Evidence
- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits
- Branch: palette/a11y-loading-svgs
- Scope gate: allowed macos UI components and test files
- Red-check handling: fix any failed docs/gate check in this same PR before merge

## Contract Impact
not applicable - UI components accessibility only, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions
not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime
not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience
not applicable - accessibility improvement only, no user-facing panel or frontend data flow changed.

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/**, .Jules/palette.md
- Denied paths: backend runtime, migrations, generated output
- Migration/docs/test impact: accessibility only; no migration expected
- Rollback note: revert the UI changes

## DevBrain Memory Impact
- [x] no durable memory update needed

## Validation
- Targeted tests or smoke run: `vitest run src/components/ui/macos/__tests__/`
- Result: passed
- Not checked: runtime app behavior, because no runtime files changed
