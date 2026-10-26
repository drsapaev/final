## Summary
**What:** Added `aria-hidden="true"` to the button loading spinner SVG.
**Why:** Even though buttons communicate their loading state effectively via `aria-busy`, the internal visual spinner (`<svg>`) used within the button can still be picked up by screen readers as an empty image or graphic, adding noise.
**Before/After:** The visual is unchanged. The SVG now contains `aria-hidden="true"`.
**Accessibility:** Prevents screen readers from announcing the loading SVG redundantly when the button itself has `aria-busy`.

## Cyclic Execution Evidence
- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits
- Branch: palette/button-spinner-a11y
- Scope gate: allowed Button.tsx and ButtonTypography.test.tsx
- Red-check handling: fix any failed tests

## Contract Impact
not applicable - UI change only

## RBAC / Permissions
not applicable - UI change only

## Notification / Realtime
not applicable - UI change only

## Frontend Resilience
not applicable - UI change only

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/Button.tsx
- Denied paths: backend runtime
- Migration/docs/test impact: added UI unit test
- Rollback note: revert the UI changes

## Validation
- Targeted tests or smoke run: ButtonTypography.test.tsx
- Result: passed
- Not checked: backend
