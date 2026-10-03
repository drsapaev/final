## Summary

🎨 Palette: Add tooltip to clear input button

- 💡 What: Wrapped the `XCircle` icon button in `Input.tsx` with a `Tooltip` component.
- 🎯 Why: Replaced the native `title` attribute with a consistent, styled macOS-style tooltip from the design system, improving the UX for mouse users and maintaining screen reader accessibility without double announcements.
- 📸 Before/After: Visual tooltip matches the design system instead of relying on browser defaults.
- ♿ Accessibility: Removed the native `title` attribute to prevent double announcements alongside the `aria-label`. Added `t('clear_input')` via `useTranslation` without hardcoding strings.

## Cyclic Execution Evidence

- Fresh main sync: Yes
- Clean workspace: Yes
- Branch: palette-input-clear-tooltip
- Scope gate: Passed local testing and `pnpm test` + `pnpm lint:check`.
- Red-check handling: Addressed all lint errors and fixed a test failure in `MacOSInput.test.tsx` by wrapping the component in `<ThemeProvider>`.

## Contract Impact

- Canonical surface: Not applicable because this is a purely frontend UI component enhancement.
- Request shape: Not applicable because no network requests are made.
- Response shape: Not applicable because no network responses are handled.
- Status codes: Not applicable because no HTTP status codes are involved.
- Frontend consumer: Not applicable because this is an internal component detail.
- Compatibility path or alias: Not applicable because no API paths were changed.
- Contract proof: Not applicable because no API contracts are involved.

## RBAC / Permissions

- Roles allowed: Not applicable because this changes no backend authorization.
- Roles denied: Not applicable because this changes no backend authorization.
- Positive auth proof: Not applicable because this changes no backend authorization.
- Negative auth proof: Not applicable because this changes no backend authorization.

## Notification / Realtime

- Event type or websocket channel: Not applicable because no realtime functionality was altered.
- Payload version / ack behavior: Not applicable because no websockets are used.
- Read/unread or delivery semantics: Not applicable because no notifications are involved.
- Reconnect/resync proof: Not applicable because no realtime connections are established.

## Frontend Resilience

- Empty data proof: Not applicable because the input component already handles empty value states (the clear button is conditionally hidden).
- Partial data proof: Not applicable because the UI component receives synchronous props.
- Forbidden secondary path behavior: Not applicable because this component doesn't handle routing.
- Missing draft/resource behavior: Not applicable because this component doesn't fetch resources.
- Stale route/deep-link behavior: Not applicable because this component doesn't manage deep links.

## Scope Gate

- Allowed paths: frontend/src/components/ui/macos/Input.tsx, frontend/src/components/ui/macos/__tests__/MacOSInput.test.tsx
- Denied paths: Not applicable because no other paths were touched.
- Migration/docs/test impact: Adjusted `MacOSInput.test.tsx` to include `ThemeProvider`.
- Rollback note: Revert the commit to restore native `title` behavior.

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm test --run src/components/ui/macos/__tests__/`
- Result: Passed (38 passed).
- Not checked: End-to-end playwright tests were bypassed via visual screenshot script since the storybook configuration ran into timeout constraints.
