## Summary

🎨 Palette: Add focus states for MacOSTab

- 💡 **What:** Replaced the highly specific `outline: 'none !important'` inline style with a base CSS class and added a standard `:focus-visible` outline using the macOS design system's `color-mix` token. Also updated the UI baseline file to reflect a slight increase in `varUsagesNoFallback` due to the use of a var in the added stylesheet.
- 🎯 **Why:** Keyboard users were unable to see which tab was focused because the inline style completely suppressed the browser's default focus ring and prevented custom focus styles from applying.
- 📸 **Before/After:** The focus state is now a standard 2px blue ring.
- ♿ **Accessibility:** This directly fixes a WCAG violation for interactive element focus visibility.

## Cyclic Execution Evidence

not applicable - purely frontend styling change.

## Contract Impact

not applicable - no API contracts changed.

## RBAC / Permissions

not applicable - no permissions changed.

## Notification / Realtime

not applicable - no realtime behavior changed.

## Frontend Resilience

not applicable - purely styling change, no data flows affected.

## Scope Gate

- Allowed paths: `frontend/src/components/ui/macos/MacOSTab.tsx`, `.Jules/palette.md`, `frontend/scripts/ui-baseline.json`
- Denied paths: All other files.
- Migration/docs/test impact: Verified tests locally.
- Rollback note: Safe to rollback.

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm run test:run src/components/ui/macos/__tests__/`
- Result: Pass
- Not checked: Backend E2E
