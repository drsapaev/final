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
- Canonical surface: not applicable
- Request shape: not applicable
- Response shape: not applicable
- Status codes: not applicable
- Frontend consumer: not applicable
- Compatibility path or alias: not applicable
- Contract proof: not applicable

## RBAC / Permissions
- Roles allowed: not applicable
- Roles denied: not applicable
- Positive auth proof: not applicable
- Negative auth proof: not applicable

## Notification / Realtime
- Event type or websocket channel: not applicable
- Payload version / ack behavior: not applicable
- Read/unread or delivery semantics: not applicable
- Reconnect/resync proof: not applicable

## Frontend Resilience
- Empty data proof: not applicable
- Partial data proof: not applicable
- Forbidden secondary path behavior: not applicable
- Missing draft/resource behavior: not applicable
- Stale route/deep-link behavior: not applicable

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/Button.tsx
- Denied paths: backend runtime
- Migration/docs/test impact: added UI unit test
- Rollback note: revert the UI changes

## Validation
- Targeted tests or smoke run: ButtonTypography.test.tsx
- Result: passed
- Not checked: backend
