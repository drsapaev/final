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
- Canonical surface: not applicable - purely frontend styling
- Request shape: not applicable - purely frontend styling
- Response shape: not applicable - purely frontend styling
- Status codes: not applicable - purely frontend styling
- Frontend consumer: not applicable - purely frontend styling
- Compatibility path or alias: not applicable - purely frontend styling
- Contract proof: not applicable - purely frontend styling

## RBAC / Permissions
- Roles allowed: not applicable - purely frontend styling
- Roles denied: not applicable - purely frontend styling
- Positive auth proof: not applicable - purely frontend styling
- Negative auth proof: not applicable - purely frontend styling

## Notification / Realtime
- Event type or websocket channel: not applicable - purely frontend styling
- Payload version / ack behavior: not applicable - purely frontend styling
- Read/unread or delivery semantics: not applicable - purely frontend styling
- Reconnect/resync proof: not applicable - purely frontend styling

## Frontend Resilience
- Empty data proof: not applicable - purely frontend styling
- Partial data proof: not applicable - purely frontend styling
- Forbidden secondary path behavior: not applicable - purely frontend styling
- Missing draft/resource behavior: not applicable - purely frontend styling
- Stale route/deep-link behavior: not applicable - purely frontend styling

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/Button.tsx
- Denied paths: backend runtime
- Migration/docs/test impact: added UI unit test
- Rollback note: revert the UI changes

## Validation
- Targeted tests or smoke run: ButtonTypography.test.tsx
- Result: passed
- Not checked: backend
